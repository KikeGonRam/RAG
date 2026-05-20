"""
llm.py — Cliente para el LLM de Ollama (/api/chat).
Soporta respuesta normal y streaming.
"""

import json
import logging
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = httpx.Timeout(120.0, connect=10.0)

    async def is_available(self) -> bool:
        """Verifica que Ollama esté corriendo y el modelo disponible."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                data = resp.json()
                model_names = [m.get("name", "") for m in data.get("models", [])]
                available = any(self.model in name for name in model_names)
                if not available:
                    logger.warning(
                        f"Modelo '{self.model}' no encontrado. "
                        f"Modelos disponibles: {model_names}"
                    )
                return available
        except Exception as e:
            logger.error(f"Ollama no disponible: {e}")
            return False

    async def chat(self, prompt: str) -> str:
        """Envía un prompt y retorna la respuesta completa como string."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": settings.LLM_TEMPERATURE,
                "num_ctx": settings.LLM_CTX_WINDOW,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(f"Enviando prompt a Ollama (modelo: {self.model})...")
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()

            data = resp.json()
            content = data.get("message", {}).get("content", "")
            logger.info("✅ Respuesta recibida de Ollama.")
            return content

    async def chat_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Envía un prompt y hace yield de tokens conforme llegan (streaming)."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {
                "temperature": settings.LLM_TEMPERATURE,
                "num_ctx": settings.LLM_CTX_WINDOW,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
