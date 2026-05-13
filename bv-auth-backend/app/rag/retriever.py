# backend/app/rag/retriever.py

import logging
import threading
from pathlib import Path
from typing import List, Dict, Any

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration
JINA_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v5-text-small"
COLLECTION_NAME = "table_schemas"
REQUEST_TIMEOUT = 30  # secondes

QDRANT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "qdrant_data"


class SchemaRetriever:
    """Récupère les schémas de tables pertinents depuis Qdrant."""

    def __init__(self):
        self.client = QdrantClient(path=str(QDRANT_PATH))
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
            "Content-Type": "application/json",
        })

    def _get_embedding(self, text: str) -> List[float]:
        """Appelle Jina API pour obtenir l'embedding de la question."""
        resp = self.session.post(
            JINA_URL,
            json={"model": JINA_MODEL, "input": [text], "normalized": True},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    def retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Récupère les chunks les plus pertinents pour une question donnée."""
        query_vector = self._get_embedding(query)

        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        return [
            {
                "score": r.score,
                "table_name": r.payload.get("table_name"),
                "category": r.payload.get("category"),
                "description": r.payload.get("description"),
                "columns": r.payload.get("columns", []),
                "relations": r.payload.get("relations", []),
                "text": r.payload.get("text", ""),
            }
            for r in response.points
        ]

    def retrieve_by_table(self, table_name: str, limit: int = 3) -> List[Dict]:
        """Récupère les chunks d'une table spécifique via scroll (sans vecteur)."""
        records, _ = self.client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="table_name", match=MatchValue(value=table_name))]
            ),
            limit=limit,
            with_payload=True,
        )
        return [{"text": r.payload.get("text", "")} for r in records]

    def close(self):
        self.session.close()
        self.client.close()


# Singleton thread-safe
_retriever: SchemaRetriever | None = None
_lock = threading.Lock()


def get_retriever() -> SchemaRetriever:
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                _retriever = SchemaRetriever()
    return _retriever