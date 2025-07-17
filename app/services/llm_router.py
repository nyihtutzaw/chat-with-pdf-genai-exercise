import json
import logging

from openai import AsyncOpenAI

from app.config.llm import LLMConfig, RouterResponse
from app.models.intent import IntentLabel, IntentPrediction

# Constants for messages
WEB_SEARCH_PROMPT = "What specific information are you looking for?"
RECENT_INFO_PROMPT = "Are you looking for recent information or something specific?"
PDF_QUERY_CLARIFICATION = "Are you looking for information from the PDF documents?"

# Configure logger
logger = logging.getLogger(__name__)

# Type alias for intent type to maintain compatibility with existing code
IntentType = IntentLabel

INTENT_CLASSIFICATION_PROMPT = """
You are an intent classification system for a chat application that helps users with PDF documents.
Classify the user's message into one of these intents:

1. greeting: When the user is just saying hello or starting a conversation.
   - This includes any variation of greetings, even very short ones.
   - Examples: "Hi", "Hello", "Hey", "Good morning", "Hi there", "Hello!", "Hey!", "Greetings"
   - Even just "hi" or "hello" without punctuation should be classified as greeting.

2. pdf_query: When the user is asking about the content of PDF documents,
             which are academic research papers about computer science
             and artificial intelligence.
   Examples: "What does the document say about X in computer science?",
             "Summarize the paper about AI", "What is the main contribution of the paper?"

3. web_search: When the user is asking for general information not specific to PDFs
   Examples: "What's the weather like?", "Tell me about machine learning"

4. clarification_needed: When the intent is not clear or more information is needed
   Examples: "I need help", "Can you find something for me?"

For very short messages, prioritize greeting classification if it could be a greeting.
If the message is just a greeting word or phrase, it's almost certainly a greeting intent.

Return your response as a JSON object with the following structure:
{
    "intent": "intent_name",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of your classification"
}
"""

class LLMRouter:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self._intent_cache = {}  # Simple cache to avoid redundant API calls
    
    async def _classify_intent(self, message: str) -> IntentPrediction:
        """Classify the intent of a message using OpenAI's API."""
        if not message.strip():
            return IntentPrediction(
                intent=IntentLabel.CLARIFICATION_NEEDED,
                confidence=1.0,
                reasoning="Empty message requires clarification"
            )
        
        # Check cache first
        cache_key = message.lower().strip()
        if cache_key in self._intent_cache:
            return self._intent_cache[cache_key]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                    {"role": "user", "content": message}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=150
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            prediction = IntentPrediction(
                intent=IntentLabel(result["intent"]),
                confidence=float(result["confidence"]),
                reasoning=result["reasoning"]
            )
            
            # Cache the result
            self._intent_cache[cache_key] = prediction
            return prediction
            
        except Exception as e:  # pylint: disable=broad-except
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Log the error with appropriate level
            if isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
                logger.error(
                    "Failed to parse intent classification response: %s: %s",
                    error_type, error_msg
                )
                reasoning = "I had trouble understanding that. Could you rephrase?"
            else:
                logger.exception("Unexpected error during intent classification")
                reasoning = f"I encountered an error: {error_msg}. Please try again."
            
            return IntentPrediction(
                intent=IntentLabel.CLARIFICATION_NEEDED,
                confidence=0.0,
                reasoning=reasoning
            )
    
    
    async def route_query(self, user_message: str, force_web_search: bool = False) -> RouterResponse:
        """
        Route the user query to the appropriate handler based on intent.
        
        Args:
            user_message: The message from the user to be routed
            force_web_search: If True, forces a web search regardless of message content
            
        Returns:
            RouterResponse: The routing decision with appropriate response
        """
        logger.info("\n%s", "=" * 80)
        logger.info("Processing message: '%s'", user_message)
        logger.info("Force web search: %s", force_web_search)
        
        # If web search is forced, return web search intent immediately
        if force_web_search:
            logger.info("Force web search is enabled")
            return RouterResponse(
                intent=IntentType.WEB_SEARCH,
                message="Performing a web search as requested. What would you like to know?",
                needs_clarification=not user_message,
                clarification_questions=[WEB_SEARCH_PROMPT, RECENT_INFO_PROMPT] if not user_message else []
            )
        
        try:
            # Classify the intent using the LLM
            prediction = await self._classify_intent(user_message)
            logger.info(
                "Intent classification - Message: '%s', Intent: %s, Confidence: %.2f, Reason: %s",
                user_message, prediction.intent.value, prediction.confidence, prediction.reasoning
            )
            
            # Map our internal intent labels to the RouterResponse intent types
            intent_mapping = {
                IntentLabel.GREETING: IntentType.GREETING,
                IntentLabel.PDF_QUERY: IntentType.PDF_QUERY,
                IntentLabel.WEB_SEARCH: IntentType.WEB_SEARCH,
                IntentLabel.CLARIFICATION_NEEDED: IntentType.CLARIFICATION_NEEDED
            }
            
            intent_type = intent_mapping.get(prediction.intent, IntentType.WEB_SEARCH)
            
            # Handle each intent type
            if prediction.intent == IntentLabel.GREETING:
                return RouterResponse(
                    intent=intent_type,
                    message="Hello! How can I assist you with the PDF documents today?",
                    needs_clarification=False
                )
            elif prediction.intent == IntentLabel.PDF_QUERY:
                return RouterResponse(
                    intent=intent_type,
                    message="I'll search through the PDF documents for that information.",
                    needs_clarification=False
                )
            else:  # WEB_SEARCH or CLARIFICATION_NEEDED
                return RouterResponse(
                    intent=intent_type,
                    message=(
                        "I'll look that up for you. What specific information are you looking for?"
                        if prediction.intent == IntentLabel.WEB_SEARCH
                        else "I'm not sure I understand. Could you please provide more details?"
                    ),
                    needs_clarification=True,
                    clarification_questions=[
                        WEB_SEARCH_PROMPT,
                        RECENT_INFO_PROMPT,
                        "Are you looking for information from the PDF documents?"
                    ]
                )
            
        except Exception as e:  # pylint: disable=broad-except
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Log the error with appropriate level
            if isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
                logger.error(
                    "Failed to process response in route_query: %s: %s",
                    error_type, error_msg,
                    exc_info=True
                )
                message = "I had trouble understanding that. Could you rephrase?"
                questions = [
                    "Could you rephrase your question?",
                    PDF_QUERY_CLARIFICATION,
                    WEB_SEARCH_PROMPT
                ]
            else:
                logger.exception("Unexpected error in route_query")
                message = f"I'm having some technical difficulties: {error_msg}. Please try again or rephrase."
                questions = [
                    "Could you rephrase your question?",
                    "Would you like to try a different approach?",
                    PDF_QUERY_CLARIFICATION
                ]
            
            return RouterResponse(
                intent=IntentType.CLARIFICATION_NEEDED,
                message=message,
                needs_clarification=True,
                clarification_questions=questions
            )
