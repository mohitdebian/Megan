"""
Email Monitor — Autonomously checks the IMAP inbox for important emails.
"""

import asyncio
import imaplib
import email
from email.header import decode_header
import structlog
from config import get_settings
from core.events import EventBus, Event, EventType
from core.classifier import PriorityClassifier
import uuid

logger = structlog.get_logger(__name__)


class EmailMonitor:
    def __init__(self, event_bus: EventBus):
        self.settings = get_settings()
        self.event_bus = event_bus
        self.classifier = PriorityClassifier()
        self._task: asyncio.Task | None = None
        self._is_running = False
        
        # Keep track of seen email IDs to avoid repeating announcements
        self._seen_uids = set()

    async def start(self):
        """Start the email monitoring loop."""
        if self._is_running:
            return
            
        if not self.settings.email.email_address or not self.settings.email.app_password:
            logger.warning("email_monitor_skipped", reason="no credentials")
            return
            
        self._is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("email_monitor_started")

    async def stop(self):
        """Stop the email monitoring loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("email_monitor_stopped")

    async def _monitor_loop(self):
        """Poll the IMAP inbox every 60 seconds."""
        # Initial wait so we don't block startup
        await asyncio.sleep(10)
        
        while self._is_running:
            try:
                await self._check_inbox()
            except Exception as e:
                logger.error("email_monitor_error", error=str(e))
                
            # Wait 60 seconds before checking again
            await asyncio.sleep(60)

    async def _check_inbox(self):
        """Fetch unread emails and classify them."""
        # Use asyncio.to_thread since imaplib is blocking
        emails = await asyncio.to_thread(self._fetch_unread_sync)
        
        for email_data in emails:
            uid = email_data["uid"]
            if uid in self._seen_uids:
                continue
                
            self._seen_uids.add(uid)
            
            sender = email_data["sender"]
            subject = email_data["subject"]
            snippet = email_data["snippet"]
            
            # Combine subject and snippet for evaluation
            content = f"Subject: {subject}\nSnippet: {snippet}"
            
            is_imp = await self.classifier.is_important("Email", sender, content)
            
            if is_imp:
                logger.info("important_email_detected", sender=sender, subject=subject)
                
                # Emit a SYSTEM_NOTIFICATION event so Megan speaks it
                message = f"Sir, you have an important new email from {sender}. The subject is: {subject}."
                await self.event_bus.emit(
                    Event(
                        type=EventType.SYSTEM_NOTIFICATION,
                        data={"message": message},
                        conversation_id=str(uuid.uuid4())
                    )
                )

    def _fetch_unread_sync(self):
        """Synchronously fetch unread emails using IMAP."""
        results = []
        try:
            mail = imaplib.IMAP4_SSL(self.settings.email.imap_server)
            mail.login(self.settings.email.email_address, self.settings.email.app_password)
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                return []

            for num in messages[0].split():
                # Fetch headers and a small portion of the body (RFC822.SIZE or just peek)
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue
                    
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject, encoding = decode_header(msg.get("Subject", ""))[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                            
                        sender = msg.get("From", "")
                        
                        # Get a small snippet
                        snippet = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        snippet = payload.decode(errors="ignore")[:200]
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                snippet = payload.decode(errors="ignore")[:200]
                                
                        results.append({
                            "uid": num.decode(),
                            "sender": sender,
                            "subject": subject,
                            "snippet": snippet.strip()
                        })
            
            mail.logout()
        except Exception as e:
            logger.error("imap_fetch_error", error=str(e))
            
        return results
