"""PDF Query Agent implementation."""
from typing import Dict, Any

from .base import BaseAgent

class PDFQueryAgent(BaseAgent):
   
    
    def __init__(self, vector_store):
     
        super().__init__("pdf_query_agent")
        self.vector_store = vector_store
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
     



        query = state.get("messages", [{}])[-1].get("content", "")
        search_results = self.vector_store.search_similar(
            query=query,
            limit=3,
            min_similarity=0.5
        )

        state["search_results"] = search_results
        state["current_agent"] = self.name    
        return state
