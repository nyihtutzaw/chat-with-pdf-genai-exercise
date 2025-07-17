"""LangChain-based router for handling chat intents and routing."""
import re
import logging
from datetime import datetime, timezone

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.config.llm import LLMConfig, IntentType, RouterResponse
from app.services.web_search import web_search_service

logger = logging.getLogger(__name__)

class LangChainRouter:
    """Router implementation using LangChain for intent classification and routing."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.llm = config.llm
        self.intent_classifier = self._create_intent_classifier()
        
    def _create_intent_classifier(self):
        """Create the intent classification chain."""
        intent_prompt = """
        You are an intent classification system for a chat application that helps users with PDF documents.
        
        Classify the following message into one of these intents:
        - greeting: For greetings like hello, hi, hey, good morning/afternoon/evening, what's up, etc.
        - pdf_query: When asking about PDF document content
        - web_search: For general knowledge questions not specific to PDFs
        - clarification_needed: When the intent is unclear
        
        Message to classify: {message}
        
        Respond with a JSON object containing:
        - intent: The classified intent (greeting, pdf_query, web_search, or clarification_needed)
        - confidence: A number between 0 and 1 indicating your confidence
        - reasoning: A brief explanation of your classification
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", intent_prompt),
            ("human", "{message}")
        ])
        
        # Create a chain that takes a message and returns a classification
        return (
            {"message": RunnablePassthrough()}
            | prompt
            | self.llm
            | JsonOutputParser()
        )
    
    def _detect_ambiguity(self, message: str) -> tuple[bool, str, str]:
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
    
    async def _perform_web_search(self, query: str) -> RouterResponse:
        """Perform a web search and format the results with follow-up questions."""
        try:
            # Generate potential follow-up questions before making the search
            follow_ups = [
                f"Tell me more about {query}",
                f"Find recent developments about {query}",
                f"Show me related information about {query.split()[0] if query.split() else 'this topic'}",
                f"Search for latest news about {query}"
            ]
            
            results = await web_search_service.search(query)
            if not results:
                return RouterResponse(
                    intent=IntentType.WEB_SEARCH,
                    message="I couldn't find any relevant information. Could you try rephrasing your question?",
                    needs_clarification=True,
                    clarification_questions=["Could you provide more specific details about what you're looking for?"],
                    follow_up_questions=follow_ups[:2]
                )
            
            # Format search results
            formatted_results = []
            for i, result in enumerate(results[:3], 1):
                title = result.get('title', 'No title').strip()
                snippet = result.get('snippet', 'No description available').strip()
                link = result.get('link', '').strip()
                
                formatted_results.append(
                    f"{i}. **{title}**\n"
                    f"{snippet}\n"
                    f"📎 {link}\n\n"
                )
            
            # Join the formatted results
            results_text = "".join(formatted_results).strip()
            
            # Update follow-up questions based on search results
            if results:
                first_result = results[0]
                if 'title' in first_result:
                    main_topic = first_result.get('title', '').split(' - ')[0].split(' | ')[0].split(' - ')[0]
                    if main_topic and len(main_topic) > 5:  # Ensure it's a meaningful topic
                        follow_ups = [
                            f"More details about {main_topic}",
                            f"Latest news on {main_topic}",
                            f"Related information to {main_topic}",
                            f"Search for more about {main_topic}"
                        ]
            
            return RouterResponse(
                intent=IntentType.WEB_SEARCH,
                message=f"🔍 Here are some relevant web results:\n\n{results_text}",
                needs_clarification=False,
                follow_up_questions=follow_ups[:4],
                metadata={
                    "search_query": query,
                    "result_count": len(results),
                    "search_timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
        except Exception as e:
            logger.error("Error performing web search: %s", str(e))
            return RouterResponse(
                intent=IntentType.WEB_SEARCH,
                message="I encountered an error while searching the web. Please try again later.",
                needs_clarification=True,
                clarification_questions=[
                    "Would you like to try a different search query?",
                    "Could you rephrase your question?"
                ],
                follow_up_questions=[
                    f"Search again for: {query}",
                    "Try a different search term"
                ]
            )

    async def route_query(self, user_message: str, force_web_search: bool = False) -> RouterResponse:
        """
        Route the user's message to the appropriate handler.
        
        Args:
            user_message: The user's message
            force_web_search: If True, force a web search regardless of intent
            
        Returns:
            RouterResponse: The routing decision with appropriate response
        """
        logger.info("\n%s", "=" * 80)
        logger.info("Processing message: '%s'", user_message)
        logger.info("Force web search: %s", force_web_search)
        
        if force_web_search:
            return await self._perform_web_search(user_message)
            
        # First check for ambiguity
        is_ambiguous, clarification, example = self._detect_ambiguity(user_message)
        if is_ambiguous:
            return RouterResponse(
                intent=IntentType.CLARIFICATION_NEEDED,
                message=clarification,
                needs_clarification=True,
                clarification_questions=[example]  # Use the example directly as it's already well-formed
            )
            
        # If not ambiguous, proceed with intent classification
        try:
            classification = await self.intent_classifier.ainvoke(user_message)
            intent_str = classification.get('intent', 'clarification_needed').lower()
            
            # Map the classified intent to our IntentType
            if 'greet' in intent_str:
                return RouterResponse(
                    intent=IntentType.GREETING,
                    message="Hello! I can help you find information in your PDFs or search the web. What would you like to know?",
                    needs_clarification=False,
                    follow_up_questions=[
                        "Search the web for information",
                        "Help me find a PDF",
                        "What can you do?"
                    ]
                )
            elif 'pdf' in intent_str:
                return RouterResponse(
                    intent=IntentType.PDF_QUERY,
                    message=user_message,
                    needs_clarification=False,
                    follow_up_questions=[
                        f"Find more about {user_message}",
                        "Search the web instead",
                        "Show me related documents"
                    ]
                )
            else:
                # For general knowledge questions, suggest a web search
                return RouterResponse(
                    intent=IntentType.WEB_SEARCH,
                    message="The system should recognize this is not covered in the PDFs and search the web.",
                    needs_clarification=True,
                    clarification_questions=[
                        "Would you like me to search the web for this information?"
                    ],
                    follow_up_questions=[
                        f"Search the web for: {user_message}",
                        "Find related information",
                        "Show me recent updates on this topic"
                    ],
                    metadata={"suggest_web_search": True}
                )
                
        except Exception as e:
            logger.error(f"Error in route_query: {str(e)}")
            return RouterResponse(
                intent=IntentType.CLARIFICATION_NEEDED,
                message="I need more information to help you effectively. Could you please provide more details?",
                needs_clarification=True,
                clarification_questions=[
                    "Could you rephrase your question with more specific details?",
                    "What specific information are you looking for?",
                    "Could you provide more context about your question?"
                ],
                follow_up_questions=[
                    "Try asking a different way",
                    "Search the web instead",
                    "Show me an example question"
                ]
            )
