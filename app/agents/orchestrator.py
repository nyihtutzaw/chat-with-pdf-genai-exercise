"""Orchestrator for multi-agent workflow.

This module implements a LangGraph-based orchestrator that coordinates multiple agents
to process user queries based on their intent. The workflow includes intent classification,
document querying, web search, and response generation.
"""
import logging
from typing import Dict, Any, Callable, Awaitable

from langgraph.graph import Graph, END

from .base import PDFQueryAgent, WebSearchAgent, ResponseAgent
from ..services.langchain_router import LangChainRouter, IntentType
from ..config import LLMConfig

# Configure logging
logger = logging.getLogger(__name__)

# Type aliases for better code readability
AgentNodeFunc = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

class AgentOrchestrator:
    """Orchestrates the multi-agent workflow."""
    
    def __init__(self, vector_store):
        """Initialize with required agents and workflow."""
        self.vector_store = vector_store
        self.agents = {
            "pdf_query": PDFQueryAgent(vector_store),
            "web_search": WebSearchAgent(),
            "response": ResponseAgent()
        }
        # Initialize the router with LLM config
        self.router = LangChainRouter(LLMConfig())
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> Graph:
        """Create and compile the LangGraph workflow.
        
        The workflow consists of the following nodes:
        - classify_intent: Determines the intent of the user's message
        - pdf_query: Handles PDF document queries
        - web_search: Handles web search queries
        - response: Formats and returns the final response
        
        Returns:
            A compiled LangGraph workflow
        """
        workflow = Graph()
        
        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("pdf_query", self._create_agent_node("pdf_query"))
        workflow.add_node("web_search", self._create_agent_node("web_search"))
        workflow.add_node("response", self._create_agent_node("response"))
        
        # Define routing function that returns the next node based on intent
        def route_after_classify(state: Dict[str, Any]) -> str:
            intent = state.get("intent", "response")
            if intent == "pdf":
                return "pdf_query"
            elif intent == "web":
                return "web_search"
            return "response"  # Default to response node
        
        # Add edges from classify_intent to the appropriate nodes
        workflow.add_conditional_edges(
            "classify_intent",
            route_after_classify
        )
        
        # Add edges from agent nodes to the response node
        workflow.add_edge("pdf_query", "response")
        workflow.add_edge("web_search", "response")
        workflow.add_edge("response", END)
        
        # Set the entry point
        workflow.set_entry_point("classify_intent")
        
        # Compile the workflow
        return workflow.compile()
    
    async def _classify_intent_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Node function for intent classification using LangChain router.
        
        This node:
        1. Extracts the latest user message
        2. Uses the router to determine intent
        3. Updates the state with intent and metadata
        4. Ensures all required fields are present in the state
        
        Args:
            state: The current conversation state
            
        Returns:
            Updated state with intent classification
        """
        # Ensure messages exist and get the latest user message
        messages = state.get("messages", [])
        query = messages[-1].get("content", "") if messages else ""
        
        # Initialize default values
        state.setdefault("intent", "response")
        state.setdefault("metadata", {})
        state["metadata"].setdefault("intent_classification", {})
        
        try:
            # Get the routing decision from the router
            routing_decision = await self.router.route_query(query)
            
            # Map the router's intent to our node's intent
            if routing_decision.intent == IntentType.PDF_QUERY:
                state["intent"] = "pdf"
            elif routing_decision.intent == IntentType.WEB_SEARCH:
                state["intent"] = "web"
            elif routing_decision.intent == IntentType.GREETING:
                state["intent"] = "response"  # Greetings go straight to response
            else:
                state["intent"] = "response"
            
            # Store detailed classification info in metadata
            state["metadata"]["intent_classification"] = {
                "detected_intent": routing_decision.intent.value,
                "confidence": getattr(routing_decision, 'confidence', 1.0),
                "needs_clarification": getattr(routing_decision, 'needs_clarification', False),
                "source": "llm_router"
            }
            
            # If clarification is needed, update response fields
            if getattr(routing_decision, 'needs_clarification', False):
                state["needs_clarification"] = True
                state["clarification_questions"] = getattr(
                    routing_decision, 
                    'clarification_questions', 
                    ["Could you please clarify your request?"]
                )
            
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error in intent classification: %s", str(e))
            # Fallback to simple keyword matching if router fails
            query_lower = query.lower()
            if any(keyword in query_lower for keyword in ["search", "find", "look up"]):
                state["intent"] = "web"
            elif any(keyword in query_lower for keyword in ["document", "pdf", "file"]):
                state["intent"] = "pdf"
            else:
                state["intent"] = "response"
                
            # Update metadata to indicate fallback was used
            state["metadata"]["intent_classification"] = {
                "detected_intent": "fallback_keyword_matching",
                "confidence": 0.5,
                "needs_clarification": False,
                "source": "fallback",
                "error": str(e)
            }
        
        # Ensure all required fields are present in the state
        state.setdefault("needs_clarification", False)
        state.setdefault("clarification_questions", [])
        state.setdefault("follow_up_questions", [])
        state.setdefault("search_results", [])
                
        return state
    
    # Removed _route_by_intent - replaced with inline route_after_classify function in _create_workflow
    
    def _create_agent_node(self, agent_name: str):
        """Create a node function for the given agent.
        
        This factory function creates an async node function that:
        1. Processes the state using the specified agent
        2. Ensures all required fields are present in the result
        3. Handles errors gracefully
        
        Args:
            agent_name: The name of the agent to create a node for
            
        Returns:
            An async function that processes the state using the specified agent
        """
        async def node_func(state: Dict[str, Any]) -> Dict[str, Any]:
            # Ensure we have a copy of the state to modify
            result = dict(state)
            
            try:
                # Process the state with the appropriate agent
                logger.info("Processing with agent: %s", agent_name)
                agent_result = await self.agents[agent_name].process(state)
                
                # Update the result with the agent's output
                if isinstance(agent_result, dict):
                    result.update(agent_result)
                
                # Ensure metadata exists and track which agent processed this
                result.setdefault("metadata", {})
                result["metadata"].update({
                    "processed_by": agent_name,
                    "processing_steps": result["metadata"].get("processing_steps", []) + [agent_name]
                })
                
                # Ensure all required fields are present
                result.setdefault("intent", state.get("intent", "response"))
                result.setdefault("needs_clarification", False)
                result.setdefault("clarification_questions", [])
                result.setdefault("follow_up_questions", [])
                result.setdefault("search_results", [])
                
                # For response agent, ensure we have a response field
                if agent_name == "response" and "response" not in result:
                    result["response"] = "I've processed your request."
                
                return result
                
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Error in agent node %s: %s", agent_name, str(e), exc_info=True)
                
                # Return a safe response with error information
                result.update({
                    "response": f"An error occurred while processing your request with {agent_name}.",
                    "metadata": {
                        "error": str(e),
                        "agent": agent_name,
                        "success": False,
                        "processing_steps": result.get("metadata", {}).get("processing_steps", []) + [f"{agent_name}_error"]
                    },
                    "needs_clarification": True,
                    "clarification_questions": [
                        f"I encountered an error with the {agent_name} agent. Would you like to try again?"
                    ]
                })
                return result
                
        return node_func
    
    async def process_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """Process a user message through the agent workflow.
        
        This method:
        1. Initializes the conversation state
        2. Runs the workflow with the user's message
        3. Processes the result to ensure all required fields are present
        4. Returns a properly formatted response
        
        Args:
            message: The user's message
            session_id: The conversation session ID
            
        Returns:
            A dictionary containing the response data with all required fields for ChatResponse
        """
        # Initialize the state with user message and default values
        state = {
            "messages": [{"role": "user", "content": message}],
            "session_id": session_id,
            "intent": "response",
            "needs_clarification": False,
            "clarification_questions": [],
            "follow_up_questions": [],
            "search_results": [],
            "metadata": {
                "session_id": session_id,
                "processing_steps": ["started"]
            }
        }
        
        # Run the workflow
        try:
            logger.info(f"Processing message with workflow: {message[:100]}...")
            result = await self.workflow.ainvoke(state)
            
            # Ensure we have a valid response
            response = result.get("response", "I'm not sure how to respond to that.")
            if not response:
                response = "I don't have a response for that. Could you please rephrase?"
            
            # Format search results if available
            search_results = result.get("search_results", [])
            if search_results and isinstance(search_results, list) and len(search_results) > 0:
                if not response or response == "I'm not sure how to respond to that.":
                    response = "Here's what I found:"
            
            # Normalize intent
            intent = result.get("intent", "response")
            if intent == "pdf":
                intent = "pdf_query"
            elif intent == "web":
                intent = "web_search"
            
            # Ensure all required fields are present
            needs_clarification = bool(result.get("needs_clarification", False))
            clarification_questions = result.get("clarification_questions", [])
            follow_up_questions = result.get("follow_up_questions", [])
            
            # Get conversation history, ensuring it's a list of message dicts
            conversation_history = []
            if "messages" in result and isinstance(result["messages"], list):
                conversation_history = [
                    msg for msg in result["messages"] 
                    if isinstance(msg, dict) and "role" in msg and "content" in msg
                ]
            
            # Prepare metadata
            metadata = {
                "agent_used": result.get("current_agent", "unknown"),
                "session_id": session_id,
                "intent": intent,
                "success": True,
                **result.get("metadata", {})
            }
            
            # Log successful processing
            logger.info(f"Successfully processed message with intent: {intent}")
            
            return {
                "intent": intent,
                "message": response,
                "session_id": session_id,
                "search_results": search_results if isinstance(search_results, list) else [],
                "needs_clarification": needs_clarification,
                "clarification_questions": clarification_questions if isinstance(clarification_questions, list) else [],
                "follow_up_questions": follow_up_questions if isinstance(follow_up_questions, list) else [],
                "conversation_history": conversation_history,
                "metadata": metadata
            }
        except Exception as e:
            logger.error(f"Error in agent workflow: {str(e)}", exc_info=True)
            return {
                "intent": "error",
                "message": "I encountered an error processing your request. Please try again.",
                "session_id": session_id,
                "search_results": [],
                "needs_clarification": False,
                "clarification_questions": [],
                "follow_up_questions": [],
                "conversation_history": [],
                "metadata": {
                    "error": str(e),
                    "session_id": session_id
                }
            }
