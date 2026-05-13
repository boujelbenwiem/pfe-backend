# backend/app/api/chat.py
# Endpoint POST /chat — point d'entrée pour l'interface

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from app.agents.orchestrator import run_pipeline, build_initial_state
from app.core.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    intention: Optional[str] = None
    output_type: Optional[str] = None          # "text" | "table" | "chart"
    sql_query: Optional[str] = None
    filters_applied: Optional[list] = None     # filtres MCP appliques (ex: shop_id)
    formatted_response: Optional[Any] = None   # structure varies by output_type
    access_denied: Optional[bool] = None
    execution_error: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Execute the multi-agent pipeline for a user question.

    The authenticated user's role and store are taken from the JWT token —
    no need to pass them in the request body.
    """
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="La question ne peut pas être vide.")

    try:
        state = build_initial_state(
            question=request.question,
            user_id=str(current_user.id),
            user_role=current_user.role,
            user_shop_id=current_user.store_id,
        )
        result = run_pipeline(state, session_id=str(current_user.id))
    except Exception as exc:
        logger.exception("Pipeline error for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Erreur interne du pipeline.")

    return ChatResponse(
        intention=result.get("intention"),
        output_type=result.get("output_type"),
        sql_query=result.get("sql_query"),
        filters_applied=result.get("filters_applied"),
        formatted_response=result.get("formatted_response"),
        access_denied=result.get("access_denied"),
        execution_error=result.get("execution_error"),
        error=result.get("error"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
