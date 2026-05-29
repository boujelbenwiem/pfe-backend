# backend/app/agents/agent_query_rewriter.py
# Pre-retrieval : réécriture et expansion de la question utilisateur
# pour améliorer la qualité du retrieval vectoriel (schéma de tables).

import logging

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)

SYSTEM_PROMPT = """\
Tu es un assistant spécialisé dans la réécriture de requêtes utilisateur pour \
améliorer la recherche dans une base de connaissances contenant des schémas de \
tables d'une base de données e-commerce .

Ton objectif : transformer la question brute de l'utilisateur en une version \
enrichie qui maximise les chances de retrouver les bonnes tables et colonnes \
dans un index vectoriel.

RÈGLES :
1. Garde le SENS EXACT de la question — ne change pas l'intention.
3. Corrige les fautes d'orthographe et de grammaire.
4. Si la question mentionne un concept vague, précise-le \
5. Traduis les abréviations courantes (CA → chiffre d'affaires, promo → promotion).
6. Retourne UNIQUEMENT la question réécrite, rien d'autre.
7. Reste en français.
"""


def rewrite_query(state: AgentState) -> AgentState:
    """Réécrit/expand la question utilisateur avant le retrieval vectoriel."""
    question = state["question"]

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Question originale : {question}"),
        ])
        rewritten = response.content.strip()
        if not rewritten:
            rewritten = question

        logger.info("Query rewritten: '%s' → '%s'", question, rewritten)
        return {**state, "question": rewritten, "original_question": question}
    except Exception as e:
        logger.warning("Query rewriting failed, using original: %s", e)
        return {**state, "original_question": question}
