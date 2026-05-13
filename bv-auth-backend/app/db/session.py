# gerer les connections à la base de données DuckDB
# DuckDB allows only ONE read-write connection per file per process.
# We use a module-level singleton + threading.Lock so all FastAPI threads
# share the same connection safely.
import threading
import duckdb
from app.core.config import settings

_auth_conn: duckdb.DuckDBPyConnection | None = None
_auth_lock = threading.Lock()


def get_auth_connection() -> duckdb.DuckDBPyConnection:
    """Return the shared auth-DB connection, creating it once if needed."""
    global _auth_conn
    if _auth_conn is None:
        _auth_conn = duckdb.connect(database=settings.DATABASE_PATH, read_only=False)
    return _auth_conn


def get_db_connection():
    """
    FastAPI dependency — yields the shared DuckDB connection protected by a lock.
    The lock serialises writes so concurrent requests don't corrupt state.
    """
    conn = get_auth_connection()
    with _auth_lock:
        yield conn




