# backend/app/rag/reranker.py

import logging
from typing import List, Dict, Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
JINA_RERANK_MODEL = "jina-reranker-v3"
REQUEST_TIMEOUT = 30


class SchemaReranker:
    """Reranke les résultats du retriever avec Jina Reranker v3."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
            "Content-Type": "application/json",
        })

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Reranke les documents par rapport à la query.
        Construit un texte enrichi (table + description + colonnes) pour le reranking.
        """
        if not documents:
            return []

        # Construire un texte enrichi pour chaque document
        texts = []
        for doc in documents:
            enriched = (
                f"Table: {doc.get('table_name', '')}\n"
                f"Catégorie: {doc.get('category', '')}\n"
                f"Description: {doc.get('description', '')}\n"
                f"Colonnes: {', '.join(doc.get('columns', []))}\n"
                f"Relations: {', '.join(doc.get('relations', []))}"
            )
            texts.append(enriched)

        resp = self.session.post(
            JINA_RERANK_URL,
            json={
                "model": JINA_RERANK_MODEL,
                "query": query,
                "documents": texts,
                "top_n": top_n,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # Reconstruire les résultats avec le score de reranking
        reranked = []
        for item in data["results"]:
            idx = item["index"]
            doc = documents[idx].copy()
            doc["rerank_score"] = item["relevance_score"]
            reranked.append(doc)

        return reranked

    def close(self):
        self.session.close()


_reranker: SchemaReranker | None = None


def get_reranker() -> SchemaReranker:
    global _reranker
    if _reranker is None:
        _reranker = SchemaReranker()
    return _reranker
