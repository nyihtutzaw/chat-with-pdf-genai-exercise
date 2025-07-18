"""Multi-agent system implementation using LangGraph."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class AgentState(BaseModel):
    """State for the agent workflow."""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    current_agent: Optional[str] = None
    search_results: List[Dict] = Field(default_factory=list)
    response: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
