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
        self.model = settings.EMBEDDING_MODEL
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    async def embed(self, text: str) -> list[float]:
        """Genera el embedding de un único texto."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text}
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding")

            if not embedding:
                raise ValueError(f"Ollama no retornó embedding para el modelo '{self.model}'.")

            return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Genera embeddings para una lista de textos.
        Ollama no tiene endpoint batch nativo, así que hacemos llamadas secuenciales
        con un cliente compartido para reutilizar la conexión HTTP.
        """
        embeddings = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i, text in enumerate(texts):
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding")

                if not embedding:
                    raise ValueError(
                        f"No se obtuvo embedding para el chunk {i}. "
                        f"¿Está el modelo '{self.model}' descargado en Ollama?"
                    )

                embeddings.append(embedding)

                if (i + 1) % 10 == 0:
                    logger.info(f"  Embeddings generados: {i + 1}/{len(texts)}")

        return embeddings
