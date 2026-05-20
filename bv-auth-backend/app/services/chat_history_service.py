import duckdb
import json
import uuid
from datetime import datetime
from typing import Any, Optional, List

from app.schemas.chat_history import (
    ConversationResponse,
    ConversationDetailResponse,
    MessageResponse,
)


class ChatHistoryService:
    """Service pour gérer l'historique des conversations (style ChatGPT)."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self.db_path)

    def _init_tables(self):
        """Crée les tables de chat history si elles n'existent pas."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                title VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_archived BOOLEAN DEFAULT FALSE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id VARCHAR PRIMARY KEY,
                conversation_id VARCHAR NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                sql_query TEXT,
                formatted_response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: ajouter la colonne formatted_response si elle n'existe pas
        try:
            conn.execute("ALTER TABLE conversation_messages ADD COLUMN formatted_response TEXT")
        except Exception:
            pass  # Colonne existe déjà
        conn.close()

    def create_conversation(self, user_id: str, title: Optional[str] = None) -> str:
        """Crée une nouvelle conversation et retourne son ID."""
        conversation_id = str(uuid.uuid4())
        now = datetime.now()
        title = title or f"Conversation {now.strftime('%d/%m/%Y %H:%M')}"
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, user_id, title, now, now),
        )
        conn.close()
        return conversation_id

    def add_message(self, conversation_id: str, role: str, content: str, sql_query: Optional[str] = None, formatted_response: Optional[Any] = None) -> str:
        """Ajoute un message à une conversation existante."""
        message_id = str(uuid.uuid4())
        now = datetime.now()
        formatted_json = json.dumps(formatted_response, ensure_ascii=False, default=str) if formatted_response else None
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO conversation_messages (id, conversation_id, role, content, sql_query, formatted_response, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, conversation_id, role, content, sql_query, formatted_json, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.close()
        return message_id

    def get_user_conversations(self, user_id: str, limit: int = 50, include_archived: bool = False) -> List[ConversationResponse]:
        """Récupère la liste des conversations d'un utilisateur."""
        conn = self._get_conn()
        archive_filter = "" if include_archived else "AND c.is_archived = FALSE"
        rows = conn.execute(f"""
            SELECT
                c.id, c.title, c.created_at, c.updated_at,
                COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN conversation_messages m ON m.conversation_id = c.id
            WHERE c.user_id = ? {archive_filter}
            GROUP BY c.id, c.title, c.created_at, c.updated_at
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append(ConversationResponse(
                id=row[0],
                title=row[1],
                created_at=row[2],
                updated_at=row[3],
                message_count=row[4],
                last_message=None,
            ))
        return results

    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[ConversationDetailResponse]:
        """Récupère une conversation avec tous ses messages."""
        conn = self._get_conn()
        conv_row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()

        if not conv_row:
            conn.close()
            return None

        msg_rows = conn.execute(
            "SELECT id, role, content, sql_query, formatted_response, timestamp FROM conversation_messages WHERE conversation_id = ? ORDER BY timestamp ASC",
            (conversation_id,),
        ).fetchall()
        conn.close()

        messages = []
        for r in msg_rows:
            fr = None
            if r[4]:
                try:
                    fr = json.loads(r[4])
                except (json.JSONDecodeError, TypeError):
                    pass
            messages.append(
                MessageResponse(id=r[0], role=r[1], content=r[2], sql_query=r[3], formatted_response=fr, timestamp=r[5])
            )

        return ConversationDetailResponse(
            id=conv_row[0],
            title=conv_row[1],
            created_at=conv_row[2],
            updated_at=conv_row[3],
            messages=messages,
        )

    def update_conversation(self, conversation_id: str, user_id: str, title: Optional[str] = None, is_archived: Optional[bool] = None) -> bool:
        """Met à jour le titre ou archive une conversation."""
        conn = self._get_conn()
        # Vérifier que la conversation appartient à l'utilisateur
        exists = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if not exists:
            conn.close()
            return False

        if title is not None:
            conn.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?", (title, datetime.now(), conversation_id))
        if is_archived is not None:
            conn.execute("UPDATE conversations SET is_archived = ?, updated_at = ? WHERE id = ?", (is_archived, datetime.now(), conversation_id))
        conn.close()
        return True

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Supprime une conversation et tous ses messages."""
        conn = self._get_conn()
        exists = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if not exists:
            conn.close()
            return False

        conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.close()
        return True

    def get_recent_messages(self, conversation_id: str, limit: int = 5) -> List[dict]:
        """Récupère les N derniers messages d'une conversation (pour la mémoire agent)."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT role, content, sql_query, timestamp
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (conversation_id, limit)).fetchall()
        conn.close()

        messages = []
        for r in reversed(rows):  # ordre chronologique
            messages.append({
                "role": r[0],
                "content": r[1],
                "sql_query": r[2],
                "timestamp": r[3].isoformat() if r[3] else "",
            })
        return messages
