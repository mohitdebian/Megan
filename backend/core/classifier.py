"""
Priority Classifier — lightweight LLM wrapper to evaluate message importance.
"""

import httpx
import structlog
from config import get_settings

logger = structlog.get_logger(__name__)


class PriorityClassifier:
    def __init__(self):
        self.settings = get_settings()

    async def is_important(self, source: str, sender: str, content: str) -> bool:
        """
        Evaluate if a message/email is important enough to announce.
        Returns True if score >= 7, else False.
        """
        try:
            prompt = (
                f"You are an AI assistant filtering incoming notifications for the user.\n"
                f"Evaluate the following {source} message for urgency and importance.\n"
                f"Sender: {sender}\n"
                f"Content: {content}\n\n"
                f"Rate the importance from 1 to 10. Consider emails from family members, "
                f"work urgency, financial alerts, or direct questions as high priority (>=7).\n"
                f"Spam, newsletters, casual chatter, or promotions should be low priority.\n"
                f"Respond ONLY with a single number between 1 and 10. Do not output any other text."
            )

            headers = {
                "Authorization": f"Bearer {self.settings.claude.auth_token}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            payload = {
                "model": self.settings.claude.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }

            url = f"{self.settings.claude.base_url}/v1/messages"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    logger.warning("classifier_api_failed", status=resp.status_code)
                    return False
                
                data = resp.json()
                content_blocks = data.get("content", [])
                
                # Extract response text
                response_text = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        response_text += block.get("text", "")
                
                # Parse number
                score_str = "".join(filter(str.isdigit, response_text))
                if score_str:
                    score = int(score_str)
                    logger.info("classification_result", source=source, sender=sender, score=score)
                    return score >= 7
                
            return False

        except Exception as e:
            logger.error("classifier_error", error=str(e))
            return False
