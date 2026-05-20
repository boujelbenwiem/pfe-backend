from typing import TypedDict, List, Dict, Optional, Literal


class AgentState(TypedDict):
    """Etat partage entre tous les agents."""

    # Entree utilisateur
    user_id: str
    user_role: str
    user_shop_id: Optional[str]
    question: str
    timestamp: str
    conversation_id: Optional[str]

    # Agent 1 - Classification
    intention: Optional[Literal["analytique", "metier", "generale", "erreur"]]

    # Agent 2 - Generation SQL
    retrieved_chunks: Optional[List[Dict]]   
    reranked_chunks: Optional[List[Dict]]    
    sql_query: Optional[str]
    sql_error: Optional[str]
    retry_count: int

    # Agent 3 - Execution
    query_result: Optional[List[tuple]]
    query_columns: Optional[List[str]]
    filters_applied: Optional[List[str]]  
    execution_error: Optional[str]

    # Agent 4 - Formatage
    output_type: Optional[Literal["text", "table", "chart"]]
    chart_type: Optional[Literal["bar", "line", "pie"]]
    formatted_response: Optional[Dict]

    # Global
    access_denied: Optional[bool]
    error: Optional[str]
