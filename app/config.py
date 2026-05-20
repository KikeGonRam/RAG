"""
config.py — Configuración centralizada vía variables de entorno.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    EMBEDDING_MODEL: str | None = None  # Puede ser None para LLM-only

    # LLM
    LLM_TEMPERATURE: float = 0.2
    LLM_CTX_WINDOW: int = 4096

    # ChromaDB
    CHROMA_PATH: str = "/app/data/chroma_db"

    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
