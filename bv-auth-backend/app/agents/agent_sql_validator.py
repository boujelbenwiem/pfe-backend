# backend/app/agents/agent_sql_validator.py
# Agent de validation et correction SQL.
# Intervient après un échec d'exécution MCP (execution_error != None).
# Stratégies :
#   1. "fix_sql"     — Corriger la requête SQL directement (typo, syntaxe, logique)
#   2. "inspect_schema" — Interroger le schéma DB via MCP pour vérifier colonnes/tables
#   3. "re_retrieve" — Relancer le retrieval complet (la question était mal comprise)

import logging
from typing import Literal

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.config import settings
from app.MCP.server import execute_query, MCPRequest

logger = logging.getLogger(__name__)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.0,
)

# ---------------------------------------------------------------------------
# Schema introspection via MCP (DuckDB information_schema)
# ---------------------------------------------------------------------------

def _inspect_tables() -> str:
    """Liste toutes les tables disponibles dans le warehouse."""
    req = MCPRequest(
        sql="SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name",
        user_role="ADMIN",
    )
    resp = execute_query(req)
    if resp.success:
        return "\n".join(row[0] for row in resp.rows)
    return f"[Erreur introspection tables: {resp.error}]"


def _inspect_columns(table_name: str) -> str:
    """Liste les colonnes d'une table spécifique."""
    # Sanitize table name to prevent injection
    safe_name = table_name.strip().replace("'", "''")
    req = MCPRequest(
        sql=f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{safe_name}' ORDER BY ordinal_position",
        user_role="ADMIN",
    )
    resp = execute_query(req)
    if resp.success:
        return "\n".join(f"  {row[0]} ({row[1]})" for row in resp.rows)
    return f"[Erreur introspection colonnes: {resp.error}]"


# ---------------------------------------------------------------------------
# Decision: what strategy to use
# ---------------------------------------------------------------------------

DECISION_PROMPT = """\
Tu es un expert en débogage SQL pour DuckDB.

On te donne :
- La question de l'utilisateur
- La requête SQL générée
- L'erreur d'exécution
- Le contexte schéma utilisé (chunks RAG)

Analyse l'erreur et choisis UNE stratégie de correction :

1. **fix_sql** — L'erreur est une typo, mauvaise syntaxe, mauvais nom de colonne, \
   mauvaise logique SQL. Tu peux corriger sans plus d'info.
2. **inspect_schema** — L'erreur suggère qu'un nom de table ou colonne est incorrect \
   mais tu n'es pas sûr du bon nom. Il faut interroger le schéma réel de la DB.
3. **re_retrieve** — Le contexte RAG semble complètement inadapté à la question. \
   Les tables récupérées ne correspondent pas à ce que l'utilisateur demande. \
   Il faut refaire le retrieval avec une meilleure formulation.

Réponds UNIQUEMENT avec un mot : fix_sql, inspect_schema, ou re_retrieve
"""


def _decide_strategy(state: AgentState) -> Literal["fix_sql", "inspect_schema", "re_retrieve"]:
    """LLM décide de la stratégie de correction."""
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks") or []
    context_summary = "\n".join(
        chunk.get("text", f"Table: {chunk.get('table_name', '?')}")[:200]
        for chunk in chunks[:3]
    )

    user_msg = (
        f"Question: {state['question']}\n\n"
        f"SQL généré: {state.get('sql_query', 'N/A')}\n\n"
        f"Erreur: {state.get('execution_error') or state.get('sql_error', 'N/A')}\n\n"
        f"Contexte schéma (top 3 chunks):\n{context_summary}"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=DECISION_PROMPT),
            HumanMessage(content=user_msg),
        ])
        decision = response.content.strip().lower().replace("**", "")
        if decision in ("fix_sql", "inspect_schema", "re_retrieve"):
            logger.info("SQL validator decision: %s", decision)
            return decision
    except Exception as e:
        logger.warning("Decision LLM failed: %s", e)

    # Default: try to fix the SQL
    return "fix_sql"


# ---------------------------------------------------------------------------
# Strategy: fix_sql — correct the query using error context
# ---------------------------------------------------------------------------

FIX_SQL_PROMPT = """\
Tu es un expert SQL DuckDB. Corrige la requête SQL en te basant sur l'erreur.

RÈGLES :
- Retourne UNIQUEMENT la requête SQL corrigée, sans markdown, sans explication.
- Colonnes BOOLEAN : true/false (pas de guillemets)
- Pas de préfixe de schéma
- Pas de guillemets autour des identifiants
- IDs de magasins sont des chaînes : 'BV551', 'BV015'
"""


def _fix_sql(state: AgentState, schema_info: str = "") -> AgentState:
    """Corrige le SQL directement à partir de l'erreur."""
    extra_schema = f"\n\nSchéma réel de la DB:\n{schema_info}" if schema_info else ""

    user_msg = (
        f"Question: {state['question']}\n\n"
        f"SQL original: {state.get('sql_query', '')}\n\n"
        f"Erreur: {state.get('execution_error') or state.get('sql_error', '')}\n"
        f"{extra_schema}\n\n"
        f"SQL corrigé:"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=FIX_SQL_PROMPT),
            HumanMessage(content=user_msg),
        ])
        fixed_sql = (
            response.content.strip()
            .removeprefix("```sql")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        logger.info("SQL fixed: %s → %s", state.get("sql_query", "")[:80], fixed_sql[:80])
        return {
            **state,
            "sql_query": fixed_sql,
            "sql_error": None,
            "execution_error": None,
        }
    except Exception as e:
        logger.error("SQL fix failed: %s", e)
        return {**state, "sql_error": f"Fix failed: {str(e)}"}


# ---------------------------------------------------------------------------
# Strategy: inspect_schema — query DB schema then fix
# ---------------------------------------------------------------------------

def _inspect_and_fix(state: AgentState) -> AgentState:
    """Interroge le schéma via MCP, puis corrige le SQL."""
    # Determine which tables to inspect from the error and query
    sql = state.get("sql_query", "")
    error = state.get("execution_error") or state.get("sql_error", "")

    # Get all tables first
    tables_list = _inspect_tables()

    # Try to find mentioned tables in the SQL to get their columns
    schema_parts = [f"Tables disponibles:\n{tables_list}\n"]
    known_tables = [
        "products", "pricing_by_shop", "product_delivery_stock", "shops",
        "promotions", "promotion_by_product", "promotion_by_shop",
        "categories", "product_category", "product_variants",
        "product_attributes", "product_associations", "shop_services",
        "shop_opening_hours", "shop_delivery_modes", "shop_printing_services",
        "commandes",
    ]
    for table in known_tables:
        if table in sql.lower() or table in error.lower():
            cols = _inspect_columns(table)
            schema_parts.append(f"\nTable '{table}':\n{cols}")

    schema_info = "\n".join(schema_parts)
    logger.info("Schema inspected for tables in query")

    return _fix_sql(state, schema_info=schema_info)


# ---------------------------------------------------------------------------
# Strategy: re_retrieve — signal to redo the retrieval pipeline
# ---------------------------------------------------------------------------

def _mark_for_re_retrieval(state: AgentState) -> AgentState:
    """Marque l'état pour relancer le retrieval (reset chunks + retry)."""
    return {
        **state,
        "retrieved_chunks": None,
        "reranked_chunks": None,
        "sql_query": None,
        "sql_error": None,
        "execution_error": None,
        "needs_re_retrieval": True,
    }


# ---------------------------------------------------------------------------
# Main node: validate_and_correct
# ---------------------------------------------------------------------------

def validate_and_correct(state: AgentState) -> AgentState:
    """
    Nœud principal du validateur SQL.
    Appelé quand execution_error est non-null après call_mcp.
    Décide de la stratégie et l'applique.
    """
    error = state.get("execution_error")
    if not error:
        # Pas d'erreur → rien à faire
        return state

    logger.info("SQL validator triggered — error: %s", error[:100])

    strategy = _decide_strategy(state)

    if strategy == "fix_sql":
        return _fix_sql(state)
    elif strategy == "inspect_schema":
        return _inspect_and_fix(state)
    else:  # re_retrieve
        return _mark_for_re_retrieval(state)


# ---------------------------------------------------------------------------
# Routing function for the orchestrator
# ---------------------------------------------------------------------------

def route_after_validation(state: AgentState) -> Literal["retry_mcp", "re_retrieve", "give_up"]:
    """
    Après validation/correction :
    - Si SQL corrigé → réessayer MCP
    - Si re_retrieve → relancer le retrieval
    - Si toujours en erreur après 2 tentatives → abandonner
    """
    if state.get("needs_re_retrieval"):
        return "re_retrieve"

    if state.get("sql_query") and not state.get("sql_error"):
        return "retry_mcp"

    return "give_up"
