# backend/app/MCP/server.py
# MCP Server : orchestre les 4 étapes (validation → filtrage → exécution → post-traitement)

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.MCP.validator import validate_sql
from app.MCP.filter import apply_filters
from app.MCP.executor import execute_sql, format_result

logger = logging.getLogger(__name__)


@dataclass
class MCPRequest:
    sql: str
    user_role: str
    user_shop_id: Optional[str] = None


@dataclass
class MCPResponse:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    filters_applied: list[str] = field(default_factory=list)
    error: Optional[str] = None


def execute_query(request: MCPRequest) -> MCPResponse:
    """
    Pipeline MCP complet :
      1. Validation   — syntaxe + sécurité
      2. Filtrage     — selon rôle utilisateur
      3. Exécution    — DuckDB (max 1000 lignes)
      4. Formatage    — JSON + métadonnées
    """

    # --- Etape 1 : Validation ---
    validation = validate_sql(request.sql)
    if not validation.valid:
        logger.warning("SQL validation failed: %s", validation.error)
        return MCPResponse(success=False, error=f"Validation: {validation.error}")

    # --- Etape 2 : Filtrage ---
    filter_result = apply_filters(
        sql=request.sql,
        user_role=request.user_role,
        user_shop_id=request.user_shop_id,
    )
    filtered_sql = filter_result.sql
    logger.debug("Filtered SQL: %s", filtered_sql)

    # --- Etape 3 : Exécution ---
    exec_result = execute_sql(filtered_sql)
    if not exec_result.success:
        return MCPResponse(
            success=False,
            filters_applied=filter_result.applied,
            error=f"Execution: {exec_result.error}",
        )

    # --- Etape 4 : Post-traitement ---
    formatted = format_result(exec_result)

    return MCPResponse(
        success=True,
        columns=formatted["columns"],
        rows=formatted["rows"],
        metadata=formatted["metadata"],
        filters_applied=filter_result.applied,
    )
