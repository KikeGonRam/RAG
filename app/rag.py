"""
rag.py — Orquestador del pipeline RAG.
Coordina: chunking → embeddings → vector store → LLM.
"""

import logging
from typing import AsyncGenerator

from app.vectorstore import VectorStore
from app.embeddings import EmbeddingClient
from app.llm import OllamaClient
from app.utils import chunk_text

logger = logging.getLogger(__name__)


def _token_set(text: str) -> set[str]:
    return {tok for tok in text.lower().split() if tok}


class RAGPipeline:
    def __init__(self):
        self.vectorstore = VectorStore()
        self.embedder = EmbeddingClient()
        self.llm = OllamaClient()

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        ollama_ok = await self.llm.is_available()
        chroma_ok = self.vectorstore.is_available()
        return {
            "ollama": ollama_ok,
            "chromadb": chroma_ok,
            "status": "ok" if ollama_ok and chroma_ok else "degraded"
        }

    # ── Ingest ────────────────────────────────────────────────────────────────

    async def ingest(self, texts: list[str], collection: str = "default") -> int:
        """
        Divide los textos en chunks, genera embeddings y los almacena en ChromaDB.
        Retorna el número total de chunks guardados.
        """
        all_chunks: list[str] = []
        for text in texts:
            chunks = chunk_text(text)
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning("No se generaron chunks de los textos recibidos.")
            return 0

        logger.info(f"Generando embeddings para {len(all_chunks)} chunks...")
        embeddings = await self.embedder.embed_batch(all_chunks)

        self.vectorstore.upsert(
            collection=collection,
            texts=all_chunks,
            embeddings=embeddings
        )

        logger.info(f"✅ {len(all_chunks)} chunks almacenados en colección '{collection}'.")
        return len(all_chunks)

    # ── Ask (normal) ──────────────────────────────────────────────────────────

    async def ask(self, question: str, collection: str = "default", top_k: int = 4) -> dict:
        """
        Pipeline RAG completo o solo LLM si no hay embeddings.
        """
        logger.info(f"🔍 Query: {question}")

        # Si no hay modelo de embeddings, responde solo con el LLM
        if not hasattr(self.embedder, 'model') or not self.embedder.model:
            answer = await self.llm.chat(question)
            return {
                "answer": answer,
                "sources": [],
                "context_used": 0,
                "mode": "llm_only",
                "warning": "Embeddings deshabilitados en configuración.",
            }

        # 1. Embedding de la pregunta
        try:
            query_embedding = await self.embedder.embed(question)
        except Exception as exc:
            logger.warning("Embeddings no disponibles, se usa fallback LLM-only: %s", exc)
            answer = await self.llm.chat(question)
            return {
                "answer": answer,
                "sources": [],
                "context_used": 0,
                "mode": "llm_only",
                "warning": "Embeddings no disponibles, respuesta generada sin contexto vectorial.",
            }

        # 2. Búsqueda vectorial en ChromaDB
        results = self.vectorstore.query(
            collection=collection,
            query_embedding=query_embedding,
            top_k=top_k
        )

        if not results["documents"]:
            return {
                "answer": "No encontré información relevante en la base de conocimiento.",
                "sources": [],
                "context_used": 0,
                "mode": "rag",
                "warning": "No hubo contexto relevante para la consulta.",
            }

        context_chunks = self._rerank_documents(
            question=question,
            documents=results.get("documents", []),
            distances=results.get("distances", []),
        )
        context_text = "\n\n---\n\n".join(context_chunks)

        # 3. Prompt augmentation
        prompt = self._build_prompt(context=context_text, question=question)

        # 4. Llamada al LLM
        answer = await self.llm.chat(prompt)

        return {
            "answer": answer,
            "sources": context_chunks,
            "context_used": len(context_chunks),
            "mode": "rag",
            "warning": None,
        }

    # ── Ask (streaming) ───────────────────────────────────────────────────────

    async def ask_stream(
        self, question: str, collection: str = "default", top_k: int = 4
    ) -> AsyncGenerator[str, None]:
        """Versión streaming del pipeline RAG (Server-Sent Events) o solo LLM si no hay embeddings."""

        # Si no hay modelo de embeddings, responde solo con el LLM
        if not hasattr(self.embedder, 'model') or not self.embedder.model:
            async for token in self.llm.chat_stream(question):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            query_embedding = await self.embedder.embed(question)
        except Exception as exc:
            logger.warning("Embeddings no disponibles en streaming, fallback LLM-only: %s", exc)
            async for token in self.llm.chat_stream(question):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
            return
        results = self.vectorstore.query(
            collection=collection,
            query_embedding=query_embedding,
            top_k=top_k
        )

        if not results["documents"]:
            yield "data: No encontré información relevante.\n\n"
            return

        context_text = "\n\n---\n\n".join(results["documents"])
        prompt = self._build_prompt(context=context_text, question=question)

        async for token in self.llm.chat_stream(prompt):
            yield f"data: {token}\n\n"

        yield "data: [DONE]\n\n"

    # ── Prompt Builder ────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(context: str, question: str) -> str:
        return f"""Eres un asistente experto. Usa ÚNICAMENTE el siguiente contexto para responder la pregunta.
Si la respuesta no está en el contexto, di claramente que no tienes esa información.
No inventes datos ni uses conocimiento externo.

CONTEXTO:
{context}

PREGUNTA:
{question}

RESPUESTA:"""

    @staticmethod
    def _rerank_documents(question: str, documents: list[str], distances: list[float]) -> list[str]:
        """Reordena chunks por overlap léxico y luego por similitud vectorial."""
        if not documents:
            return []

        q_tokens = _token_set(question)
        rows = []
        seen: set[str] = set()

        for i, doc in enumerate(documents):
            clean = (doc or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)

            d_tokens = _token_set(clean)
            overlap = len(q_tokens & d_tokens)
            distance = distances[i] if i < len(distances) else 1.0
            rows.append((overlap, distance, clean))

        rows.sort(key=lambda item: (-item[0], item[1]))
        return [doc for _, _, doc in rows]
