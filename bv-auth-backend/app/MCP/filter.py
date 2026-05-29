# backend/app/MCP/filter.py
# Etape 2 : Filtrage et transformation SQL selon le rôle utilisateur

import re
import logging
from dataclasses import dataclass
from typing import Optional

from app.MCP.executor import _get_warehouse_conn, _warehouse_lock

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    sql: str                  # requête transformée
    applied: list[str]        # liste des transformations appliquées


def _tables_with_shop_id() -> set[str]:
    """Retourne l'ensemble des tables qui possèdent une colonne shop_id dans le warehouse."""
    try:
        with _warehouse_lock:
            conn = _get_warehouse_conn()
            rows = conn.execute(
                "SELECT DISTINCT table_name FROM information_schema.columns "
                "WHERE column_name = 'shop_id'"
            ).fetchall()
        return {r[0].lower() for r in rows}
    except Exception as e:
        logger.warning("Could not query information_schema for shop_id: %s", e)
        return set()


def _sql_references_shop_id_table(sql: str, shop_id_tables: set[str]) -> bool:
    """Vérifie si le SQL référence au moins une table qui a une colonne shop_id."""
    # Extrait les identifiants qui ressemblent à des noms de tables (après FROM / JOIN)
    referenced = set(re.findall(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        sql,
        re.IGNORECASE,
    ))
    return bool(referenced & shop_id_tables)


def apply_filters(sql: str, user_role: str, user_shop_id: Optional[str] = None) -> FilterResult:
    """
    Applique les transformations SQL selon le rôle :
    - STORE_MANAGER : injection WHERE shop_id = '...'
    - ADMIN         : aucune transformation
    """
    applied = []

    if user_role == "STORE_MANAGER":
        sql, applied = _filter_store_manager(sql, user_shop_id, applied)

    
    # ADMIN : pass-through

    return FilterResult(sql=sql, applied=applied)


# ---------------------------------------------------------------------------
# Filtres par rôle
# ---------------------------------------------------------------------------

def _filter_store_manager(sql: str, shop_id: Optional[str], applied: list) -> tuple[str, list]:
    """Restreint les données au magasin de l'utilisateur — seulement si shop_id existe dans les tables référencées."""
    if not shop_id:
        return sql, applied

    # Ne filtre que si au moins une table du SQL possède une colonne shop_id
    shop_id_tables = _tables_with_shop_id()
    if not _sql_references_shop_id_table(sql, shop_id_tables):
        logger.debug("STORE_MANAGER filter skipped: no shop_id column in referenced tables")
        return sql, applied

    shop_id_safe = re.sub(r"['\";]", "", shop_id)  # sanitation basique

    if re.search(r"\bWHERE\b", sql, re.IGNORECASE):
        # Ajoute la condition au WHERE existant
        sql = re.sub(
            r"\bWHERE\b",
            f"WHERE shop_id = '{shop_id_safe}' AND",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
    elif re.search(r"\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bHAVING\b", sql, re.IGNORECASE):
        # Insère WHERE avant la première clause de fin
        sql = re.sub(
            r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING)\b",
            f"WHERE shop_id = '{shop_id_safe}' \\1",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        sql = sql.rstrip("; \n") + f" WHERE shop_id = '{shop_id_safe}'"

    applied.append(f"STORE_MANAGER filter: shop_id = '{shop_id_safe}'")
    return sql, applied






