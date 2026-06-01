# backend/app/agents/agent_query_rewriter.py
# Query rewriting par synonymes uniquement (déterministe, < 10ms)

import logging
import time
from typing import Tuple
from functools import lru_cache

from app.agents.state import AgentState

logger = logging.getLogger(__name__)

# ============================================================================
# DICTIONNAIRE SYNONYMES (DÉTERMINISTE, < 10MS)
# ============================================================================

SYNONYMS = {
    "stock": ["available_quantity", "origin_quantity", "disponibilité", "inventaire"],
    "prix": ["selling_price_ttc", "selling_price_ht", "tarif", "coût"],
    "produit": ["sku"],
    
}

# ============================================================================
# MATCHING PAR SYNONYMES AVEC SCORE DE CONFIANCE
# ============================================================================

def _calculate_match_confidence(question: str, matched_words: list) -> float:
    """
    Calcule un score de confiance basé sur:
    - Nombre de mots matchés
    - Couverture du vocabulaire
    """
    if not matched_words:
        return 0.0
    
    question_words = set(question.lower().split())
    matched_set = set(matched_words)
    
    # Ratio: mots matchés / total de mots de la question
    coverage = len(matched_set) / max(len(question_words), 1)
    
    # Nombre de mots matchés (bonus si plusieurs matches)
    match_count = len(matched_set)
    match_bonus = min(match_count / 3.0, 1.0)  # Plafond à 1.0
    
    # Score final: moyenne pondérée
    confidence = (coverage * 0.6) + (match_bonus * 0.4)
    return min(confidence, 1.0)


def _rewrite_with_synonyms(question: str) -> Tuple[str, float, list]:
    """
    Enrichit la question avec synonymes (déterministe, <10ms).
    
    Returns:
        (rewritten_question, confidence_score, matched_words)
    """
    start = time.time()
    question_lower = question.lower()
    enriched = question
    matched_words = []
    
    # Cherche des matches de synonymes
    for word, synonyms in SYNONYMS.items():
        if word in question_lower:
            enriched += " " + " ".join(synonyms)
            matched_words.append(word)
    
    elapsed = time.time() - start
    confidence = _calculate_match_confidence(question, matched_words)
    
    logger.debug(f"REWRITE: {elapsed*1000:.2f}ms, confidence={confidence:.2f}, matches={matched_words}")
    
    return enriched, confidence, matched_words


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def rewrite_query(state: AgentState) -> AgentState:
    """
    Enrichit la question avec synonymes du dictionnaire.
    """
    question = state["question"]
    
    start = time.time()
    rewritten, confidence, matched_words = _rewrite_with_synonyms(question)
    elapsed = time.time() - start
    
    logger.info(f"Rewrite: {elapsed*1000:.2f}ms | confidence={confidence:.2f} | matches={matched_words}")
    
    return {
        **state,
        "question": rewritten,
        "original_question": question,
        "rewrite_method": "SYNONYMS",
        "rewrite_confidence": confidence,
    }