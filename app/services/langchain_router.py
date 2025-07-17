"""LangChain-based router for handling chat intents and routing."""
import re
import logging

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
        """Perform a web search and format the results."""
        try:
            results = await web_search_service.search(query)
            if not results:
                return RouterResponse(
                    intent=IntentType.WEB_SEARCH,
                    message="I couldn't find any relevant information. Could you try rephrasing your question?",
                    needs_clarification=True,
                    clarification_questions=["Could you provide more specific details about what you're looking for?"]
                )
            
            # Format search results
            formatted_results = []
            for i, result in enumerate(results[:3], 1):
                formatted_results.append(
                    f"{i}. **{result.get('title', 'No title')}**\n"
                    f"{result.get('snippet', 'No description available')}\n"
                    f"📎 {result.get('link', '')}\n"
                )
            
            # Join the formatted results first, then include in the f-string
            results_text = "".join(formatted_results)
            return RouterResponse(
                intent=IntentType.WEB_SEARCH,
                message=f"🔍 Here are some relevant web results:\n\n{results_text}",
                needs_clarification=False
            )
            
        except Exception as e:
            logger.error(f"Error performing web search: {str(e)}")
            return RouterResponse(
                intent=IntentType.WEB_SEARCH,
                message="I encountered an error while searching the web. Please try again later.",
                needs_clarification=True
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
                    needs_clarification=False
                )
            elif 'pdf' in intent_str:
                return RouterResponse(
                    intent=IntentType.PDF_QUERY,
                    message=user_message,
                    needs_clarification=False
                )
            else:
                # Default to web search for general knowledge questions
                return await self._perform_web_search(user_message)
                
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
                ]
            )
