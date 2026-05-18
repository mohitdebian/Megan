"""
SEAL Learning Engine Stub — Self-Adapting Language Models logic.

Extracts corrective feedback from user interactions and stores them
as generalized rules/preferences in long-term memory.
"""

import asyncio
import structlog
from typing import Any

from config import Settings
from memory.long_term import LongTermMemory

logger = structlog.get_logger(__name__)


class SealEngine:
    """
    Self-Adapting Language Model engine stub.
    Analyzes conversations asynchronously to extract self-edits and rules.
    """

    def __init__(self, settings: Settings, long_term: LongTermMemory) -> None:
        self.settings = settings
        self.long_term = long_term

    async def process_feedback(self, user_input: str, response: str, context_id: str) -> None:
        """
        Asynchronously check if user_input contains corrective feedback.
        If so, extract a rule and save it to preferences.
        """
        # Run in background to avoid blocking the main conversation loop
        asyncio.create_task(self._extract_and_store(user_input, response, context_id))

    async def _extract_and_store(self, user_input: str, response: str, context_id: str) -> None:
        """
        MIT SEAL Self-Evaluator Node.
        Asynchronously uses the LLM to analyze the interaction and extract a generalized rule
        if a correction or behavioral instruction is detected.
        """
        try:
            import httpx
            import uuid
            
            system_prompt = (
                "You are the SEAL continuous learning evaluator. "
                "Analyze the user's input. Did the user issue a correction, a behavioral instruction, or a preference? "
                "If YES, formulate a short, generalized rule for the agent to follow in the future. "
                "If NO, return exactly the word 'NONE'. "
                "Output ONLY the rule or 'NONE'. "
                "Example 1: 'always call me Commander' -> 'Rule: Always address the user as Commander.' "
                "Example 2: 'what is the weather' -> 'NONE'"
            )
            
            headers = {
                "Authorization": f"Bearer {self.settings.claude.auth_token}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            
            payload = {
                "model": self.settings.claude.model,
                "max_tokens": 150,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_input}],
            }
            
            base_url = self.settings.claude.base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{base_url}/v1/messages", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = ""
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            content += block.get("text", "")
                    
                    rule = content.strip()
                    if rule and "NONE" not in rule.upper() and len(rule) > 5:
                        logger.info("seal_correction_detected", context_id=context_id, user_input=user_input, rule=rule)
                        
                        rule_key = f"seal_rule_{str(uuid.uuid4())[:8]}"
                        
                        # Save the new rule/preference in Long-Term Memory
                        await self.long_term.set_preference(rule_key, rule)
                        logger.info("seal_rule_stored", rule_key=rule_key)
        except Exception as e:
            logger.error("seal_engine_error", error=str(e))
