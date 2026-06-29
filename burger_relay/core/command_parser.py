"""Command parsing engine: hard-match first, LLM fallback."""
from __future__ import annotations
import json
import logging
import time
from typing import Optional
from ..utils.models import CommandResult, CommandType
from .command_mappings import get_hard_match_command
from ..llm.llm_factory import LLMClient
from ..auth.gift_whitelist import GiftWhitelist

logger = logging.getLogger("BurgerRelay.parser")

class CommandParser:
    """Parses danmaku text into game commands."""

    def __init__(self, whitelist: GiftWhitelist, llm_client: Optional[LLMClient] = None) -> None:
        self._whitelist = whitelist
        self._llm = llm_client

    def set_llm(self, client: Optional[LLMClient]) -> None:
        self._llm = client

    async def parse(self, text: str, user_name: str, require_gift: bool = True) -> CommandResult:
        """Parse danmaku text.

        - Starts with '!' → LLM only (no hard-match)
        - Otherwise → hard-match only (no LLM fallback)
        """
        if not text or not text.strip():
            return CommandResult(CommandType.IGNORE, "", "none", raw_input=text)

        t = text.strip()

        # --- ! prefix → LLM only ---
        if t.startswith("!"):
            if self._llm is None:
                return CommandResult(CommandType.IGNORE, "", "none", raw_input=text)
            if require_gift and not self._whitelist.is_whitelisted(user_name):
                logger.info(f"LLM blocked (no gift): [{user_name}] '{t}'")
                return CommandResult(
                    CommandType.IGNORE, "", "llm",
                    raw_input=text, error="User not in gift whitelist",
                )
            logger.info(f"LLM: [{user_name}] '{t}'")
            return await self._llm_parse(t)

        # --- No ! → hard-match only ---
        hard = get_hard_match_command(t)
        if hard:
            ct = self._classify_command(hard)
            logger.info(f"Hard-match: [{user_name}] '{t}' -> '{hard}'")
            return CommandResult(ct, hard, "hard_match", raw_input=text)

        return CommandResult(CommandType.IGNORE, "", "none", raw_input=text)

    async def _llm_parse(self, text: str) -> CommandResult:
        start = time.time()
        try:
            raw = await self._llm.generate(text)
            elapsed = (time.time() - start) * 1000
            result = json.loads(raw)
            ct_str = result.get("type", "ignore")
            cmd = result.get("command", "")
            ct = CommandType(ct_str) if ct_str in {e.value for e in CommandType} else CommandType.IGNORE
            logger.info(f"LLM parse ({elapsed:.0f}ms): '{text}' -> type={ct.value} cmd='{cmd}'")
            return CommandResult(ct, cmd, "llm", raw_input=text)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.warning(f"LLM parse failed ({elapsed:.0f}ms): '{text}' - {e}")
            return CommandResult(
                CommandType.IGNORE, "", "llm",
                raw_input=text, error=str(e)
            )

    @staticmethod
    def _classify_command(cmd: str) -> CommandType:
        c = cmd.lower()
        if c.startswith("!burgie"):
            return CommandType.ORDER
        if any(c.startswith(x) for x in ("!dirty", "!fire", "!noise", "!fence", "!window", "!door")):
            return CommandType.COMPLAINT
        if any(c.startswith(x) for x in ("!bell", "!leave", "!go", "!skin")):
            return CommandType.INTERACT
        return CommandType.IGNORE
