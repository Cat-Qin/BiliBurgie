"""LLM client factory and abstract base."""
from __future__ import annotations
import abc
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger("BurgerRelay.llm")

PROVIDER_LABELS = {
    "local": "本地 (Ollama)",
    "custom": "自定义 (OpenAI 兼容)",
}
PROVIDER_DEFAULTS: dict[str, list[str]] = {
    "local": [],
    "custom": [],
}


class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def generate(self, text: str) -> str: ...
    @abc.abstractmethod
    async def test(self) -> bool: ...


def create_llm_client(provider: str, model: str, api_base: str, api_key: str = "",
                      temperature: float = 0.1, timeout: float = 5.0,
                      max_tokens: int = 300) -> Optional[LLMClient]:
    """Factory for LLM clients."""
    if provider == "local":
        from .ollama_client import OllamaClient
        return OllamaClient(model, api_base, temperature, timeout, max_tokens)
    if provider == "custom":
        from .openai_client import OpenAIClient
        return OpenAIClient(model, api_base, api_key, temperature, timeout, max_tokens)
    return None


async def fetch_models(provider: str, api_base: str, api_key: str = "") -> list[str]:
    """Fetch available model names from the provider's API."""
    timeout = aiohttp.ClientTimeout(total=8)

    if provider == "local":
        base = api_base.rstrip("/")
        url = f"{base.rsplit('/', 1)[0]}/api/tags"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama returned {resp.status}")
                data = await resp.json()
                models = [m["name"] for m in data.get("models", [])]
                logger.info(f"Local: found {len(models)} models")
                return models

    # custom — OpenAI-compatible
    headers = {
        "User-Agent": "BurgerRelay/1.0",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    base = api_base.rstrip("/")
    url = f"{base}/models"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}")
            data = await resp.json()
            models = [m["id"] for m in data.get("data", [])]
            models.sort()
            logger.info(f"Custom API: found {len(models)} models")
            return models
