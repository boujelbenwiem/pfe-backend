# backend/app/agents/test_pipeline.py

import time

import pandas as pd
from opik import get_global_client as opik_client

from app.agents.orchestrator import _get_pipeline_graph, build_initial_state, run_pipeline
from app.agents.state import AgentState

# ---------------------------------------------------------------------------
# Export config
# ---------------------------------------------------------------------------
EXPORT_TO_EXCEL = False         # Mettre True pour exporter les résultats en Excel
EXPORT_FILE     = "test_results.xlsx"

def _format_reponse_finale(fr: dict) -> str:
    """Résume formatted_response en texte pour l'export Excel."""
    if not fr:
        return ""
    ftype = fr.get("type", "?")
    if ftype == "text":
        return fr.get("content", "")
    if ftype == "table":
        intro  = fr.get("intro", "")
        cols   = [c["label"] for c in fr.get("columns", [])]
        n_rows = len(fr.get("data", []))
        return f"{intro}\nColonnes : {cols}\nLignes : {n_rows}"
    if ftype == "chart":
        intro = fr.get("intro", "")
        x     = fr.get("xAxis", {}).get("label", "")
        y     = fr.get("yAxis", {}).get("label", "")
        return f"{intro}\nAxes : X={x} | Y={y}"
    return str(fr)


# ---------------------------------------------------------------------------
# Node-level live logging
# ---------------------------------------------------------------------------

NODE_LABELS = {
    "classify":        ("🔍", "Classifier"),
    "check_access":    ("🔒", "Contrôle accès"),
    "answer_directly": ("💬", "Réponse directe"),
    "retrieve":        ("📦", "Retrieval RAG"),
    "rerank":          ("✅", "Reranking"),
    "generate_sql":    ("🛠️ ", "Génération SQL"),
    "increment_retry": ("🔄", "Retry SQL"),
    "call_mcp":        ("🗄️ ", "Exécution DuckDB"),
    "decide_format":   ("🎨", "Décision format"),
    "format_as_text":  ("📝", "Format texte"),
    "format_as_table": ("📋", "Format tableau"),
    "format_as_chart": ("📊", "Format graphique"),
}


def _log_node(node: str, patch: dict):
    """Affiche un résumé concis de ce que le nœud a produit."""
    emoji, label = NODE_LABELS.get(node, ("▶️ ", node))
    print(f"\n  {emoji} [{label}]")

    if "intention" in patch:
        print(f"      intention       : {patch['intention']}")

    if "access_denied" in patch:
        status = "🚫 BLOQUÉ" if patch["access_denied"] else "✅ autorisé"
        print(f"      accès           : {status}")

    if "retrieved_chunks" in patch and patch["retrieved_chunks"] is not None:
        tables = [c.get("table_name", "?") for c in patch["retrieved_chunks"]]
        print(f"      chunks récupérés: {len(patch['retrieved_chunks'])} → {tables}")

    if "reranked_chunks" in patch and patch["reranked_chunks"] is not None:
        tables = [c.get("table_name", "?") for c in patch["reranked_chunks"]]
        print(f"      chunks rerankés : {len(patch['reranked_chunks'])} → {tables}")

    if "sql_query" in patch and patch["sql_query"]:
        sql = patch["sql_query"].replace("\n", " ")
        print(f"      SQL             : {sql[:200]}")

    if "sql_error" in patch and patch["sql_error"]:
        print(f"      ❌ Erreur SQL   : {patch['sql_error']}")

    if "retry_count" in patch:
        print(f"      tentative n°    : {patch['retry_count']}")

    if "query_columns" in patch and patch["query_columns"]:
        cols = patch["query_columns"]
        rows = patch.get("query_result") or []
        print(f"      colonnes        : {cols}")
        print(f"      lignes          : {len(rows)}")
        for row in rows[:3]:
            print(f"        {row}")

    if "execution_error" in patch and patch["execution_error"]:
        print(f"      ❌ Exec erreur  : {patch['execution_error']}")

    if "output_type" in patch and patch["output_type"]:
        print(f"      format décidé   : {patch['output_type']}")

    if "formatted_response" in patch and patch["formatted_response"]:
        fr = patch["formatted_response"]
        ftype = fr.get("type", "?")
        print(f"      type réponse    : {ftype}" +
              (f" ({fr.get('chartType')})" if fr.get("chartType") else ""))
        if ftype == "text":
            preview = str(fr.get("content", ""))[:200]
            print(f"      contenu         : {preview}")
        elif ftype == "table":
            if fr.get("intro"):
                print(f"      intro           : {fr['intro']}")
            print(f"      lignes tableau  : {len(fr.get('data', []))}")
        elif ftype == "chart":
            if fr.get("intro"):
                print(f"      intro           : {fr['intro']}")
            print(f"      axes            : X={fr['xAxis']['label']} | Y={fr['yAxis']['label']}")

    if "error" in patch and patch["error"]:
        print(f"      ❌ Erreur       : {patch['error']}")


# ---------------------------------------------------------------------------
# Résumé final
# ---------------------------------------------------------------------------

def print_result(state: AgentState):
    print(f"\n{'─'*70}")
    print("  RÉSUMÉ FINAL")
    print(f"{'─'*70}")
    intention_emoji = {
        "analytique": "📊", "metier": "📖", "generale": "ℹ️", "erreur": "❌",
    }.get(state.get("intention"), "❓")
    print(f"  {intention_emoji} Intention       : {state.get('intention')}")
    print(f"  👤 Rôle           : {state['user_role']}" +
          (f" (magasin: {state['user_shop_id']})" if state.get("user_shop_id") else ""))

    if state.get("retrieved_chunks") is not None:
        print(f"  📦 Chunks         : {len(state['retrieved_chunks'])} récupérés"
              f" → {len(state.get('reranked_chunks') or [])} rerankés")
        print(f"     Tables         : {[c['table_name'] for c in (state.get('reranked_chunks') or [])]}")
        print(f"  🔄 Tentatives SQL : {state['retry_count']}")

    if state.get("sql_query"):
        print(f"  🔍 SQL généré :\n     {state['sql_query']}")
    if state.get("filters_applied"):
        print(f"  🧹 Filtres MCP : {state['filters_applied']}")

    if state.get("execution_error"):
        print(f"  ❌ Erreur exec    : {state['execution_error']}")
    elif state.get("query_columns"):
        print(f"  📊 Colonnes       : {state['query_columns']}")
        rows = state.get("query_result") or []
        print(f"  📊 Lignes         : {len(rows)}")
        for row in rows[:5]:
            print(f"     {row}")

    fr = state.get("formatted_response")
    if fr:
        ftype = fr["type"]
        print(f"  💬 Format         : {ftype}" +
              (f" ({fr.get('chartType')})" if fr.get("chartType") else ""))
        if ftype == "text":
            print(f"  💬 Réponse        : {fr['content']}")
        elif ftype == "table":
            if fr.get("intro"):
                print(f"  💬 Intro          : {fr['intro']}")
            print(f"  💬 Colonnes table : {[c['label'] for c in fr['columns']]}")
            print(f"  💬 Lignes table   : {len(fr['data'])}")
        elif ftype == "chart":
            if fr.get("intro"):
                print(f"  💬 Intro          : {fr['intro']}")
            print(f"  💬 Axes           : X={fr['xAxis']['label']} | Y={fr['yAxis']['label']}")

    if state.get("error"):
        print(f"  ❌ Erreur pipeline: {state['error']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
   
    
    
    ("Quels est le nom  du produit 1282 ?", "STORE_MANAGER", "BV551"),
    

   
]



    print("\n" + "=" * 70)
    print("[TEST] PIPELINE — STREAMING PAS-A-PAS")
    print("=" * 70)

    graph = _get_pipeline_graph()
    results = []  # for Excel export

    for question, role, shop_id in tests:
        print(f"\n❓ {question}")
        print(f"   Rôle: {role}" + (f" | Magasin: {shop_id}" if shop_id else ""))
        print("-" * 70)

        t0 = time.perf_counter()
        initial_state = build_initial_state(
            question, user_id="test", user_role=role, user_shop_id=shop_id
        )

        # Stream : chaque étape s'affiche dès qu'elle se termine (updates only)
        final_state = initial_state
        for step in graph.stream(initial_state, stream_mode="updates"):
            for node_name, patch in step.items():
                _log_node(node_name, patch)
                # Merge patch into final_state for the summary
                final_state = {**final_state, **patch}

        elapsed = round(time.perf_counter() - t0, 2)

        print_result(final_state)
        print(f"\n  ⏱  Durée totale : {elapsed}s")

        if EXPORT_TO_EXCEL:
            results.append({
                "question":      question,
                "requete_sql":   final_state.get("sql_query") or "",
                "reponse_finale": _format_reponse_finale(final_state.get("formatted_response")),
            })

        # Opik trace (entrypoint) for this question
        run_pipeline(initial_state, session_id=f"test-pipeline-{role}")

    print("\n" + "=" * 70)
    print("[OK] Pipeline termine")
    print("=" * 70)

    if EXPORT_TO_EXCEL and results:
        df = pd.DataFrame(results, columns=["question", "requete_sql", "reponse_finale"])
        df.to_excel(EXPORT_FILE, index=False)
        print(f"\n  📁 Résultats exportés → {EXPORT_FILE}")

    # Flush Opik traces before the script exits
    try:
        opik_client().flush()
    except Exception:
        pass
        opik_client().flush()
    except Exception:
        pass
