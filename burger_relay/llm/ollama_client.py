"""LLM client: Ollama backend."""
from __future__ import annotations
import json
import logging
import aiohttp
from .llm_factory import LLMClient

logger = logging.getLogger("BurgerRelay.llm.ollama")

class OllamaClient(LLMClient):
    def __init__(self, model: str, api_base: str = "http://localhost:11434/api/generate",
                 temperature: float = 0.1, timeout: float = 5.0,
                 max_tokens: int = 300) -> None:
        self._model = model
        self._api_base = api_base
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def generate(self, text: str) -> str:
        from ..utils.prompts import get_system_prompt
        system = get_system_prompt()
        prompt = f"{system}\n\n弹幕内容: {text}\n请返回JSON:"

        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self._temperature, "num_predict": self._max_tokens},
        }
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(self._api_base, json=payload) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama returned {resp.status}")
                data = await resp.json()
                raw = data.get("response", "").strip()
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start:end + 1]
        logger.debug("No JSON braces in LLM response, returning raw: %s", text[:200])
        return text

    async def test(self) -> bool:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
                async with s.get(f"{self._api_base.rsplit('/', 1)[0]}/api/tags") as r:
                    return r.status == 200
        except Exception:
            return False
