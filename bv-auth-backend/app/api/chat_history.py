import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.chat_history import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
)
from app.services.chat_history_service import ChatHistoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Singleton du service
_chat_history_service: ChatHistoryService = None


def get_chat_history_service() -> ChatHistoryService:
    global _chat_history_service
    if _chat_history_service is None:
        _chat_history_service = ChatHistoryService(db_path=settings.DATABASE_PATH)
    return _chat_history_service


@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    limit: int = 50,
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Liste toutes les conversations de l'utilisateur connecté."""
    return service.get_user_conversations(
        user_id=str(current_user.id),
        limit=limit,
        include_archived=include_archived,
    )


@router.post("", status_code=201)
def create_conversation(
    body: ConversationCreate,
    current_user: User = Depends(get_current_user),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Crée une nouvelle conversation."""
    conversation_id = service.create_conversation(
        user_id=str(current_user.id),
        title=body.title,
    )
    return {"id": conversation_id}


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Récupère une conversation avec tous ses messages."""
    conv = service.get_conversation(conversation_id, user_id=str(current_user.id))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return conv


@router.patch("/{conversation_id}")
def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Met à jour le titre ou archive une conversation."""
    success = service.update_conversation(
        conversation_id=conversation_id,
        user_id=str(current_user.id),
        title=body.title,
        is_archived=body.is_archived,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return {"status": "updated"}


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Supprime une conversation et tous ses messages."""
    success = service.delete_conversation(conversation_id, user_id=str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return {"status": "deleted"}
