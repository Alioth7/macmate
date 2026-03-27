"""
Shell command executor with three-tier security model.

Security Modes:
  - strict:          Every command requires user confirmation.
  - agent (default): Only dangerous commands require confirmation;
                     safe ones execute directly.
  - self_supervised: An auxiliary LLM session rates each command
                     (safe / suspicious / dangerous) before execution.
"""

import json
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from core.tools import registry


# ---------------------------------------------------------------------------
# Dangerous-pattern blacklist
# ---------------------------------------------------------------------------
_DANGER_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+.*-\s*[^\s]*r[^\s]*f", re.IGNORECASE),   # rm -rf
    re.compile(r"\brm\s+(-\S+\s+)*/\s*$"),                        # rm /
    re.compile(r"\bsudo\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\b:\(\)\s*\{\s*:\|:\s*&\s*\}\s*;"),              # fork bomb
    re.compile(r">\s*/dev/sd[a-z]"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bhalt\b"),
    re.compile(r"\bchmod\s+.*777\s+/"),                            # chmod 777 /
    re.compile(r"\blaunchctl\s+(unload|remove)"),
    re.compile(r"\bnohup\b.*&"),                                   # stealth daemon
]


def _is_dangerous(cmd: str) -> bool:
    """Return True when *cmd* matches any known dangerous pattern."""
    for pat in _DANGER_PATTERNS:
        if pat.search(cmd):
            return True
    return False


def _classify_danger_level(cmd: str) -> str:
    """Quick local heuristic: 'safe', 'suspicious', or 'dangerous'."""
    if _is_dangerous(cmd):
        return "dangerous"
    # Mildly suspicious patterns
    suspicious = [
        r"\bchmod\b", r"\bchown\b", r"\bkill\b", r"\bpkill\b",
        r"\bkillall\b", r"\brm\b", r"\bmv\s+/", r"\bcurl\b.*\|\s*(ba)?sh",
        r"\bwget\b.*\|\s*(ba)?sh",
    ]
    for pat in suspicious:
        if re.search(pat, cmd, re.IGNORECASE):
            return "suspicious"
    return "safe"


class ShellExecutor:
    """Execute shell commands on behalf of the user with safety guardrails."""

    MODES = ("strict", "agent", "self_supervised")

    def __init__(
        self,
        mode: str = "agent",
        timeout: int = 15,
        max_output: int = 4000,
        llm_safety_checker=None,
    ):
        """
        Args:
            mode:  One of 'strict', 'agent', 'self_supervised'.
            timeout: Max seconds a command is allowed to run.
            max_output: Characters of stdout/stderr returned.
            llm_safety_checker: A callable(cmd:str)->str that returns a
                                safety rating string. Used only when
                                mode == 'self_supervised'.
        """
        if mode not in self.MODES:
            mode = "agent"
        self._mode = mode
        self._timeout = timeout
        self._max_output = max_output
        self._llm_safety_checker = llm_safety_checker

        registry.bind_instance(self)

    # ------------------------------------------------------------------
    # Registered tools
    # ------------------------------------------------------------------
    @registry.register(
        "run_shell_command",
        "Execute a shell command on macOS. Args: command(str). "
        "Returns stdout/stderr or a safety-rejection message. "
        "Dangerous commands may be blocked or require confirmation.",
    )
    def run_shell_command_tool(self, command: str) -> str:
        command = (command or "").strip()
        if not command:
            return "Error: empty command."

        # --- Security gate ---
        level = _classify_danger_level(command)

        if self._mode == "strict":
            # In strict mode every command is flagged for user review.
            return self._format_confirmation_request(command, level)

        if self._mode == "self_supervised" and self._llm_safety_checker:
            try:
                llm_rating = self._llm_safety_checker(command)
            except Exception as exc:
                llm_rating = f"error ({exc})"
            level = self._merge_ratings(level, llm_rating)

        if level == "dangerous":
            return (
                f"🚨 BLOCKED — command classified as **dangerous**.\n"
                f"Command: `{command}`\n"
                f"If you really need to run this, ask the user to execute it manually."
            )

        if level == "suspicious":
            if self._mode in ("agent", "self_supervised"):
                return self._format_confirmation_request(command, level)

        # --- Execute ---
        return self._execute(command)

    @registry.register(
        "run_shell_command_confirmed",
        "Execute a previously-flagged shell command after user confirmation. "
        "Args: command(str). Skips safety gate. Use ONLY after ANSWER confirmation.",
    )
    def run_shell_command_confirmed_tool(self, command: str) -> str:
        command = (command or "").strip()
        if not command:
            return "Error: empty command."
        if _classify_danger_level(command) == "dangerous":
            return "🚨 BLOCKED — this command is in the absolute blacklist and cannot run."
        return self._execute(command)

    @registry.register(
        "get_shell_security_mode",
        "Get current shell security mode. No args. Returns mode name.",
    )
    def get_shell_security_mode_tool(self) -> str:
        return json.dumps({"mode": self._mode}, ensure_ascii=False)

    @registry.register(
        "set_shell_security_mode",
        "Change shell security mode. Args: mode(str 'strict'|'agent'|'self_supervised').",
    )
    def set_shell_security_mode_tool(self, mode: str) -> str:
        mode = (mode or "").strip().lower()
        if mode not in self.MODES:
            return f"Error: unknown mode '{mode}'. Valid: {', '.join(self.MODES)}"
        self._mode = mode
        return f"Shell security mode set to: {self._mode}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _execute(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=os.path.expanduser("~"),
            )
            out = (result.stdout or "") + (result.stderr or "")
            out = out.strip()
            if len(out) > self._max_output:
                out = out[: self._max_output] + "\n... (output truncated)"
            if not out:
                out = "(no output)"
            return f"Exit code: {result.returncode}\n{out}"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {self._timeout}s."
        except Exception as exc:
            return f"Error executing command: {exc}"

    def _format_confirmation_request(self, command: str, level: str) -> str:
        emoji = "⚠️" if level == "suspicious" else "🔒"
        return (
            f"{emoji} **Command needs user confirmation** (level: {level}, mode: {self._mode})\n"
            f"```\n{command}\n```\n"
            f"Please use ANSWER to ask the user whether to proceed. "
            f"If confirmed, call `run_shell_command_confirmed(command=\"{command}\")`."
        )

    @staticmethod
    def _merge_ratings(local_level: str, llm_rating: str) -> str:
        """Combine local heuristic with LLM rating (take the stricter one)."""
        order = {"safe": 0, "suspicious": 1, "dangerous": 2}
        llm_clean = "safe"
        for key in order:
            if key in (llm_rating or "").lower():
                llm_clean = key
                break
        local_rank = order.get(local_level, 0)
        llm_rank = order.get(llm_clean, 0)
        merged_rank = max(local_rank, llm_rank)
        for k, v in order.items():
            if v == merged_rank:
                return k
        return "suspicious"
