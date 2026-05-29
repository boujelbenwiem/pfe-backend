# backend/app/agents/orchestrator.py
# Construit et compile le graph complet du pipeline multi-agents.
# Toutes les topologies sont visibles ici en un seul endroit.

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from langgraph.graph import StateGraph, END
import opik
from opik import configure as opik_configure
from opik import get_global_client as opik_client
from opik.integrations.langchain import OpikTracer

from langfuse import get_client as get_langfuse_client
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

from app.core.config import settings
from app.agents.state import AgentState
from app.agents.agent_classifier import classify_query, answer_directly
from app.agents.agent_rag import retrieve_chunks, rerank_chunks
from app.agents.agent_sql import generate_sql, increment_retry, should_retry
from app.agents.agent_mcp_client import call_mcp
from app.agents.agent_formattage import (
    decide_format, format_as_text, format_as_table, format_as_chart, route_format
)
from app.agents.agent_access_control import check_shop_access, route_access

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Opik tracing setup (kept for future use)
# ---------------------------------------------------------------------------

if settings.TRACING_BACKEND == "opik":
    if settings.OPIK_API_KEY:
        opik_configure(
            api_key=settings.OPIK_API_KEY,
            project_name=settings.OPIK_PROJECT_NAME,
            use_local=False,
        )
    else:
        opik_configure(use_local=True, project_name=settings.OPIK_PROJECT_NAME)

# ---------------------------------------------------------------------------
# Langfuse tracing setup (v4 SDK — uses env vars LANGFUSE_SECRET_KEY,
# LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL automatically via get_client())
# ---------------------------------------------------------------------------


def _make_tracer() -> Optional["OpikTracer"]:
    """Crée un OpikTracer attaché au graph compilé pour le tracing LangGraph complet."""
    try:
        return OpikTracer(graph=_get_pipeline_graph().get_graph(xray=True))
    except Exception as e:
        logger.warning("OpikTracer init failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_by_intention(state: AgentState) -> Literal["retrieve", "answer_directly", "end"]:
    """Après classification : analytique → RAG+SQL, generale/metier → LLM direct, sinon → END."""
    intention = state.get("intention")
    if intention == "analytique":
        return "retrieve"
    if intention in ("generale", "metier"):
        return "answer_directly"
    return "end"


# ---------------------------------------------------------------------------
# Graph (singleton)
# ---------------------------------------------------------------------------

_pipeline_graph = None


def _get_pipeline_graph():
    global _pipeline_graph
    if _pipeline_graph is None:
        builder = StateGraph(AgentState)

        # Nœuds
        builder.add_node("classify",          classify_query)
        builder.add_node("check_access",      check_shop_access)
        builder.add_node("answer_directly",   answer_directly)
        builder.add_node("retrieve",          retrieve_chunks)
        builder.add_node("rerank",            rerank_chunks)
        builder.add_node("generate_sql",      generate_sql)
        builder.add_node("increment_retry",   increment_retry)
        builder.add_node("call_mcp",          call_mcp)
        builder.add_node("decide_format",     decide_format)
        builder.add_node("format_as_text",    format_as_text)
        builder.add_node("format_as_table",   format_as_table)
        builder.add_node("format_as_chart",   format_as_chart)

        # Entrée
        builder.set_entry_point("classify")

        # classify → route selon intention
        builder.add_conditional_edges(
            "classify",
            route_by_intention,
            {"retrieve": "check_access", "answer_directly": "answer_directly", "end": END},
        )
        builder.add_edge("answer_directly", END)

        # Contrôle d'accès (STORE_MANAGER) → bloqué ou autorisé
        builder.add_conditional_edges(
            "check_access",
            route_access,
            {"allowed": "retrieve", "denied": END},
        )

        # RAG pipeline
        builder.add_edge("retrieve", "rerank")
        builder.add_edge("rerank",   "generate_sql")

        # SQL avec retry → MCP si succès
        builder.add_conditional_edges(
            "generate_sql",
            should_retry,
            {"retry": "increment_retry", "done": "call_mcp"},
        )
        builder.add_edge("increment_retry", "generate_sql")
        builder.add_edge("call_mcp", "decide_format")
        builder.add_conditional_edges(
            "decide_format",
            route_format,
            {
                "format_as_text":  "format_as_text",
                "format_as_table": "format_as_table",
                "format_as_chart": "format_as_chart",
            },
        )
        builder.add_edge("format_as_text",  END)
        builder.add_edge("format_as_table", END)
        builder.add_edge("format_as_chart", END)

        _pipeline_graph = builder.compile()
    return _pipeline_graph


def run_pipeline(state: AgentState, session_id: Optional[str] = None) -> AgentState:
    """Point d'entrée principal — exécute le pipeline complet avec tracing Opik ou Langfuse."""
    config: dict = {}

    if settings.TRACING_BACKEND == "langfuse":
        # Langfuse v4: CallbackHandler auto-reads env vars (LANGFUSE_SECRET_KEY,
        # LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL). We use propagate_attributes to
        # attach user_id and session_id to all spans in the trace.
        langfuse_handler = LangfuseCallbackHandler()
        config["callbacks"] = [langfuse_handler]
        config["metadata"] = {
            "langfuse_session_id": session_id or state.get("conversation_id", ""),
            "langfuse_user_id": state.get("user_id", ""),
            "langfuse_tags": ["multi-agent-pipeline", state.get("user_role", "")],
        }
        if session_id:
            config["run_name"] = f"pipeline-{session_id}"
    else:
        tracer = _make_tracer()
        if tracer:
            config["callbacks"] = [tracer]
        if session_id:
            config["run_name"] = session_id

    result = _get_pipeline_graph().invoke(state, config=config or None)

    # Flush trace buffer
    if settings.TRACING_BACKEND == "langfuse":
        try:
            get_langfuse_client().flush()
        except Exception:
            pass
    else:
        try:
            opik_client().flush()
        except Exception:
            pass

    return result


def build_initial_state(
    question: str,
    user_id: str,
    user_role: str,
    user_shop_id: str = None,
    conversation_id: Optional[str] = None,
) -> AgentState:
    """Construit l'état initial propre pour une nouvelle requête."""
    return {
        "user_id": user_id,
        "user_role": user_role,
        "user_shop_id": user_shop_id,
        "question": question,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "intention": None,
        "access_denied": None,
        "retrieved_chunks": None,
        "reranked_chunks": None,
        "sql_query": None,
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


# ---------------------------------------------------------------------------
# Test standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        ("Quel est le stock du produit avec le SKU 1282 ?",       "ADMIN",         None),
        
    ]

    print("\n" + "=" * 70)
    print("🧪 TEST ORCHESTRATOR — PIPELINE COMPLET")
    print("=" * 70)

    for question, role, shop_id in tests:
        state = build_initial_state(question, user_id="test", user_role=role, user_shop_id=shop_id)
        result = run_pipeline(state)

        intention_emoji = {"analytique": "📊", "metier": "📖", "generale": "ℹ️", "erreur": "❌"}.get(result["intention"], "❓")
        print(f"\n❓ {question}")
        print(f"  {intention_emoji} Intention     : {result['intention']}")
        if result.get("retrieved_chunks") is not None:
            print(f"  📦 Chunks       : {len(result['retrieved_chunks'])} récupérés → {len(result.get('reranked_chunks') or [])} rerankés")
            print(f"  🔄 Tentatives   : {result['retry_count']}")
        if result.get("sql_query"):
            print(f"  🔍 SQL :\n     {result['sql_query']}")
        if result.get("query_columns"):
            print(f"  📊 Colonnes     : {result['query_columns']}")
            print(f"  📊 Lignes       : {len(result.get('query_result') or [])}")
        if result.get("execution_error"):
            print(f"  ❌ Exec erreur  : {result['execution_error']}")
        if result.get("error"):
            print(f"  ❌ Erreur       : {result['error']}")        
        fr = result.get("formatted_response")
        if fr:
            print(f"  \U0001f4ac Format       : {fr['type']}"
                  + (f" ({fr.get('chartType')})" if fr.get('chartType') else ""))
            if fr["type"] == "text":
                print(f"  \U0001f4ac R\u00e9ponse      : {fr['content']}")
            elif fr["type"] == "table":
                print(f"  \U0001f4ac Colonnes     : {[c['label'] for c in fr['columns']]}")
                print(f"  \U0001f4ac Lignes       : {len(fr['data'])}")
            elif fr["type"] == "chart":
                print(f"  \U0001f4ac X={fr['xAxis']['label']} | Y={fr['yAxis']['label']}")       
                print("-" * 70)
