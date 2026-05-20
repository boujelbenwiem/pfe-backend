from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional
from datetime import datetime
from uuid import UUID


class MessageCreate(BaseModel):
    role: str 
    content: str
    sql_query: Optional[str] = None
    formatted_response: Optional[Any] = None

class ConversationCreate(BaseModel):
    title: Optional[str] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    sql_query: Optional[str] = None
    formatted_response: Optional[Any] = None
    timestamp: datetime

class ConversationResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message: Optional[MessageResponse] = None

class ConversationDetailResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []