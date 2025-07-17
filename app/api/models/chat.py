from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class IntentType(str, Enum):
    GREETING = "greeting"
    PDF_QUERY = "pdf_query"
    WEB_SEARCH = "web_search"
    CLARIFICATION_NEEDED = "clarification_needed"

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="The user's message")
    session_id: Optional[str] = Field(
        None, 
        description="Optional session ID for maintaining conversation context"
    )
    force_web_search: bool = Field(
        False, 
        description="If True, forces a web search regardless of the message content"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the message"
    )

class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    intent: str = Field(..., description="The determined intent of the message")
    message: str = Field(..., description="The assistant's response")
    session_id: str = Field(..., description="The conversation session ID")
    needs_clarification: bool = Field(
        False, 
        description="Whether the response requires clarification"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="List of clarification questions if needed"
    )
    follow_up_questions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions"
    )
    conversation_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="The conversation history"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )

class ClearSessionResponse(BaseModel):
    """Response model for clear session endpoint."""
    status: str
    message: str
