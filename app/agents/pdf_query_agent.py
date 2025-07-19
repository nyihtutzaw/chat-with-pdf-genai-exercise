"""PDF Query Agent implementation."""
from typing import Dict, Any

from .base import BaseAgent

class PDFQueryAgent(BaseAgent):
    """Agent for handling PDF document queries."""
    
    def __init__(self, vector_store):
        """Initialize the PDF query agent.
        
        Args:
            vector_store: Vector store for document search
        """
        super().__init__("pdf_query_agent")
        self.vector_store = vector_store
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF query.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with search results
        """
        query = state.get("messages", [{}])[-1].get("content", "")
        search_results = self.vector_store.search_similar(
            query=query,
            limit=3,
            min_similarity=0.5
        )

        state["search_results"] = search_results
        state["current_agent"] = self.name    
        return state
