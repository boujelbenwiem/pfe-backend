# backend/app/MCP/executor.py
# Etape 3 & 4 : Exécution DuckDB + post-traitement

import threading
import time
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

import duckdb

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_ROWS = 1000

# ---------------------------------------------------------------------------
# Singleton warehouse connection (read-only — multiple threads safe in DuckDB)
# ---------------------------------------------------------------------------
_warehouse_conn: duckdb.DuckDBPyConnection | None = None
_warehouse_lock = threading.Lock()


def _get_warehouse_conn() -> duckdb.DuckDBPyConnection:
    global _warehouse_conn
    if _warehouse_conn is None:
        _warehouse_conn = duckdb.connect(database=settings.WAREHOUSE_PATH, read_only=False)
    return _warehouse_conn


@dataclass
class ExecutionResult:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False          # True si résultat limité à MAX_ROWS
    error: Optional[str] = None


def execute_sql(sql: str) -> ExecutionResult:
    """
    Exécute la requête SQL sur DuckDB.
    - Limite à MAX_ROWS lignes
    - Mesure le temps d'exécution
    - Retourne colonnes + lignes + métadonnées
    """
    start = time.perf_counter()

    try:
        with _warehouse_lock:
            conn = _get_warehouse_conn()

            # Limite les résultats
            limited_sql = _apply_limit(sql, MAX_ROWS + 1)

            relation = conn.execute(limited_sql)
            columns = [desc[0] for desc in relation.description]
            rows = relation.fetchall()

        truncated = len(rows) > MAX_ROWS
        if truncated:
            rows = rows[:MAX_ROWS]

        # Fix mal-encodage latin-1/UTF-8 sur toutes les valeurs texte
        rows = [tuple(_fix_encoding(v) for v in row) for row in rows]

        elapsed_ms = (time.perf_counter() - start) * 1000

        return ExecutionResult(
            success=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(elapsed_ms, 2),
            truncated=truncated,
        )

    except duckdb.Error as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error("DuckDB execution error: %s", e)
        return ExecutionResult(
            success=False,
            execution_time_ms=round(elapsed_ms, 2),
            error=str(e),
        )


def _apply_limit(sql: str, limit: int) -> str:
    """
    Ajoute ou remplace la clause LIMIT pour ne pas dépasser MAX_ROWS.
    """
    import re
    existing = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
    if existing:
        current_limit = int(existing.group(1))
        # Garde le plus petit
        if current_limit > limit:
            sql = re.sub(
                r"\bLIMIT\s+\d+", f"LIMIT {limit}", sql, flags=re.IGNORECASE
            )
    else:
        sql = sql.rstrip("; \n") + f" LIMIT {limit}"
    return sql


def _fix_encoding(v: Any) -> Any:
    """Corrige les chaînes mal encodées (UTF-8 lu comme latin-1 → réencode en UTF-8)."""
    if not isinstance(v, str):
        return v
    try:
        return v.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return v


def _serialize_value(v: Any) -> Any:
    """Convertit les types DuckDB non-JSON-serialisables."""
    if isinstance(v, Decimal):
        return float(v)
    return _fix_encoding(v)


def format_result(result: ExecutionResult) -> dict[str, Any]:
    """
    Sérialise le résultat en dict JSON-compatible avec métadonnées.
    """
    return {
        "success": result.success,
        "columns": result.columns,
        "rows": [[_serialize_value(v) for v in row] for row in result.rows],
        "metadata": {
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "truncated": result.truncated,
            "max_rows": MAX_ROWS,
        },
        "error": result.error,
    }
