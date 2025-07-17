import json
import logging

from openai import AsyncOpenAI
from app.services.web_search import web_search_service

from app.config.llm import LLMConfig, RouterResponse
from app.models.intent import IntentLabel, IntentPrediction

# Constants for messages
WEB_SEARCH_PROMPT = "What specific information are you looking for?"
RECENT_INFO_PROMPT = "Are you looking for recent information or something specific?"
PDF_QUERY_CLARIFICATION = "Are you looking for information from the PDF documents?"
REPHRASE_QUESTION = "Could you rephrase your question?"

# Ambiguity patterns and clarification templates
AMBIGUITY_PATTERNS = [
    # Vague quantity questions
    {
        'pattern': r'\b(how many|how much|what (?:is|are) (?:the )?(?:number|amount|quantity) of)\b.*\b(enough|sufficient|good|optimal|best|required)\b',
        'clarification': "I'm not sure I understand your question. Could you specify how many/much of something you're asking about and what you're trying to achieve?",
        'example': "For example, instead of 'How many examples are enough?', try 'How many training examples do I need to achieve 95% accuracy on the test set for sentiment analysis?'"
    },
    # Vague quality questions
    {
        'pattern': r'\b(is|are|does|do|will|would|can|could|should|might|may)\b.*\b(good|bad|better|best|worst|enough|sufficient|optimal|work|help|improve|affect|impact|matter)\b',
        'clarification': "I'm not sure I understand your question. Could you explain what you mean by 'good/bad' or 'better/worse' in this context?",
        'example': "For example, instead of 'Is this model good?', try 'How does this model's 90% accuracy compare to state-of-the-art on the IMDB dataset?'"
    },
    # Vague comparison questions
    {
        'pattern': r'\b(which|what) (is|are) (better|best|worse|worst|faster|slower|more accurate|less accurate)\b',
        'clarification': "To help you compare effectively, could you explain what you mean by 'better/worse' in this context and what you're trying to achieve?",
        'example': "For example, instead of 'Which model is better?', try 'Which model has higher F1 score on small text classification tasks with limited training data?'"
    }
]

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
             and artificial intelligence. This includes:
             - References to papers using author names (e.g., "Zhang et al.")
             - References to documents by full or partial names
             - Any mention of PDFs, papers, or research documents
             - Requests for summaries or information from specific papers
   Examples: 
             - "What does Zhang et al. say about X?"
             - "Summary of Zhang et al. report"
             - "Zhang et al. - 2024 - Benchmarking the Text-to-SQL Capability of Large"
             - "Tell me about the paper on Text-to-SQL by Zhang"
             - "What's in the PDF about Text-to-SQL?"
             - "Summarize the document about AI safety"

3. web_search: When the user is asking for general information not specific to PDFs
   Examples: "What's the weather like?", "Tell me about machine learning"

4. clarification_needed: When the intent is not clear or more information is needed
   Examples: "I need help", "Can you find something for me?"

Important notes:
- If the message contains a document name, paper title, or author names (especially with academic citation formats like "et al."), it's VERY LIKELY a pdf_query.
- If the message asks for a summary or information that could be in a research paper, prefer pdf_query over web_search.
- When in doubt between pdf_query and web_search, choose pdf_query if the query could reasonably be about academic research.
- If the message contains a document name that looks like a research paper (e.g., "Zhang et al. - 2024 - Title..."), it's DEFINITELY a pdf_query.
- If the message is asking about the content of a specific paper or document, it's a pdf_query.

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
    
    
    def _detect_ambiguity(self, message: str) -> tuple[bool, str, str]:
        """
        Check if a message is ambiguous and return appropriate clarification.
        
        Args:
            message: The user's message to check for ambiguity
            
        Returns:
            tuple: (is_ambiguous, clarification_message, example)
        """
        import re
        
        # Check for ambiguity patterns
        for pattern_info in AMBIGUITY_PATTERNS:
            if re.search(pattern_info['pattern'], message, re.IGNORECASE):
                return True, pattern_info['clarification'], pattern_info.get('example', '')
                
        return False, "", ""
    
    async def _perform_web_search(self, query: str) -> RouterResponse:
        """
        Perform a web search and format the results.
        
        Args:
            query: The search query
            
        Returns:
            RouterResponse: Formatted search results or error message
        """
        try:
            search_results = await web_search_service.search(query)
            if search_results:
                # Format the results into a readable response
                response_text = "🔍 Here are some relevant web results:\n\n"
                for i, result in enumerate(search_results[:3], 1):  # Show top 3 results
                    response_text += (
                        f"{i}. **{result['title']}**\n"
                        f"   {result['snippet']}\n"
                        f"   📎 {result['link']}\n\n"
                    )
                
                return RouterResponse(
                    intent=IntentType.WEB_SEARCH,
                    message=response_text.strip(),
                    needs_clarification=False,
                    context={"search_results": search_results}
                )
            else:
                return RouterResponse(
                    intent=IntentType.CLARIFICATION_NEEDED,
                    message="I couldn't find any relevant web results. Could you try rephrasing your query?",
                    needs_clarification=True,
                    clarification_questions=[
                        "Would you like to try a different search term?",
                        "Could you provide more specific details about what you're looking for?"
                    ]
                )
                
        except Exception as e:
            logger.error(f"Error in web search: {str(e)}")
            return RouterResponse(
                intent=IntentType.CLARIFICATION_NEEDED,
                message="I encountered an error while performing the web search. Please try again later.",
                needs_clarification=True
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
        
        # If web search is forced, perform it immediately
        if force_web_search:
            return await self._perform_web_search(user_message)
        
        # First check for ambiguous questions
        is_ambiguous, clarification, example = self._detect_ambiguity(user_message)
        if is_ambiguous:
            clarification_questions = [
                clarification,
                "Could you provide more specific details or constraints?",
                example if example else ""
            ]
            return RouterResponse(
                intent=IntentType.CLARIFICATION_NEEDED,
                message="I want to make sure I understand your question correctly.",
                needs_clarification=True,
                clarification_questions=[q for q in clarification_questions if q]
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
            elif prediction.intent == IntentLabel.WEB_SEARCH:
                return await self._perform_web_search(user_message)
            else:  # CLARIFICATION_NEEDED
                return RouterResponse(
                    intent=intent_type,
                    message="I'm not sure I understand. Could you please provide more details?",
                    needs_clarification=True,
                    clarification_questions=[
                        REPHRASE_QUESTION,
                        PDF_QUERY_CLARIFICATION,
                        "Would you like me to search the web for this information?"
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
                message = f"I had trouble understanding that. {REPHRASE_QUESTION}"
                questions = [
                    REPHRASE_QUESTION,
                    PDF_QUERY_CLARIFICATION,
                    WEB_SEARCH_PROMPT
                ]
            else:
                logger.exception("Unexpected error in route_query")
                message = f"I'm having some technical difficulties: {error_msg}. Please try again or rephrase."
                questions = [
                    "Could you rephrase your question?",
                    PDF_QUERY_CLARIFICATION
                ]
            
            return RouterResponse(
                intent=IntentType.CLARIFICATION_NEEDED,
                message=message,
                needs_clarification=True,
                clarification_questions=questions
            )
