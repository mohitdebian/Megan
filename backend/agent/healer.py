"""
Healer Agent — Autonomous code debugger and patcher.

A lightweight LangGraph-less agent that reads a crashed script,
sends the traceback + source to the LLM, receives a patch,
applies it, and re-runs the script to verify the fix.
"""

import asyncio
import httpx
import json
import structlog
from pathlib import Path

from config import get_settings

logger = structlog.get_logger(__name__)


class HealerAgent:
    """
    Given a file path and a traceback, this agent:
    1. Reads the source file.
    2. Sends source + traceback to the LLM with instructions to fix the bug.
    3. Writes the patched file back.
    4. Re-runs the script to verify.
    5. Returns a summary of what was fixed.
    """

    def __init__(self):
        self.settings = get_settings()

    async def heal(self, file_path: str, traceback: str) -> dict:
        """
        Attempt to heal a crashed script.
        
        Returns:
            dict with keys: success, summary, original_error
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "summary": f"File not found: {file_path}", "original_error": traceback}

        original_source = path.read_text()

        # Step 1: Ask the LLM to fix the code
        patched_source = await self._get_patch(original_source, traceback, file_path)

        if not patched_source or patched_source.strip() == original_source.strip():
            return {
                "success": False,
                "summary": "LLM could not generate a different patch.",
                "original_error": traceback
            }

        # Step 2: Write the patched file
        # Keep a backup
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(original_source)

        path.write_text(patched_source)
        logger.info("healer_patch_applied", file=file_path)

        # Step 3: Re-run to verify
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(path.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 0:
                # Success! Remove backup
                backup_path.unlink(missing_ok=True)
                summary = f"Fixed {path.name}. The script now runs successfully."
                logger.info("healer_verified", file=file_path)
                return {"success": True, "summary": summary, "original_error": traceback}
            else:
                # Patch didn't work, rollback
                path.write_text(original_source)
                backup_path.unlink(missing_ok=True)
                new_error = stderr.decode(errors="ignore")[:500]
                logger.warning("healer_patch_failed", file=file_path, new_error=new_error)
                return {
                    "success": False,
                    "summary": f"Patch introduced a new error. Rolled back to original. New error: {new_error}",
                    "original_error": traceback
                }
        except asyncio.TimeoutError:
            # Script hung, rollback
            path.write_text(original_source)
            backup_path.unlink(missing_ok=True)
            return {
                "success": False,
                "summary": "Patched script timed out (30s). Rolled back to original.",
                "original_error": traceback
            }

    async def _get_patch(self, source: str, traceback: str, filename: str) -> str | None:
        """Send the source + traceback to the LLM and get a patched version."""
        prompt = (
            f"You are an expert Python debugger. A script has crashed with the following traceback:\n\n"
            f"```\n{traceback}\n```\n\n"
            f"Here is the full source code of `{filename}`:\n\n"
            f"```python\n{source}\n```\n\n"
            f"Fix the bug. Return ONLY the complete, corrected Python source code. "
            f"Do NOT include markdown fences, explanations, or anything else — just the raw Python code. "
            f"Preserve all existing comments and structure."
        )

        headers = {
            "Authorization": f"Bearer {self.settings.claude.auth_token}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.settings.claude.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        url = f"{self.settings.claude.base_url.rstrip('/')}/v1/messages"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    logger.error("healer_llm_error", status=resp.status_code)
                    return None

                data = resp.json()
                content_blocks = data.get("content", [])

                response_text = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        response_text += block.get("text", "")

                # Strip markdown code fences if the LLM included them anyway
                cleaned = response_text.strip()
                if cleaned.startswith("```python"):
                    cleaned = cleaned[len("```python"):].strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

                return cleaned if cleaned else None

        except Exception as e:
            logger.error("healer_llm_exception", error=str(e))
            return None
