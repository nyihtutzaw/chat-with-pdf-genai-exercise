"""Multi-agent system implementation using LangGraph."""
from typing import Dict, Any, List, Optional, TypeVar
from pydantic import BaseModel, Field

from .base import BaseAgent
from .pdf_query_agent import PDFQueryAgent
from .web_search_agent import WebSearchAgent
from .response_agent import ResponseAgent

# Type variable for agent classes
AgentType = TypeVar('AgentType', bound=BaseAgent)

__all__ = [
    'BaseAgent',
    'PDFQueryAgent',
    'WebSearchAgent',
    'ResponseAgent'
]
