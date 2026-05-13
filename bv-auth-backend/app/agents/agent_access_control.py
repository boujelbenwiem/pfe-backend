# backend/app/agents/agent_access_control.py
# Nœud de contrôle d'accès : vérifie si un STORE_MANAGER demande
# des données d'un magasin qui n'est pas le sien.

import re
import logging
from typing import Literal

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)

# Pattern pour détecter un identifiant magasin (ex: BV551, BV015, bv123)
_SHOP_ID_PATTERN = re.compile(r"\b(BV\d{2,4})\b", re.IGNORECASE)


def check_shop_access(state: AgentState) -> AgentState:
    """
    Pour un STORE_MANAGER : vérifie si la question mentionne un magasin
    différent du sien. Si oui → bloque avec un message d'erreur.
    Pour tout autre rôle → passe directement.
    """
    # Ne s'applique qu'aux STORE_MANAGER
    if state["user_role"] != "STORE_MANAGER":
        return {**state, "access_denied": False}

    user_shop = (state.get("user_shop_id") or "").upper()
    if not user_shop:
        return {**state, "access_denied": False}

    question = state["question"]

    # Détection rapide par regex : si un shop_id explicite autre que le sien est mentionné
    mentioned_shops = set(m.upper() for m in _SHOP_ID_PATTERN.findall(question))
    if mentioned_shops:
        other_shops = mentioned_shops - {user_shop}
        if other_shops:
            shops_str = ", ".join(sorted(other_shops))
            return {
                **state,
                "access_denied": True,
                "formatted_response": {
                    "type": "text",
                    "content": (
                        f"Vous n'avez pas accès aux données du magasin {shops_str}. "
                        f"En tant que manager de {user_shop}, vous ne pouvez consulter "
                        f"que les informations de votre propre magasin."
                    ),
                },
            }

    # Si pas de shop_id explicite → analyse LLM pour détecter une demande
    # sur un autre magasin (ex: "le magasin de Lyon", "un autre magasin")
    prompt = (
        f"Question de l'utilisateur (manager du magasin {user_shop}) :\n"
        f"\"{question}\"\n\n"
        "L'utilisateur demande-t-il des informations sur un AUTRE magasin "
        f"que le sien ({user_shop}) ?\n"
        "Réponds UNIQUEMENT par : OUI ou NON"
    )
    try:
        response = _llm.invoke([
            SystemMessage(content=(
                "Tu analyses des questions d'employés Bureau Vallée. "
                "Réponds OUI si la question concerne clairement un autre magasin, NON sinon. "
                "Si la question ne mentionne aucun magasin ou est générale, réponds NON."
            )),
            HumanMessage(content=prompt),
        ])
        answer = response.content.strip().upper()
        if "OUI" in answer:
            return {
                **state,
                "access_denied": True,
                "formatted_response": {
                    "type": "text",
                    "content": (
                        f"Vous n'avez pas accès aux données d'un autre magasin. "
                        f"En tant que manager de {user_shop}, vous ne pouvez consulter "
                        f"que les informations de votre propre magasin."
                    ),
                },
            }
    except Exception as e:
        logger.warning("Access control LLM check failed: %s — allowing access", e)

    return {**state, "access_denied": False}


def route_access(state: AgentState) -> Literal["allowed", "denied"]:
    """Router après check_shop_access."""
    if state.get("access_denied"):
        return "denied"
    return "allowed"
