
from typing import List

from app.agents.state import AgentState
from app.core.config import settings


class AgentMemory:
    MAX_MEMORY_ENTRIES = 3

    def get_memory_context(self, state: AgentState) -> str:
        """Récupère les dernières discussions depuis la DB et les formate en contexte."""
        conversation_id = state.get("conversation_id")
        if not conversation_id:
            return ""

        
        from app.services.chat_history_service import ChatHistoryService

        service = ChatHistoryService(db_path=settings.DATABASE_PATH)
        messages = service.get_recent_messages(
            conversation_id=conversation_id,
            limit=self.MAX_MEMORY_ENTRIES * 2,  # user + assistant = 2 messages par échange
        )

        if not messages:
            return ""

        # Regrouper par paires (user question + assistant answer)
        context_parts = ["\n=== Mémoire de la conversation ===\n"]
        i = 0
        count = 0
        while i < len(messages) and count < self.MAX_MEMORY_ENTRIES:
            msg = messages[i]
            if msg["role"] == "user":
                question = msg["content"]
                answer = ""
                sql_query = None
                # Chercher la réponse assistant suivante
                if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                    answer = messages[i + 1]["content"]
                    sql_query = messages[i + 1].get("sql_query")
                    i += 2
                else:
                    i += 1
                context_parts.append(f"Question: {question}")
                context_parts.append(f"Réponse: {answer}")
                if sql_query:
                    context_parts.append(f"SQL: {sql_query}")
                context_parts.append("")
                count += 1
            else:
                i += 1

        if count == 0:
            return ""

        return "\n".join(context_parts)
        