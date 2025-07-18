"""Base agent implementation."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from ..core.vector_store import VectorStore
from ..services.web_search import web_search_service

class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the input state and return updated state."""
        pass

class PDFQueryAgent(BaseAgent):
    """Agent for handling PDF document queries."""
    
    def __init__(self, vector_store: VectorStore):
        super().__init__("pdf_query_agent")
        self.vector_store = vector_store
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF query."""
        query = state.get("messages", [{}])[-1].get("content", "")
        search_results = self.vector_store.search_similar(
            query=query,
            limit=3,
            min_similarity=0.3
        )
        
        state["search_results"] = search_results
        state["current_agent"] = self.name
        return state

class WebSearchAgent(BaseAgent):
    """Agent for handling web searches."""
    
    def __init__(self):
        super().__init__("web_search_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process web search query."""
        query = state.get("messages", [{}])[-1].get("content", "")
        search_results = await web_search_service.search(query)
        
        state["search_results"] = search_results
        state["current_agent"] = self.name
        return state

class ResponseAgent(BaseAgent):
    """Agent for formatting responses."""
    
    def __init__(self):
        super().__init__("response_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Format the final response."""
        search_results = state.get("search_results", [])
        
        if not search_results:
            state["response"] = "I couldn't find any relevant information."
            return state
            
        formatted_results = []
        for i, result in enumerate(search_results[:3], 1):
            text = result.get("text", "").strip()
            source = result.get("metadata", {}).get("source", "Unknown")
            formatted_results.append(f"{i}. {source}: {text}")
        
        state["response"] = "\n\n".join(formatted_results)
        return state
