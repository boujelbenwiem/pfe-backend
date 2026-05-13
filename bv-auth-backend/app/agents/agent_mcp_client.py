# backend/app/agents/agent_mcp_client.py
# Responsabilité unique : appelle le MCP server et met à jour query_result dans le state

import logging

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.MCP.server import execute_query, MCPRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nœud
# ---------------------------------------------------------------------------

def call_mcp(state: AgentState) -> AgentState:
    """
    Appelle le MCP server avec le sql_query du state.
    Met à jour : query_result, query_columns, execution_error.
    """
    sql = state.get("sql_query")

    if not sql:
        return {**state, "execution_error": "Aucune requête SQL à exécuter."}

    request = MCPRequest(
        sql=sql,
        user_role=state["user_role"],
        user_shop_id=state.get("user_shop_id"),
    )

    response = execute_query(request)

    if not response.success:
        logger.error("MCP execution failed: %s", response.error)
        return {
            **state,
            "query_result": None,
            "query_columns": None,
            "execution_error": response.error,
        }

    return {
        **state,
        "query_result": [tuple(row) for row in response.rows],
        "query_columns": response.columns,
        "filters_applied": response.filters_applied,
        "execution_error": None,
    }


# ---------------------------------------------------------------------------
# Graph (singleton) — nœud unique, utilisé par l'orchestrateur
# ---------------------------------------------------------------------------

_mcp_graph = None


def _get_mcp_graph():
    global _mcp_graph
    if _mcp_graph is None:
        builder = StateGraph(AgentState)
        builder.add_node("call_mcp", call_mcp)
        builder.set_entry_point("call_mcp")
        builder.add_edge("call_mcp", END)
        _mcp_graph = builder.compile()
    return _mcp_graph


def run_mcp_agent(state: AgentState) -> AgentState:
    """Point d'entrée pour l'orchestrateur."""
    return _get_mcp_graph().invoke(state)


# ---------------------------------------------------------------------------
# Test standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import datetime, timezone

    state: AgentState = {
        "user_id": "test",
        "user_role": "ADMIN",
        "user_shop_id": None,
        "question": "Combien y a-t-il de produits ?",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intention": "analytique",
        "retrieved_chunks": None,
        "reranked_chunks": None,
        "sql_query": "SELECT COUNT(*) AS total FROM products",
        "sql_error": None,
        "retry_count": 0,
        "query_result": None,
        "query_columns": None,
        "execution_error": None,
        "output_type": None,
        "chart_type": None,
        "formatted_response": None,
        "error": None,
    }

    result = run_mcp_agent(state)

    if result.get("execution_error"):
        print(f"❌ Erreur : {result['execution_error']}")
    else:
        print(f"✅ Colonnes : {result['query_columns']}")
        print(f"📊 Résultats ({len(result['query_result'])} lignes) :")
        for row in result["query_result"][:5]:
            print(f"   {row}")
