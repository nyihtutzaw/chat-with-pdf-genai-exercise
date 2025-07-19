"""Response Agent implementation."""
from typing import Dict, Any

from .base import BaseAgent

class ResponseAgent(BaseAgent):
    
    def __init__(self):
        super().__init__("response_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
      
       
        if "response" in state and state["response"]:
            return state
            
        metadata = state.get("metadata", {})
        intent_classification = metadata.get("intent_classification", {})
        is_follow_up = intent_classification.get("is_follow_up", False)
        
        if is_follow_up and not state.get("search_results"):
            state["response"] = (
                "I'm having trouble finding more information about that. "
                "Could you rephrase your question or provide more context?"
            )
            return state
            
        formatted_results = []
        search_results = state.get("search_results", [])
        current_agent = state.get("current_agent", "")
        
        if current_agent == "web_search_agent":
            
            for i, result in enumerate(search_results[:3], 1):
                title = result.get("title", "No title").strip()
                snippet = result.get("snippet", "No description available").strip()
                link = result.get("link", "#")
                
                snippet = self._clean_snippet(snippet)
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                    
                formatted_results.append(
                    f"{i}. {title}\n"
                    f"   URL: {link}\n"
                    f"   Snippet: {snippet}\n"
                )
                
        elif current_agent == "pdf_query_agent":
            
            for i, result in enumerate(search_results[:3], 1):
                text = result.get("text", "").strip()
                source = result.get("metadata", {}).get("source", "Document")
                page = result.get("metadata", {}).get("page", "")
                
                
                text = self._clean_snippet(text)
                if len(text) > 200:
                    text = text[:200] + "..."
                    
                formatted_results.append(
                    f"{i}. From {source} (Page {page}):\n"
                    f"   {text}\n"
                )
        
        
        if formatted_results:
            if is_follow_up:
                state["response"] = "Here's what I found about that:\n\n" + "\n".join(formatted_results)
            else:
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
        
    def _clean_snippet(self, text: str) -> str:
        if not text:
            return ""
        import re
        text = re.sub(r'\s+', ' ', text).strip()
        return text
