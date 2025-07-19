"""Orchestrator for multi-agent workflow.

This module implements a LangGraph-based orchestrator that coordinates multiple agents
to process user queries based on their intent. The workflow includes intent classification,
document querying, web search, and response generation.
"""
import logging
import re
from typing import Any, Callable, Awaitable, Dict, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import Graph, END

from app.agents.pdf_query_agent import PDFQueryAgent
from app.agents.web_search_agent import WebSearchAgent
from app.agents.response_agent import ResponseAgent
from app.config.llm import LLMConfig

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
        # Initialize the LLM config
        self.llm_config = LLMConfig()
        self.intent_classifier = self._create_intent_classifier()
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
            # If we already have a response (e.g., from greeting), go to response node
            if state.get("response"):
                return "response"
                
            intent = state.get("intent", "response")

            # If force_web_search is True, go directly to web search
            metadata = state.get("metadata", {})
            if metadata.get("force_web_search", False):
                return "web_search"


            # Route based on intent
            if intent == "pdf":
                return "pdf_query"
            elif intent == "web":
                return "web_search"
                
            return "response"  # Default to response node
            
        def route_after_pdf(state: Dict[str, Any]) -> str:
            # If we have search results, go to response
            search_results = state.get("search_results", [])
            if search_results:
                return "response"
                
            state["intent"] = "web"
            state["metadata"]["intent_classification"] = {
                "detected_intent": "web_search",
                "confidence": 0.8,
                "needs_clarification": False,
                "source": "pdf_search_fallback"
            }
            
            return "web_search"
        
        # Add edges from classify_intent to the appropriate nodes
        workflow.add_conditional_edges(
            "classify_intent",
            route_after_classify
        )
        
        # Add conditional edge after PDF query to handle fallback to web search
        workflow.add_conditional_edges(
            "pdf_query",
            route_after_pdf
        )
        
        # Add edges from agent nodes to the response node
        workflow.add_edge("web_search", "response")
        workflow.add_edge("response", END)
        
        # Set the entry point
        workflow.set_entry_point("classify_intent")
        
        # Compile the workflow
        return workflow.compile()
    
    def _initialize_state(self, state: Dict[str, Any]) -> tuple:
        """Initialize and extract necessary values from the state."""
        messages = state.get("messages", [{}])
        last_message = messages[-1] if messages else {}
        query = last_message.get("content", "")
        metadata = last_message.get("metadata", {})
        
        # Initialize default values
        state.setdefault("intent", "response")
        state.setdefault("metadata", {})
        state["metadata"].setdefault("intent_classification", {})
        
        return state, query, metadata
    
    
    def _apply_keyword_fallback(self, state: Dict[str, Any], query: str) -> None:
        """Apply keyword-based intent classification as a fallback."""
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in ["search", "find", "look up"]):
            state["intent"] = "web"
        elif any(keyword in query_lower for keyword in ["document", "pdf", "file"]):
            state["intent"] = "pdf"
        else:
            state["intent"] = "response"
    
    def _ensure_dict_state(self, state: Any) -> Dict[str, Any]:
        """Ensure the state is a dictionary and return a mutable copy."""
        if isinstance(state, dict):
            return dict(state)
            
        try:
            if hasattr(state, '_asdict'):
                return state._asdict()
            if isinstance(state, (tuple, list)):
                return dict(enumerate(state))
            return dict(state) if state is not None else {}
        except (TypeError, ValueError):
            return {'_state': state}

    def _initialize_intent_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize the state dictionary with required fields."""
        state = self._ensure_dict_state(state)
        
        # Ensure metadata exists and is mutable
        state['metadata'] = self._ensure_dict_state(state.get('metadata', {}))
        
        # Initialize required state fields if they don't exist
        state.setdefault('messages', [])
        state.setdefault('intent', 'response')
        state.setdefault('needs_clarification', False)
        state.setdefault('clarification_questions', [])
        state.setdefault('search_results', [])
        
        # Initialize any additional state fields
        return self._initialize_state(state)[0]  # Only return the state, not the tuple
    
    
    def _create_intent_classifier(self):
        """Create the intent classification chain."""
        intent_prompt = """
        You are an intent classification system for a chat application that helps users with PDF documents and general knowledge.
        
        Classify the following message into one of these intents:
        - greeting: For greetings like hello, hi, hey, good morning/afternoon/evening, what's up, etc.
        - pdf_query: For general knowledge questions related to academic papers
        - web_search: For general knowledge questions
        - follow_up: When the message is a follow-up question or reference to previous conversation
        - clarification_needed: When the intent is unclear
        
        Conversation History:
        {conversation_history}
        
        Message to classify: {message}
        
        If this is a follow-up question (e.g., using pronouns like 'he', 'she', 'it', 'they', or referring to something previously mentioned), 
        classify it as 'follow_up' and include the context from the conversation that it refers to.
        
        Respond with a JSON object containing:
        - intent: The classified intent (greeting, pdf_query, web_search, follow_up, or clarification_needed)
        - confidence: A number between 0 and 1 indicating your confidence
        - reasoning: A brief explanation of your classification
        - context: If this is a follow-up, include the specific context from previous messages that this refers to
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", intent_prompt),
            ("human", "{message}")
        ])
        
        # Create a chain that properly formats the input with conversation history
        chain = ({
            "message": lambda x: x["message"],
            "conversation_history": lambda x: x.get("conversation_history", "No previous conversation"),
        } | prompt | self.llm_config.llm | JsonOutputParser())
        
        return chain
        
    def _detect_ambiguity(self, message: str) -> Tuple[bool, str, str]:
        """Check if the message is ambiguous using comprehensive patterns.
        
        Returns:
            tuple[bool, str, str]: A tuple containing:
                - bool: True if the message is ambiguous, False otherwise
                - str: The clarification message to show to the user
                - str: An example of how to rephrase the question
        """
        # Check for short or incomplete messages first
        if len(message.strip().split()) <= 3 and not any(p in message.lower() for p in ['hi', 'hello', 'hey']):
            return True, "Your question seems a bit brief. Could you provide more details?", \
                   "For example, instead of 'How to?', try 'How do I implement a neural network in PyTorch for image classification?'"
        
        ambiguity_patterns = [
            # Vague quantity questions
            {
                'pattern': r'\b(how many|how much|what (?:is|are) (?:the )?(?:number|amount|quantity))\b.*\b(enough|sufficient|good|required|necessary|adequate|appropriate|suitable|decent|reasonable|acceptable|satisfactory|optimal|ideal|recommended|suggested)\b',
                'clarification': "I'm not sure I understand your question. Could you explain what you mean by 'enough' in this context?",
                'example': "For example, instead of 'How many examples are enough for good accuracy?', try 'How many training examples do I need to achieve 95% accuracy on the test set for sentiment analysis?'"
            },
            # Vague quality questions
            {
                'pattern': r'\b(is|are|does|do|will|would|can|could|should|might|may)\b.*\b(bad|worse|faster|slower|more accurate|less accurate|more efficient|less efficient|more effective|less effective|superior|inferior|preferable|optimal)\b',
                'clarification': "I'm not sure I understand your question. Could you explain what you mean by 'good/bad' in this context?",
                'example': "For example, instead of 'Is this model good?', try 'How does this model's 90% accuracy compare to state-of-the-art on the IMDB dataset?'"
            },
            # Vague comparison questions
            {
                'pattern': r'\b(which|what) (is|are) (better)\b',
                'clarification': "To help you compare effectively, could you explain what you mean by 'better' in this context?",
                'example': "For example, instead of 'Which model is better?', try 'Which model has higher F1 score on small text classification tasks with limited training data?'"
            },
            # Vague requests for information
            {
                'pattern': r'\b(tell me about|what (?:is|are)|explain|describe|how (?:do|does)|what (?:do|does)|what (?:is|are) (?:the|a|an)|can you (?:tell|explain|describe))\b',
                'clarification': "I'd be happy to help! Could you be more specific about what you'd like to know?",
                'example': "For example, instead of 'Tell me about transformers', try 'What are the key components of the transformer architecture in NLP?'"
            }
        ]

        for pattern_info in ambiguity_patterns:
            if re.search(pattern_info['pattern'], message, re.IGNORECASE):
                return True, pattern_info['clarification'], pattern_info['example']

        return False, "", ""


    async def _classify_intent_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Node function for intent classification using LLM.
        
        This node:
        1. If force_web_search is True, goes to web search
        2. Otherwise, checks for ambiguous questions
        3. Uses LLM to classify the intent
           - greeting: Returns a greeting response
           - pdf_query: Routes to PDF query handler
           - web_search: Routes to web search
           - follow_up: Handles follow-up questions using conversation context
           - clarification_needed: Asks for clarification
        """
        # Initialize state with required fields
        state = self._initialize_intent_state(state)
        
        try:
            # Get the conversation history and latest message
            messages = state.get("messages", [])
            if not messages:
                raise ValueError("No messages in conversation")
                
            last_message = messages[-1]
            query = last_message.get("content", "").strip()
            metadata = last_message.get("metadata", {})
            
            # Prepare conversation history for context
            conversation_history = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
                for msg in messages[:-1]  # Exclude the current message
            )

           


               
            
           

            # 1. Check for force_web_search flag first - this takes highest priority
            if metadata.get("force_web_search", False):
                state["intent"] = "web"
                state["metadata"]["intent_classification"] = {
                    "detected_intent": "web_search",
                    "confidence": 1.0,
                    "needs_clarification": False,
                    "source": "force_web_search_flag"
                }
                return state
            
            # 2. Use LLM to detect if the query is requesting a web search
            try:
                # Create a prompt to detect web search intent
                web_search_prompt = f"""
                Determine if the following user query is requesting to search the web for information.
                A query is considered a web search request if it explicitly asks to search, look up, 
                or find information online, on the internet, or using a search engine.
                
                Query: "{query}"
                
                Respond with a JSON object containing:
                - is_web_search: boolean indicating if this is a web search request
                - confidence: float between 0 and 1 indicating confidence
                - reasoning: brief explanation of the decision
                """
                
                # Call the LLM to analyze the query
                response = await self.llm_config.llm.ainvoke(web_search_prompt)
                
                # Parse the response
                try:
                    import json
                    result = json.loads(response.content)
                    
                    if result.get('is_web_search', False):
                        state["intent"] = "web"
                        state["metadata"]["intent_classification"] = {
                            "detected_intent": "web_search",
                            "confidence": min(float(result.get('confidence', 0.8)), 1.0),
                            "needs_clarification": False,
                            "source": "llm_web_search_detection",
                            "reasoning": result.get('reasoning', 'Detected as web search request by LLM')
                        }
                        return state
                        
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse LLM response for web search detection: {e}")
                    # Continue with normal flow if parsing fails
                    
            except Exception as e:
                logger.error(f"Error during web search detection: {e}", exc_info=True)
                # Continue with normal flow if there's an error
                
            
            
            # 3. Classify intent using the intent classifier with conversation history

         

            classification = await self.intent_classifier.ainvoke({
                "message": query,
                "conversation_history": conversation_history
            })

     
            
            # Update state based on the classified intent
            intent = classification.get("intent", "pdf_query")
    

            state["metadata"]["intent_classification"] = {
                "detected_intent": intent,
                "confidence": classification.get("confidence", 1.0),
                "needs_clarification": intent == "clarification_needed",
                "reasoning": classification.get("reasoning", ""),
                "source": "llm_intent_classifier",
                "context": classification.get("context", "")
            }


            if (intent != "follow_up"):
             # 3. Check for ambiguous questions, but be very permissive with follow-ups
                is_ambiguous, clarification_msg, example = self._detect_ambiguity(query)
                if is_ambiguous:
                    state["intent"] = "response"
                    state["response"] = f"{clarification_msg}\n\n{example}"
                    state["metadata"]["intent_classification"] = {
                        "detected_intent": "clarification_needed",
                        "confidence": 0.9,
                        "needs_clarification": True,
                        "is_ambiguous": True,
                        "reasoning": "Question was detected as ambiguous",
                        "source": "ambiguity_detector"
                    }
                    return state
            

         
     
          
            
            # Handle greeting intent
            if intent == "greeting":
                state["intent"] = "response"
                state["response"] = "Hello! How can I assist you today?"
                return state
                
            # Handle PDF query intent
            if intent == "pdf_query":
                state["intent"] = "pdf"
                state["metadata"]["original_query"] = query
                return state
                
            # Handle follow-up questions
            if intent == "follow_up":

                print("here it is ")

                context = classification.get("context", "")
                if context:
                    # If we have context, use it to modify the query
                    modified_query = f"{context} {query}"
                    state["metadata"]["original_query"] = modified_query
                    
                    # For follow-ups about people, places, or things previously searched, default to web search
                    if any(term in query.lower() for term in ["he", "she", "it", "they", "that", "this", "the"]):
                        state["intent"] = "web"
                        # Force web search to get fresh information
                        state["metadata"]["force_web_search"] = True
                        return state
                    
                    # For other follow-ups, check the context
                    if any(term in context.lower() for term in ["search", "find", "look up"]):
                        state["intent"] = "web"
                    else:
                        state["intent"] = "pdf"
                    return state
                
            # Default to web search for other intents
            state["intent"] = "web" if intent == "web_search" else "pdf"
            
            # Ensure all required fields are present
            for field in ["needs_clarification", "clarification_questions", "search_results"]:
                state.setdefault(field, [] if field.endswith('s') else False)
            
            return state
            
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Unexpected error in _classify_intent_node: %s",
                str(e),
                exc_info=True
            )
            return self._handle_classification_error(
                state, 
                query if 'query' in locals() else ""
            )
            
    def _handle_classification_error(self, state: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Handle errors during intent classification."""
        state["intent"] = "response"
        state["needs_clarification"] = True
        state["clarification_questions"] = [
            "I'm having trouble understanding your request. Could you please rephrase?"
        ]
        
        # Apply keyword fallback if possible
        if query:
            self._apply_keyword_fallback(state, query)
            
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
    
    async def process_message(self, message: str, session_id: str, force_web_search: bool = False) -> Dict[str, Any]:
       
    
        
        """Process a user message through the agent workflow.
        
        This method:
        1. Initializes the conversation state
        2. Runs the workflow with the user's message
        3. Processes the result to ensure all required fields are present
        4. Returns a properly formatted response
        
        Args:
            message: The user's message
            session_id: The conversation session ID
            force_web_search: If True, forces a web search regardless of message content
            
        Returns:
            A dictionary containing the response data with all required fields for ChatResponse
        """
        # Initialize the state with user message and default values

       
        state = {
            "messages": [{"role": "user", "content": message, "metadata": {}}],
            "session_id": session_id,
            "intent": "response",
            "needs_clarification": False,
            "clarification_questions": [],
       
            "search_results": [],
            "metadata": {
                "session_id": session_id,
                "processing_steps": ["started"],
                "force_web_search": force_web_search
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
               
                "conversation_history": [],
                "metadata": {
                    "error": str(e),
                    "session_id": session_id
                }
            }
