import logging
import os
from fastapi import APIRouter, HTTPException
from app.services.llm_router import LLMRouter
from app.config.llm import LLMConfig
from app.api.models.chat import ChatRequest, ChatResponse
from app.core.vector_store import VectorStore

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

# Get OpenAI API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

llm_config = LLMConfig(openai_api_key=openai_api_key)
llm_router = LLMRouter(llm_config)

# Initialize vector store
vector_store = VectorStore()

@router.post("/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest):
    """
    Handle chat messages and route them appropriately.
    
    - **message**: The user's message
    - **session_id**: Optional session ID for maintaining conversation context
    - **force_web_search**: If True, forces a web search regardless of message content
    """
    if not llm_config.is_configured:
        raise HTTPException(
            status_code=500,
            detail="LLM service is not properly configured. Please check the API key."
        )
    
    try:
        # Route the query using the LLM router
        response = await llm_router.route_query(
            user_message=chat_request.message,
            force_web_search=chat_request.force_web_search
        )
        
        # If this is a PDF query, search the vector store
        if response.intent == "pdf_query":
            search_results = vector_store.search_similar(chat_request.message)
            if search_results:
                # Format the search results into a response
                context = "\n\n".join([result['text'] for result in search_results[:3]])  # Use top 3 results
                response.message = f"I found this information in the documents:\n\n{context}"
            else:
                response.message = "I couldn't find any relevant information in the documents. Would you like me to search the web instead?"
                response.needs_clarification = True
                response.clarification_questions = [
                    "Would you like me to search the web for this information?",
                    "Should I look for more specific details in the documents?"
                ]
        
        return ChatResponse(
            intent=response.intent,
            message=response.message,
            needs_clarification=response.needs_clarification,
            clarification_questions=response.clarification_questions,
            context=response.context if hasattr(response, 'context') else None
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}"
        )
