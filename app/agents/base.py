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
        current_agent = state.get("current_agent", "")
        messages = state.get("messages", [])
        last_message = messages[-1].get("content", "").lower() if messages else ""
        
        # Check for greeting message
        greeting_phrases = {"hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"}
        is_greeting = any(phrase in last_message for phrase in greeting_phrases)
        
        if is_greeting:
            state["response"] = (
                "Hello! I'm your AI assistant. How can I help you today?\n\n"
                "I can help you with:\n"
                "- Answering questions about your documents\n"
                "- Searching the web for information\n"
                "- And much more!"
            )
            state["follow_up_questions"] = [
                "What would you like to know?",
                "How can I assist you today?",
                "Would you like to search for something specific?"
            ]
            return state
            
        if not search_results:
            state["response"] = "I couldn't find any relevant information. Could you please provide more details or try a different query?"
            state["needs_clarification"] = True
            state["clarification_questions"] = [
                "Would you like me to try a different search?",
                "Could you provide more specific details about what you're looking for?"
            ]
            return state
            
        formatted_results = []
        
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
                    f"{i}. **{title}**\n"
                    f"{snippet}\n"
                    f"[Read more]({link})\n"
                )
            
            if formatted_results:
                state["response"] = "Here's what I found:\n\n" + "\n".join(formatted_results)
                state["follow_up_questions"] = [
                    "Would you like me to search for more information?",
                    "Is there anything specific you'd like to know more about?"
                ]
            else:
                state["response"] = "I couldn't find any relevant information. Would you like me to try a different search?"
                state["needs_clarification"] = True
        else:
            # Format PDF search results
            for i, result in enumerate(search_results[:3], 1):
                text = result.get("text", "").strip()
                source = result.get("metadata", {}).get("source", "Document")
                page = result.get("metadata", {}).get("page", "")
                
                # Truncate long text
                if len(text) > 200:
                    text = text[:200] + "..."
                    
                source_info = f"{source} (page {page})" if page else source
                formatted_results.append(f"{i}. **From {source_info}**: {text}")
            
            if formatted_results:
                state["response"] = "Here's what I found in the documents:\n\n" + "\n\n".join(formatted_results)
            else:
                state["response"] = "I couldn't find any relevant information in the documents. Would you like me to search the web instead?"
                state["needs_clarification"] = True
                state["clarification_questions"] = [
                    "Would you like me to search the web for this information?",
                    "Would you like to try a different query?"
                ]
        
        return state
