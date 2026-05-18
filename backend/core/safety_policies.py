"""
Safety Policy Engine — rule-based action gating for dangerous operations.

Checks tool inputs against a set of policies before execution.
Actions: BLOCK (refuse entirely), CONFIRM (ask user), ALLOW (proceed).
"""

import re
import structlog
from typing import Any
from enum import Enum

logger = structlog.get_logger(__name__)


class PolicyAction(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"


# Policy rules: checked in order. First match wins.
POLICIES = [
    # Destructive filesystem operations
    {"pattern": r"rm\s+(-rf?|--recursive)\s+/(?!home)", "tools": ["terminal"], "action": PolicyAction.BLOCK, "reason": "Destructive root-level deletion"},
    {"pattern": r"rm\s+(-rf?|--recursive)\s+~/?$", "tools": ["terminal"], "action": PolicyAction.BLOCK, "reason": "Deleting entire home directory"},
    {"pattern": r"mkfs\.", "tools": ["terminal"], "action": PolicyAction.BLOCK, "reason": "Disk formatting"},
    {"pattern": r"dd\s+if=.+of=/dev/", "tools": ["terminal"], "action": PolicyAction.BLOCK, "reason": "Raw disk write"},
    
    # System-level dangerous commands
    {"pattern": r"sudo\s+shutdown", "tools": ["terminal"], "action": PolicyAction.CONFIRM, "reason": "System shutdown"},
    {"pattern": r"sudo\s+reboot", "tools": ["terminal"], "action": PolicyAction.CONFIRM, "reason": "System reboot"},
    {"pattern": r"sudo\s+rm", "tools": ["terminal"], "action": PolicyAction.CONFIRM, "reason": "Privileged file deletion"},
    {"pattern": r"chmod\s+777", "tools": ["terminal"], "action": PolicyAction.CONFIRM, "reason": "Insecure permission change"},
    
    # Database destruction
    {"pattern": r"DROP\s+(TABLE|DATABASE)", "tools": ["terminal", "code_executor"], "action": PolicyAction.BLOCK, "reason": "Database destruction"},
    {"pattern": r"TRUNCATE\s+TABLE", "tools": ["terminal", "code_executor"], "action": PolicyAction.CONFIRM, "reason": "Table truncation"},
    
    # Network / exfiltration
    {"pattern": r"curl.*\|\s*bash", "tools": ["terminal"], "action": PolicyAction.BLOCK, "reason": "Remote code execution via curl pipe"},
    {"pattern": r"wget.*\|\s*sh", "tools": ["terminal"], "action": PolicyAction.BLOCK, "reason": "Remote code execution via wget pipe"},
]


class SafetyPolicyEngine:
    """Checks tool calls against safety policies."""

    @staticmethod
    def check(tool_name: str, params: dict[str, Any]) -> tuple[PolicyAction, str]:
        """
        Check a tool call against all policies.
        
        Returns:
            (PolicyAction, reason) — the action to take and why.
        """
        # Serialize all param values into a single string for pattern matching
        param_str = " ".join(str(v) for v in params.values())

        for policy in POLICIES:
            # Check if this policy applies to this tool
            if tool_name not in policy["tools"]:
                continue

            # Check if the pattern matches
            if re.search(policy["pattern"], param_str, re.IGNORECASE):
                action = policy["action"]
                reason = policy["reason"]
                logger.warning(
                    "safety_policy_triggered",
                    tool=tool_name,
                    action=action.value,
                    reason=reason,
                    pattern=policy["pattern"],
                )
                return action, reason

        return PolicyAction.ALLOW, ""
