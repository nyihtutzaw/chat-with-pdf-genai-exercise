"""Web Search Agent implementation."""
from typing import Dict, Any

from .base import BaseAgent
from ..services.web_search import web_search_service

class WebSearchAgent(BaseAgent):
    """Agent for handling web searches."""
    
    def __init__(self):
        """Initialize the web search agent."""
        super().__init__("web_search_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process web search query.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with search results
        """
        query = state.get("messages", [{}])[-1].get("content", "")
        search_results = await web_search_service.search(query)
        
        state["search_results"] = search_results
        state["current_agent"] = self.name
        return state
