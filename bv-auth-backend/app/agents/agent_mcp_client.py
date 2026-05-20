

import logging

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.MCP.server import execute_query, MCPRequest

logger = logging.getLogger(__name__)


# Nœud

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


