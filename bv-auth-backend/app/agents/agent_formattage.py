import json
import logging
from typing import Any, Dict, List, Literal

import ollama
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "mistral:latest"

_intro_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

# Helpers

def _to_dicts(state: AgentState) -> List[Dict]:
    """Convertit query_result (list of tuples) + query_columns en list of dicts."""
    columns = state.get("query_columns") or []
    rows = state.get("query_result") or []
    return [dict(zip(columns, row)) for row in rows]


def _humanize(col: str) -> str:
    mapping = {
        "sku": "SKU", "product": "Produit", "quantity": "Quantité",
        "available_quantity": "Stock disponible", "price": "Prix",
        "date": "Date", "status": "Statut", "shop_id": "Magasin",
        "city": "Ville", "sales": "Ventes", "total": "Total",
    }
    return mapping.get(col, col.replace("_", " ").title())


def _detect_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _detect_axes(data: List[Dict], columns: List[str]):
    x_field = next(
        (c for c in columns if any(k in c.lower() for k in ["date", "product", "name", "month", "label"])),
        columns[0],
    )
    y_field = next(
        (c for c in columns if isinstance(data[0].get(c), (int, float))),
        columns[-1],
    )
    return x_field, y_field


def _llm_intro(question: str, n_rows: int, columns: List[str], output_type: str = "table") -> str:
    """Génère une phrase introductive pour un tableau ou graphique."""
    cols_str = ", ".join(columns)
    prompt = (
        f"Question de l'utilisateur : {question}\n"
        f"Le résultat contient {n_rows} ligne(s) et les colonnes suivantes : {cols_str}.\n\n"
        f"Type de réponse : {output_type}\n\n"
        "Écris UNE SEULE phrase introductive en français pas trop longue qui présente "
        "ce résultat de manière naturelle. Ne commence pas par 'Voici' uniquement, "
        "sois précis sur ce que montrent les données."
        "ne genere jamis des tableau markdown ou des listes a puce dans ta reponse, uniquement du texte fluide et naturel."
    )
    try:
        response = _intro_llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        logger.warning("Intro LLM failed: %s", e)
        return f"Voici les résultats pour : {question.rstrip('?').strip()}"


# Nœud 1 : Décision du format


def decide_format(state: AgentState) -> AgentState:
    """
    Décide du format de sortie selon la structure des données :
    - Pas de données ou ligne unique simple → text
    - Plus de 2 colonnes et plus d'une ligne → table
    - 2 colonnes dont 1 numérique          → chart (LLM choisit bar/line/pie)
    """
    data = _to_dicts(state)

    if not data:
        return {**state, "output_type": "text"}

    # Ligne unique → toujours texte
    if len(data) == 1:
        return {**state, "output_type": "text"}

    columns = list(data[0].keys())

    if len(columns) > 2 and len(data) > 1:
        return {**state, "output_type": "table"}

    # Colonnes identifiants → pas de graphique
    ID_PATTERNS = ("id", "sku", "code", "ref", "num", "number", "no")
    has_id_col = any(
        any(pat in c.lower() for pat in ID_PATTERNS)
        for c in columns
    )
    if has_id_col:
        return {**state, "output_type": "table"}

    # 2 colonnes, 1 numérique métrique → graphique
    has_numeric = any(isinstance(data[0].get(c), (int, float)) for c in columns)
    if not has_numeric:
        return {**state, "output_type": "table"}

    chart_type = _llm_decide_chart_type(data, columns, state["question"])
    return {**state, "output_type": "chart", "chart_type": chart_type}


_chart_llm = ChatGroq(
    model="gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0,
)


def _llm_decide_chart_type(
    data: List[Dict], columns: List[str], question: str
) -> Literal["bar", "line", "pie"]:
    numeric_col = next(c for c in columns if isinstance(data[0].get(c), (int, float)))
    label_col = next((c for c in columns if c != numeric_col), columns[0])

    prompt = (
        f"QUESTION: {question}\n"
        f"COLONNE LABEL: {label_col} | COLONNE VALEUR: {numeric_col}\n\n"
        
        "Choisis le type de graphique:\n"
        "- bar  : comparer des catégories\n"
        "- line : évolution temporelle (label = date/mois/année)\n"
        "- pie  : parts d'un tout\n"
        "Réponds UNIQUEMENT par un seul mot: bar, line ou pie"
    )
    try:
        response = _chart_llm.invoke([HumanMessage(content=prompt)])
        result = response.content.strip().lower()
        if "pie" in result:
            return "pie"
        if "line" in result:
            return "line"
        return "bar"
    except Exception:
        return "bar"


# Nœud 2 : Formatage texte (Groq + anonymisation des données)

_text_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.1,
)


def _anonymize_data(data: List[Dict]) -> tuple[List[Dict], Dict[str, Any]]:
    """
    Remplace chaque valeur réelle par un placeholder (VAL_1, VAL_2, ...),
    retourne les données anonymisées et un mapping placeholder → valeur réelle.
    """
    mapping: Dict[str, Any] = {}
    counter = 0
    anon_data = []
    for row in data:
        anon_row = {}
        for col, val in row.items():
            if isinstance(val, bool):
                anon_row[col] = val
            else:
                counter += 1
                placeholder = f"VAL_{counter}"
                mapping[placeholder] = val
                anon_row[col] = placeholder
        anon_data.append(anon_row)
    return anon_data, mapping


def _deanonymize_text(text: str, mapping: Dict[str, Any]) -> str:
    """Remplace les placeholders dans le texte LLM par les valeurs réelles."""
    for placeholder, real_value in mapping.items():
        text = text.replace(placeholder, str(real_value))
    return text


def format_as_text(state: AgentState) -> AgentState:
    """Formate la réponse en langage naturel via Groq LLM avec données anonymisées."""
    data = _to_dicts(state)

    # Pas de données (erreur d'exécution ou aucun résultat)
    if not data:
        error = state.get("execution_error") or state.get("sql_error") or state.get("error")
        if error:
            result = {**state, "formatted_response": {
                "type": "text",
                "content": "Je n'ai pas pu exécuter cette requête. Veuillez reformuler votre question.",
            }}
        else:
            result = {**state, "formatted_response": {
                "type": "text",
                "content": "Aucun résultat trouvé pour cette question.",
            }}
        return result
    


    # Anonymiser : on envoie les noms de colonnes + placeholders, pas les vraies valeurs
    anon_data, mapping = _anonymize_data(data)
    columns = list(data[0].keys())
    anon_str = json.dumps(anon_data, ensure_ascii=False, indent=2)

    prompt = (
        f"Question posée : {state['question']}\n\n"
        f"Attributs disponibles : {', '.join(columns)}\n"
        f"Nombre de résultats : {len(data)}\n\n"
        f"Données (les valeurs sont des identifiants temporaires que tu DOIS reprendre tels quels) :\n{anon_str}\n\n"
        "INSTRUCTIONS STRICTES :\n"
        "1. Formule une réponse naturelle en français, concise, qui répond à la question .\n"
        "2. Tu DOIS inclure les identifiants temporaires (VAL_1, VAL_2, etc.) EXACTEMENT comme ils apparaissent.\n"
        "3. Ne traduis PAS et ne modifie PAS les identifiants VAL_X.\n"
        "4. Pour les nombres dans les identifiants, utilise-les tels quels.\n"
        "5. exemple de réponse attendue : 'Le produit VAL_1 (Cahier) a un stock disponible de VAL_2 unités.'\n"
        "6. si la valeur est un booléen, repond directement naturellement exemple : oui le produit est disponible. \n"
    )
    try:
        response = _text_llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        # Réinjecter les vraies valeurs à la place des placeholders
        content = _deanonymize_text(content, mapping)
    except Exception as e:
        logger.warning("Text formatting LLM failed: %s", e)
        content = " | ".join(f"{k}: {v}" for k, v in data[0].items()) if data else "Aucune donnée."

    result= {**state, "formatted_response": {"type": "text", "content": content}}
    return result


# Nœud 3 : Formatage tableau

def format_as_table(state: AgentState) -> AgentState:
    """Formate les données en structure tableau."""
    data = _to_dicts(state)

    if not data:
        return format_as_text(state)

    columns = [
        {"field": col, "label": _humanize(col), "type": _detect_type(data[0].get(col))}
        for col in data[0].keys()
    ]
    col_names = list(data[0].keys())
    intro = _llm_intro(state["question"], len(data), col_names, output_type=state.get("output_type", "table"))

    result = {
        **state,
        "formatted_response": {
            "type": "table",
            "intro": intro,
            "title": state["question"].rstrip("?").strip(),
            "columns": columns,
            "data": data,
            "options": {"sortable": True, "pagination": len(data) > 10, "pageSize": 10},
        },
    }
    return result


# Nœud 4 : Formatage graphique

def format_as_chart(state: AgentState) -> AgentState:
    """Formate les données en structure graphique."""
    data = _to_dicts(state)

    if not data:
        return format_as_text(state)

    columns = list(data[0].keys())
    x_field, y_field = _detect_axes(data, columns)
    chart_type = state.get("chart_type") or "bar"
    intro = _llm_intro(state["question"], len(data), columns, output_type=state.get("output_type", "chart"))

    result = {
        **state,
        "formatted_response": {
            "type": "chart",
            "intro": intro,
            "chartType": chart_type,
            "title": state["question"].rstrip("?").strip(),
            "xAxis": {"label": _humanize(x_field), "field": x_field},
            "yAxis": {"label": _humanize(y_field), "field": y_field},
            "data": data,
            "options": {
                "responsive": True,
                "showValues": chart_type == "bar" and len(data) <= 10,
            },
        },
    }
    return result


# Router — utilisé par l'orchestrateur

def route_format(state: AgentState) -> Literal["format_as_text", "format_as_table", "format_as_chart"]:
    output_type = state.get("output_type", "text")
    if output_type == "table":
        return "format_as_table"
    if output_type == "chart":
        return "format_as_chart"
    return "format_as_text"


# Test standalone

if __name__ == "__main__":
    from datetime import datetime, timezone

    def _make_state(question, columns, rows) -> AgentState:
        return {
            "user_id": "test", "user_role": "ADMIN", "user_shop_id": None,
            "question": question,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intention": "analytique", "retrieved_chunks": None,
            "reranked_chunks": None, "sql_query": None, "sql_error": None,
            "retry_count": 0, "query_result": rows, "query_columns": columns,
            "execution_error": None, "output_type": None, "chart_type": None,
            "formatted_response": None, "error": None,
        }

    tests = [
        ("Quel est le stock du produit 1282 ?",
         ["sku", "available_quantity"], [("1282", 45)]),
        ("Quels sont les 5 produits les plus vendus ?",
         ["rank", "product", "qty"], [(1, "Cahier", 1250), (2, "Stylo", 980)]),
        ("Évolution des ventes par mois ?",
         ["month", "sales"], [("2024-01", 10000), ("2024-02", 12000)]),
    ]

    for question, columns, rows in tests:
        state = _make_state(question, columns, rows)
        state = decide_format(state)
        print(f"\n❓ {question}")
        print(f"  → output_type: {state['output_type']} | chart_type: {state.get('chart_type')}")
        if state["output_type"] == "text":
            result = format_as_text(state)
        elif state["output_type"] == "table":
            result = format_as_table(state)
        else:
            result = format_as_chart(state)
        print(f"  → formatted_response type: {result['formatted_response']['type']}") 

