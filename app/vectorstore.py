"""
vectorstore.py — Wrapper sobre ChromaDB para persistencia local de vectores.
"""

import uuid
import logging
import chromadb
from chromadb.config import Settings

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        logger.info(f"✅ ChromaDB inicializado en: {settings.CHROMA_PATH}")

    def is_available(self) -> bool:
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False

    def _get_or_create_collection(self, name: str):
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def upsert(self, collection: str, texts: list[str], embeddings: list[list[float]]):
        """Inserta o actualiza chunks con sus embeddings en ChromaDB."""
        col = self._get_or_create_collection(collection)
        ids = [str(uuid.uuid4()) for _ in texts]

        col.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings
        )
        logger.info(f"Upserted {len(texts)} docs en colección '{collection}'.")

    def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 4
    ) -> dict:
        """Busca los top_k documentos más similares al embedding dado."""
        try:
            col = self._get_or_create_collection(collection)
            count = col.count()

            if count == 0:
                logger.warning(f"Colección '{collection}' está vacía.")
                return {"documents": [], "distances": []}

            actual_k = min(top_k, count)
            results = col.query(
                query_embeddings=[query_embedding],
                n_results=actual_k,
                include=["documents", "distances"]
            )

            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            # Filtrar resultados poco relevantes (distancia coseno > 0.5 = poca similitud)
            filtered = [
                (doc, dist)
                for doc, dist in zip(docs, distances)
                if dist < 0.5
            ]

            if not filtered and docs:
                # Si nada pasa el umbral, devolver al menos el mejor resultado
                filtered = [(docs[0], distances[0])]

            final_docs = [doc for doc, _ in filtered]
            final_dists = [dist for _, dist in filtered]

            logger.info(f"Encontrados {len(final_docs)} chunks relevantes (de {count} totales).")
            return {"documents": final_docs, "distances": final_dists}

        except Exception as e:
            logger.error(f"Error al consultar ChromaDB: {e}")
            return {"documents": [], "distances": []}

    def delete_collection(self, name: str):
        """Elimina una colección completa."""
        self.client.delete_collection(name)
        logger.info(f"Colección '{name}' eliminada.")

    def list_collections(self) -> list[str]:
        """Lista todas las colecciones disponibles."""
        return [col.name for col in self.client.list_collections()]
