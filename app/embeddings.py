"""
embeddings.py — Cliente para generar embeddings con Ollama (/api/embeddings).
Modelo: nomic-embed-text
"""

import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        raw_model = getattr(settings, 'EMBEDDING_MODEL', None)
        self.model = raw_model.strip() if raw_model else None
        self.timeout = httpx.Timeout(60.0, connect=10.0)
        if not self.model:
            logger.warning('No EMBEDDING_MODEL configurado o está vacío. El pipeline funcionará solo con LLM.')

    async def _embed_single(self, client: httpx.AsyncClient, text: str) -> list[float]:
        """Compatibilidad con versiones de Ollama que usan /api/embeddings o /api/embed."""
        payload = {"model": self.model, "prompt": text}
        resp = await client.post(f"{self.base_url}/api/embeddings", json=payload)

        if resp.status_code == 404:
            # Fallback para instalaciones donde /api/embeddings no existe.
            resp = await client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": text})

        resp.raise_for_status()
        data = resp.json()

        embedding = data.get("embedding")
        if embedding:
            return embedding

        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            first = embeddings[0]
            if isinstance(first, list) and first:
                return first

        raise ValueError(f"Ollama no retornó embedding para el modelo '{self.model}'.")

    async def embed(self, text: str) -> list[float]:
        """Genera el embedding de un único texto."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._embed_single(client, text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Genera embeddings para una lista de textos.
        Ollama no tiene endpoint batch nativo, así que hacemos llamadas secuenciales
        con un cliente compartido para reutilizar la conexión HTTP.
        """
        embeddings = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i, text in enumerate(texts):
                embedding = await self._embed_single(client, text)

                embeddings.append(embedding)

                if (i + 1) % 10 == 0:
                    logger.info(f"  Embeddings generados: {i + 1}/{len(texts)}")

        return embeddings
