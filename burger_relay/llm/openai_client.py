"""LLM client: OpenAI-compatible API backend."""
from __future__ import annotations
import json
import logging
import aiohttp
from .llm_factory import LLMClient

logger = logging.getLogger("BurgerRelay.llm.openai")

class OpenAIClient(LLMClient):
    def __init__(self, model: str, api_base: str, api_key: str = "",
                 temperature: float = 0.1, timeout: float = 5.0,
                 max_tokens: int = 300) -> None:
        self._model = model
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def generate(self, text: str) -> str:
        from ..utils.prompts import get_system_prompt
        system = get_system_prompt()

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        if not self._api_base.endswith("/chat/completions"):
            url = f"{self._api_base}/chat/completions"
        else:
            url = self._api_base

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"弹幕: {text}\n请返回JSON:"},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"API returned {resp.status}")
                data = await resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                logger.debug("LLM raw response: %s", raw[:300])
        result = self._extract_json(raw)
        if not result or result == "{}":
            logger.warning("LLM returned empty/unparseable: %s", raw[:300])
        return result

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start:end + 1]
        # No JSON found — return the raw text as a fallback so the caller
        # can see what the model actually returned.
        logger.debug("No JSON braces in LLM response, returning raw: %s", text[:200])
        return text

    async def test(self) -> bool:
        try:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            url = f"{self._api_base}/models"
            if not self._api_base.endswith("/chat/completions"):
                url = f"{self._api_base}/models"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
                async with s.get(url, headers=headers) as r:
                    return r.status == 200
        except Exception:
            return False
