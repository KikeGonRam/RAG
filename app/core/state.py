from pathlib import Path

from app.api_key_store import ApiKeyStore
from app.chat_store import ChatStore
from app.rag import RAGPipeline

rag = RAGPipeline()
chat_store = ChatStore()
api_key_store = ApiKeyStore()

UI_PATH = Path(__file__).resolve().parents[1] / "static" / "index.html"
ADMIN_UI_PATH = Path(__file__).resolve().parents[1] / "static" / "admin.html"
