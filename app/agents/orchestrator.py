
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
   
    
    def __init__(self, vector_store):
        
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
       
       
        workflow = Graph()
        
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("pdf_query", self._create_agent_node("pdf_query"))
        workflow.add_node("web_search", self._create_agent_node("web_search"))
        workflow.add_node("response", self._create_agent_node("response"))
        
        def route_after_classify(state: Dict[str, Any]) -> str:
            if state.get("response"):
                return "response"
                
            intent = state.get("intent", "response")
            metadata = state.get("metadata", {})
            
            if intent == "follow_up":
                conversation_history = state.get("conversation_history", [])
                for msg in reversed(conversation_history):
                    if msg.get("role") == "assistant" and "agent_used" in msg.get("metadata", {}):
                        agent_used = msg["metadata"]["agent_used"]
                        if agent_used in ["web_search_agent", "pdf_query_agent"]:
                            return agent_used.replace("_agent", "")
            
            if metadata.get("force_web_search", False):
                return "web_search"


            
            if intent == "pdf":
                return "pdf_query"
            elif intent == "web":
                return "web_search"
                
            return "response"  
            
        def route_after_pdf(state: Dict[str, Any]) -> str:
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
        
        workflow.add_conditional_edges(
            "classify_intent",
            route_after_classify
        )
        
        workflow.add_conditional_edges(
            "pdf_query",
            route_after_pdf
        )
        
       
        workflow.add_edge("web_search", "response")
        workflow.add_edge("response", END)
        
        
        workflow.set_entry_point("classify_intent")
        
        
        return workflow.compile()
    
    def _initialize_state(self, state: Dict[str, Any]) -> tuple:
        
        messages = state.get("messages", [{}])
        last_message = messages[-1] if messages else {}
        query = last_message.get("content", "")
        metadata = last_message.get("metadata", {})
        
        state.setdefault("intent", "response")
        state.setdefault("metadata", {})
        state["metadata"].setdefault("intent_classification", {})
        
        return state, query, metadata
    
    
    def _apply_keyword_fallback(self, state: Dict[str, Any], query: str) -> None:
        
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in ["search", "find", "look up"]):
            state["intent"] = "web"
        elif any(keyword in query_lower for keyword in ["document", "pdf", "file"]):
            state["intent"] = "pdf"
        else:
            state["intent"] = "response"
    
    def _ensure_dict_state(self, state: Any) -> Dict[str, Any]:
        
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
        
        state = self._ensure_dict_state(state)
        
        state['metadata'] = self._ensure_dict_state(state.get('metadata', {}))
        
        state.setdefault('messages', [])
        state.setdefault('intent', 'response')
        state.setdefault('needs_clarification', False)
        state.setdefault('clarification_questions', [])
        state.setdefault('search_results', [])
        
        
        return self._initialize_state(state)[0]  
    
    
    def _create_intent_classifier(self):
        
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
        
        chain = ({
            "message": lambda x: x["message"],
            "conversation_history": lambda x: x.get("conversation_history", "No previous conversation"),
        } | prompt | self.llm_config.llm | JsonOutputParser())
        
        return chain
        
    def _detect_ambiguity(self, message: str, is_follow_up: bool = False) -> Tuple[bool, str, str]:
       
        if is_follow_up:
            return False, "", ""
            
        message_lower = message.lower()
        if len(message.strip().split()) <= 3 and not any(p in message_lower for p in ['hi', 'hello', 'hey']):
            return True, "Your question seems a bit brief. Could you provide more details?", \
                   "For example, instead of 'How to?', try 'How do I implement a neural network in PyTorch for image classification?'"
        
        ambiguity_patterns = [
            # Very vague questions
            {
                'pattern': r'^\s*(what|how|when|where|who|why|which|can you|could you|would you|is there|are there|does anyone|do you know|i need help|help me|explain|tell me about|what is|what are|what do|what does|how do|how does|how can|how to|how much|how many|what is the|what are the|what was|what were|what will|what would|what should|what could|what can|what might|what may|what if|what about|what else|what other|what kind of|what type of|what sort of|what time|what day|what year|what month|what date|what color|what size|what shape|what brand|what make|what model|what version|what language|what country|what city|what state|what province|what region|what area|what part|what section|what chapter|what page|what line|what word|what letter|what number|what amount|what quantity|what price|what cost|what value|what percentage|what percent|what ratio|what fraction|what decimal|what degree|what temperature|what speed|what distance|what length|what width|what height|what depth|what weight|what mass|what volume|what capacity|what duration|what period|what frequency|what interval|what rate|what speed|what direction|what position|what location|what address|what coordinates|what phone number|what email|what website|what url|what link|what reference|what source|what citation|what author|what title|what name|what term|what phrase|what expression|what sentence|what paragraph|what passage|what quote|what saying|what proverb|what idiom|what slang|what jargon|what acronym|what abbreviation|what initialism|what symbol|what character|what digit|what figure|what diagram|what chart|what graph|what table|what list|what item|what element|what component|what part|what piece|what section|what segment|what portion|what fraction|what percentage|what ratio|what proportion|what amount|what quantity|what number|what count|what total|what sum|what average|what mean|what median|what mode|what range|what spread|what deviation|what variance|what standard deviation|what error|what margin|what limit|what bound|what constraint|what restriction|what requirement|what condition|what criteria|what standard|what benchmark|what metric|what measure|what indicator|what signal|what sign|what symptom|what evidence|what proof|what verification|what validation|what confirmation|what certification|what approval|what authorization|what permission|what consent|what agreement|what contract|what deal|what arrangement|what plan|what schedule|what timeline|what deadline|what due date|what target|what goal|what objective|what aim|what purpose|what intention|what motive|what reason|what cause|what factor|what element|what component|what part|what piece|what section|what segment|what portion|what fraction|what percentage|what ratio|what proportion|what amount|what quantity|what number|what count|what total|what sum|what average|what mean|what median|what mode|what range|what spread|what deviation|what variance|what standard deviation|what error|what margin|what limit|what bound|what constraint|what restriction|what requirement|what condition|what criteria|what standard|what benchmark|what metric|what measure|what indicator|what signal|what sign|what symptom|what evidence|what proof|what verification|what validation|what confirmation|what certification|what approval|what authorization|what permission|what consent|what agreement|what contract|what deal|what arrangement|what plan|what schedule|what timeline|what deadline|what due date|what target|what goal|what objective|what aim|what purpose|what intention|what motive|what reason|what cause|what factor)\s*\??\s*$',
                'clarification': "I'd be happy to help! Could you be more specific about what you'd like to know?",
                'example': "For example, instead of 'Tell me about transformers', try 'What are the key components of the transformer architecture in NLP?'"
            },
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
                'pattern': r'\b(which|what) (is|are) (better|best|worse|worst)\b',
                'clarification': "To help you compare effectively, could you explain what you mean by 'better' in this context?",
                'example': "For example, instead of 'Which model is better?', try 'Which model has higher F1 score on small text classification tasks with limited training data?'"
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
           - greeting: Returns a greeting response such as the message is hi, how are you, good moring, etc
           - pdf_query: Routes to PDF query handler
           - web_search: Routes to web search
           - follow_up: Handles follow-up questions using conversation context
           - clarification_needed: Asks for clarification
        """
      
        state = self._initialize_intent_state(state)
        
        try:
          
            messages = state.get("messages", [])
            if not messages:
                raise ValueError("No messages in conversation")
                
            last_message = messages[-1]
            query = last_message.get("content", "").strip()
            metadata = last_message.get("metadata", {})
            
            
            conversation_history = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
                for msg in messages[:-1]  # Exclude the current message
            )

           


               
            
           

          
            if metadata.get("force_web_search", False):
                state["intent"] = "web"
                state["metadata"]["intent_classification"] = {
                    "detected_intent": "web_search",
                    "confidence": 1.0,
                    "needs_clarification": False,
                    "source": "force_web_search_flag"
                }
                return state
            
            
            try:
                
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
                
                
                response = await self.llm_config.llm.ainvoke(web_search_prompt)
                
                
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
                    
            except Exception as e:
                logger.error(f"Error during web search detection: {e}", exc_info=True)
                
            
            
            
            is_follow_up = False
            context = ""
            
            
            if len(conversation_history) > 0:
                
                last_agent_response = next((msg for msg in reversed(messages[:-1]) 
                                         if msg.get("role") == "assistant"), None)
                
                if last_agent_response and "search_results" in last_agent_response.get("metadata", {}):
                    
                    is_follow_up = True
                    context = last_agent_response.get("content", "")[:200]  
            
            classification = await self.intent_classifier.ainvoke({
                "message": query,
                "conversation_history": conversation_history
            })
            
            intent = classification.get("intent", "pdf_query")
            
            if is_follow_up and intent != "follow_up":
                intent = "follow_up"
                classification["intent"] = "follow_up"
                classification["reasoning"] = "Detected as follow-up based on conversation context"
                if context:
                    classification["context"] = context

            state["metadata"]["intent_classification"] = {
                "detected_intent": intent,
                "confidence": classification.get("confidence", 1.0),
                "needs_clarification": intent == "clarification_needed",
                "reasoning": classification.get("reasoning", ""),
                "source": "llm_intent_classifier",
                "context": classification.get("context", ""),
                "is_follow_up": is_follow_up
            }

            if intent not in ["follow_up", "greeting"]:
                is_ambiguous, clarification_msg, example = self._detect_ambiguity(query, is_follow_up=is_follow_up)
                if is_ambiguous and not is_follow_up:  
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
            

         
          
            
            if intent == "greeting":
                state["intent"] = "response"
                state["response"] = "Hello! How can I assist you today?"
                return state
                
            if intent == "pdf_query":
                state["intent"] = "pdf"
                state["metadata"]["original_query"] = query
                return state
                
            
            if intent == "follow_up":

          

                context = classification.get("context", "")
                if context:
                    modified_query = f"{context} {query}"
                    state["metadata"]["original_query"] = modified_query
                    state["intent"] = "pdf"
                    state["metadata"]["context"] = context
                    return state
                
            state["intent"] = "web" if intent == "web_search" else "pdf"
            
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
        
        if query:
            self._apply_keyword_fallback(state, query)
            
        return state
    
 
    def _create_agent_node(self, agent_name: str):
       
        async def node_func(state: Dict[str, Any]) -> Dict[str, Any]:
            result = dict(state)
            
            try:
                logger.info("Processing with agent: %s", agent_name)
                agent_result = await self.agents[agent_name].process(state)
                
                if isinstance(agent_result, dict):
                    result.update(agent_result)
                
                result.setdefault("metadata", {})
                result["metadata"].update({
                    "processed_by": agent_name,
                    "processing_steps": result["metadata"].get("processing_steps", []) + [agent_name]
                })
                
                result.setdefault("intent", state.get("intent", "response"))
                result.setdefault("needs_clarification", False)
                result.setdefault("clarification_questions", [])
           
                result.setdefault("search_results", [])
                
                if agent_name == "response" and "response" not in result:
                    result["response"] = "I've processed your request."
                
                return result
                
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Error in agent node %s: %s", agent_name, str(e), exc_info=True)
                
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
        
        
        try:
            logger.info(f"Processing message with workflow: {message[:100]}...")
            result = await self.workflow.ainvoke(state)
            
            response = result.get("response", "I'm not sure how to respond to that.")
            if not response:
                response = "I don't have a response for that. Could you please rephrase?"
            
            search_results = result.get("search_results", [])
            if search_results and isinstance(search_results, list) and len(search_results) > 0:
                if not response or response == "I'm not sure how to respond to that.":
                    response = "Here's what I found:"
            
            intent = result.get("intent", "response")
            if intent == "pdf":
                intent = "pdf_query"
            elif intent == "web":
                intent = "web_search"
            
            clarification_questions = result.get("clarification_questions", [])
           
            
            conversation_history = []
            if "messages" in result and isinstance(result["messages"], list):
                conversation_history = [
                    msg for msg in result["messages"] 
                    if isinstance(msg, dict) and "role" in msg and "content" in msg
                ]
            
            metadata = {
                "agent_used": result.get("current_agent", "unknown"),
                "session_id": session_id,
                "intent": intent,
                "success": True,
                **result.get("metadata", {})
            }
            
           
            logger.info(f"Successfully processed message with intent: {intent}")
            
            return {
                "intent": intent,
                "message": response,
                "session_id": session_id,
                "search_results": search_results if isinstance(search_results, list) else [],
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
            
                "clarification_questions": [],
               
                "conversation_history": [],
                "metadata": {
                    "error": str(e),
                    "session_id": session_id
                }
            }
