"""
Email Tool — read inbox via IMAP + send emails via SMTP.
Supports Gmail with app passwords. Actions auto-execute with timeout protection.
"""

import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import asyncio
import structlog

from tools.base import BaseTool, ToolResult
from config import get_settings

logger = structlog.get_logger(__name__)


class EmailTool(BaseTool):
    """
    Tool for reading and sending emails.
    Read: IMAP (list_unread, read_email)
    Send: SMTP (send_email)
    """

    name = "email"
    description = (
        "Read and send emails. Actions: "
        "'list_unread' — get latest unread emails from inbox. "
        "'read_email' — read full body of a specific email by ID. "
        "'send_email' — compose and send an email. You MUST auto-phrase the body "
        "professionally based on the user's intent. The user will describe what they "
        "want to say and you compose a well-written email body, subject, and send it. "
        "ALWAYS use this tool when the user asks to check, read, or send emails. "
        "Do NOT open a browser."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: 'list_unread', 'read_email', or 'send_email'",
            "enum": ["list_unread", "read_email", "send_email"],
            "required": True,
        },
        "email_id": {
            "type": "string",
            "description": "Email ID to read (required for 'read_email')",
        },
        "limit": {
            "type": "integer",
            "description": "Number of emails to fetch for 'list_unread' (default 5)",
        },
        "to": {
            "type": "string",
            "description": "Recipient email address (required for 'send_email')",
        },
        "subject": {
            "type": "string",
            "description": "Email subject line (required for 'send_email')",
        },
        "body": {
            "type": "string",
            "description": "Email body text — auto-compose professionally from user intent (required for 'send_email')",
        },
    }
    dangerous = False

    def __init__(self):
        settings = get_settings()
        self.imap_server = settings.email.imap_server
        self.smtp_server = settings.email.smtp_server
        self.smtp_port = settings.email.smtp_port
        self.username = settings.email.email_address
        self.password = settings.email.app_password.replace(" ", "")

    def _connect_imap(self):
        if not self.username or not self.password:
            raise ValueError("Email credentials not configured in .env")
        # 15s timeout prevents the thread from hanging indefinitely if network is blocked
        mail = imaplib.IMAP4_SSL(self.imap_server, timeout=15)
        mail.login(self.username, self.password)
        return mail

    def _decode_header(self, header_value):
        if not header_value:
            return "No Subject"
        decoded_bytes, charset = decode_header(header_value)[0]
        if isinstance(decoded_bytes, bytes):
            return decoded_bytes.decode(charset or "utf-8", errors="ignore")
        return decoded_bytes

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")

        try:
            if action == "list_unread":
                return await self._list_unread(kwargs.get("limit", 5))
            elif action == "read_email":
                return await self._read_email(kwargs.get("email_id"))
            elif action == "send_email":
                return await self._send_email(
                    to=kwargs.get("to", ""),
                    subject=kwargs.get("subject", ""),
                    body=kwargs.get("body", ""),
                )
            else:
                return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        except Exception as e:
            logger.error("email_tool_error", error=str(e))
            return ToolResult(success=False, output="", error=str(e))

    async def _list_unread(self, limit: int) -> ToolResult:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._sync_list_unread, limit)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"IMAP search failed: {str(e)}")

    def _sync_list_unread(self, limit: int) -> ToolResult:
        mail = self._connect_imap()
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return ToolResult(success=False, output="", error="Failed to search inbox")

        mail_ids = messages[0].split()
        if not mail_ids:
            return ToolResult(success=True, output="No unread emails found.")

        mail_ids = mail_ids[-limit:]
        results = []

        for i in mail_ids:
            status, msg_data = mail.fetch(i, "(RFC822.SIZE BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if status != "OK":
                continue
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    results.append({
                        "id": i.decode(),
                        "from": self._decode_header(msg.get("From")),
                        "subject": self._decode_header(msg.get("Subject")),
                        "date": msg.get("Date"),
                    })

        mail.logout()
        return ToolResult(success=True, output=json.dumps({"unread_emails": results}))

    async def _read_email(self, email_id: str | None) -> ToolResult:
        if not email_id:
            return ToolResult(success=False, output="", error="email_id is required")
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._sync_read_email, email_id)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"IMAP read failed: {str(e)}")

    def _sync_read_email(self, email_id: str) -> ToolResult:
        mail = self._connect_imap()
        mail.select("inbox")

        status, msg_data = mail.fetch(email_id.encode(), "(RFC822)")
        if status != "OK":
            return ToolResult(success=False, output="", error=f"Failed to fetch email {email_id}")

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = self._decode_header(msg.get("Subject"))
                from_ = self._decode_header(msg.get("From"))

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                            body += part.get_payload(decode=True).decode(errors="ignore")
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                mail.logout()
                return ToolResult(
                    success=True,
                    output=json.dumps({
                        "id": email_id,
                        "from": from_,
                        "subject": subject,
                        "body": body[:2000] + ("..." if len(body) > 2000 else ""),
                    }),
                )

        mail.logout()
        return ToolResult(success=False, output="", error="Email body could not be parsed.")

    async def _send_email(self, to: str, subject: str, body: str) -> ToolResult:
        """Send an email via SMTP (Gmail with app password)."""
        if not to:
            return ToolResult(success=False, output="", error="Recipient 'to' address is required")
        if not subject:
            return ToolResult(success=False, output="", error="Subject is required")
        if not body:
            return ToolResult(success=False, output="", error="Body is required")
        if not self.username or not self.password:
            return ToolResult(success=False, output="", error="Email credentials not configured")

        # Build MIME message
        msg = MIMEMultipart()
        msg["From"] = self.username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Send via SMTP in thread pool
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._smtp_send, msg)
            logger.info("email_sent", to=to, subject=subject)
            return ToolResult(
                success=True,
                output=f"Email sent successfully to {to} with subject '{subject}'",
            )
        except Exception as e:
            logger.error("email_send_error", error=str(e))
            return ToolResult(success=False, output="", error=f"Failed to send email via SMTP: {str(e)}")

    def _smtp_send(self, msg: MIMEMultipart) -> None:
        """Synchronous SMTP send (runs in thread pool)."""
        with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
