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


        

        """Process PDF query.
        
        If no results are found and should_try_web_after_pdf is True, 
        the state will be updated to trigger a web search.
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

class WebSearchAgent(BaseAgent):
    """Agent for handling web searches."""
    
    def __init__(self):
        super().__init__("web_search_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process web search query."""
        query = state.get("messages", [{}])[-1].get("content", "")

        print("web_search_agent query",query)

        search_results = await web_search_service.search(query)
        
        state["search_results"] = search_results
        state["current_agent"] = self.name
        return state

class ResponseAgent(BaseAgent):
    """Agent for formatting responses."""
    
    def __init__(self):
        super().__init__("response_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Format the final response.
        
        If the state already contains a response (e.g., from greeting in orchestrator),
        it will be returned as is. Otherwise, formats search results from either
        web search or PDF query.
        """
        # If we already have a response, just add follow-up questions and return
        if state.get("response"):
            state["follow_up_questions"] = [
                "What would you like to know?",
                "How can I assist you today?",
                "Is there something specific you'd like to ask?",
                "Would you like to search for something?"
            ]
            return state
            
        formatted_results = []
        search_results = state.get("search_results", [])
        current_agent = state.get("current_agent", "")
        
        if current_agent == "web_search_agent":
            # Format web search results
            for i, result in enumerate(search_results[:3], 1):
                title = result.get("title", "No title").strip()
                snippet = result.get("snippet", "No description available").strip()
                link = result.get("link", "#")
                
                # Truncate long snippets
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                    
                formatted_results.append(
                    f"{i}. {title}\n"
                    f"   URL: {link}\n"
                    f"   Snippet: {snippet}\n"
                )
                
        elif current_agent == "pdf_query_agent":
            # Format PDF query results
            for i, result in enumerate(search_results[:3], 1):
                text = result.get("text", "").strip()
                source = result.get("metadata", {}).get("source", "Document")
                page = result.get("metadata", {}).get("page", "")
                
                # Truncate long text
                if len(text) > 200:
                    text = text[:200] + "..."
                    
                formatted_results.append(
                    f"{i}. From {source} (Page {page}):\n"
                    f"   {text}\n"
                )
        
        # Add follow-up questions
        state["follow_up_questions"] = [
            "Can you provide more details about this?",
            "Would you like to search for something else?",
            "Is there anything specific you'd like to know more about?",
            "Would you like me to refine the search?"
        ]
        
        # Format the final response
        if formatted_results:
            state["response"] = "Here's what I found:\n\n" + "\n".join(formatted_results)
        else:
            state["response"] = (
                "I couldn't find any relevant information. "
                "Could you please provide more details or try a different query?"
            )
            state["needs_clarification"] = True
            state["clarification_questions"] = [
                "Would you like me to search the web for this information?",
                "Would you like to try a different query?"
            ]
        
        return state
