# backend/app/agents/agent_sql.py
# Responsabilité unique : génération SQL à partir de reranked_chunks + retry

import logging
from typing import Literal

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.config import settings
from app.memory.agent_memory import AgentMemory

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.0,  # SQL = déterministe
)

# Helpers

def _build_context(chunks: list, state: AgentState) -> str:
    """Construit le bloc de contexte schéma à injecter dans le prompt.
    Utilise le champ 'text' qui contient types, descriptions et clés primaires.
    """
    parts = []
    for chunk in chunks:
        # 'text' contient le schéma complet : types, descriptions, PK, relations
        if chunk.get("text"):
            parts.append(chunk["text"])
        else:
            # fallback minimal si text absent
            parts.append(
                f"Table: {chunk['table_name']} ({chunk['category']})\n"
                f"Description: {chunk['description']}\n"
                f"Colonnes: {', '.join(chunk.get('columns', []))}"
            )
        parts.append("")  # ligne vide entre tables

    memory_context = AgentMemory().get_memory_context(state)
    if memory_context:
        parts.append(memory_context)
    return "\n".join(parts) 



# Nœuds

def generate_sql(state: AgentState) -> AgentState:
    """Génère la requête SQL à partir de la question + contexte schéma + mémoire."""
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks") or []
    context = _build_context(chunks, state)

    # Contrainte selon le rôle utilisateur
    role_constraint = ""
    if state["user_role"] == "STORE_MANAGER" and state.get("user_shop_id"):
        role_constraint = (
            f"\nIMPORTANT: L'utilisateur est manager du magasin '{state['user_shop_id']}' uniquement. "
            f"Si la table utilisée possède une colonne shop_id (pricing_by_shop, product_delivery_stock, shops, shop_services, shop_opening_hours, shop_delivery_modes, shop_printing_services), "
            f"filtre avec WHERE shop_id = '{state['user_shop_id']}'. "
            f"Ne pas ajouter de filtre shop_id sur les tables qui n'ont pas cette colonne (products, promotions, categories, product_category, etc.)."
        )

    # Contexte d'erreur pour les retries
    error_context = ""
    if state.get("sql_error"):
        error_context = (
            f"\n\nLa tentative précédente a échoué avec l'erreur suivante:\n"
            f"{state['sql_error']}\n"
            f"Corrige la requête en évitant cette erreur."
        )

    system_prompt = (
    "Tu es un expert SQL spécialisé en DuckDB.\n"
    "Génère UNIQUEMENT la requête SQL brute, sans markdown, sans explication, sans ```sql```.\n"
    "La requête doit être valide pour DuckDB.\n"
    "\n"
    "RÈGLES STRICTES À RESPECTER :\n"
    "\n"
    "1. Colonnes BOOLEAN : utilise true/false (pas de guillemets, pas de 'VRAI')\n"
    "2. Pas de préfixe de schéma : utilise 'products', pas 'schema.products'\n"
    "3. Pas de guillemets autour des noms de colonnes ou tables\n"
    "4. Les IDs de magasins sont des chaînes : 'BV551', 'BV015'\n"
    "5. Utiliser Uniquement le nom de la table, pas la catégorie\n"
    "\n"
    "6. LISTES (plusieurs résultats) :\n"
    "   - Utilise TOUJOURS SELECT DISTINCT pour éviter les doublons\n"
    "   - Si le résultat attendu est une liste de produits, JOIN avec products pour avoir les noms et sku\n"
    "   - Si il demandes top de choses ou les plus popilaires sans indiquer le nombre, affiche les 10 premiers résultats avec LIMIT 10\n"
    "\n"
    "7. VALEUR UNIQUE (prix, stock, note) :\n"
    "   - Utilise SELECT DISTINCT UNIQUEMENT la colonne nécessaire\n"
    "   - N'ajoute PAS shop_id si la question ne le demande pas\n"
    "   - Exemple: SELECT selling_price_ttc FROM pricing_by_shop WHERE sku = 1282\n"
    "\n"
    "8. JOIN :\n"
    "   - Ne fais JOIN QUE si les colonnes nécessaires sont dans des tables différentes\n"
    "   - Si toutes les informations sont dans UNE seule table, ne fais pas de JOIN\n"
    "   - Exemple: pour le prix d'un produit, pricing_by_shop suffit (pas besoin de products)\n"
    "   -NE JAMAIS utiliser USING() \n"
    "\n"
    "9. Noms de colonnes :\n"
    "   - Utilise les noms EXACTS des colonnes dans les schémas\n"
    "   - selling_price_ttc = prix TTC, pas 'price' ou 'prix'\n"
    "\n"
    "10. Filtrage par magasin :\n"
    "    - Utilise WHERE shop_id = 'BV551' (pas shop_name)\n"
    "    - La table 'products' n'a PAS de colonne shop_id\n"
    "\n"
    "11. Résultat vide :\n"
    "    - Si aucune ligne ne correspond, la requête est correcte\n"
    "    - Ne pas modifier la requête pour forcer un résultat\n"
)

    user_prompt = (
        f"Schémas des tables disponibles:\n{context}"
        f"{role_constraint}"
        f"{error_context}\n\n"
        f"Question: {state['question']}\n\n"
        f"Requête SQL DuckDB:"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        sql = (
            response.content.strip()
            .removeprefix("```sql")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        return {**state, "sql_query": sql, "sql_error": None}
    except Exception as e:
        logger.error("SQL generation failed: %s", e)
        return {**state, "sql_query": None, "sql_error": f"LLM error: {str(e)}"}


def increment_retry(state: AgentState) -> AgentState:
    """Incrémente le compteur de tentatives avant un retry."""
    return {**state, "retry_count": state["retry_count"] + 1}


# Routing

def should_retry(state: AgentState) -> Literal["retry", "done"]:
    if state.get("sql_error") and state["retry_count"] < MAX_RETRIES:
        return "retry"
    return "done"

