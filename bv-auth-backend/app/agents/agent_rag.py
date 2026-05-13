import logging

from app.agents.state import AgentState
from app.rag.retriever import get_retriever
from app.rag.reranker import get_reranker

logger = logging.getLogger(__name__)



def retrieve_chunks(state: AgentState) -> AgentState:
    """Récupère les top chunks depuis Qdrant (recherche vectorielle)."""
    try:
        chunks = get_retriever().retrieve(state["question"], limit=10)
        return {**state, "retrieved_chunks": chunks, "error": None}
    except Exception as e:
        logger.error("Retrieval failed: %s", e)
        return {**state, "retrieved_chunks": [], "error": f"Retrieval failed: {str(e)}"}


def rerank_chunks(state: AgentState) -> AgentState:
    """Reranke les chunks avec Jina Reranker v3. Fallback sur raw si erreur."""
    retrieved = state.get("retrieved_chunks") or []
    if not retrieved:
        return {**state, "reranked_chunks": []}

    try:
        reranked = get_reranker().rerank(state["question"], retrieved, top_n=3)
        return {**state, "reranked_chunks": reranked, "error": None}
    except Exception as e:
        logger.warning("Reranking failed, falling back to raw retrieval: %s", e)
        return {**state, "reranked_chunks": retrieved[:5], "error": None}


