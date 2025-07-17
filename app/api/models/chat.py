from pydantic import BaseModel, Field
from typing import Optional, List

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation history")
    force_web_search: bool = Field(False, description="If True, forces a web search regardless of the message content")

class ChatResponse(BaseModel):
    intent: str = Field(..., description="The determined intent of the message")
    message: str = Field(..., description="The response message")
    needs_clarification: bool = Field(False, description="Whether clarification is needed")
    clarification_questions: List[str] = Field(default_factory=list, description="List of clarification questions if needed")
