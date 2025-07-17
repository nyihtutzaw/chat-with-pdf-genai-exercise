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
            search_results = vector_store.search_similar(chat_request.message, min_similarity=0.5)
            if not search_results:
                # No relevant documents found, perform web search
                web_search_response = await llm_router.route_query(
                    user_message=chat_request.message,
                    force_web_search=True
                )
                if web_search_response.intent == "web_search":
                    return ChatResponse(
                        intent=web_search_response.intent,
                        message=web_search_response.message,
                        needs_clarification=web_search_response.needs_clarification,
                        clarification_questions=web_search_response.clarification_questions,
                        context=web_search_response.context if hasattr(web_search_response, 'context') else None
                    )
                
                # If web search also fails, return a helpful message
                response.message = "I couldn't find any relevant information in the documents or through a web search. Could you please rephrase your question or provide more details?"
                response.needs_clarification = True
                response.clarification_questions = [
                    "Would you like to try a different search query?",
                    "Could you provide more specific details about what you're looking for?"
                ]
            else:
                # Format the search results into a response with document names
                formatted_results = []
                for result in search_results[:3]:  # Use top 3 results
                    doc_name = result.get('metadata', {}).get('source', 'The document')
                    # Clean up the document name if it's a file path
                    if '/' in doc_name:
                        doc_name = doc_name.split('/')[-1]  # Get just the filename
                    if '.' in doc_name:
                        doc_name = doc_name.split('.')[0]  # Remove file extension
                    doc_name = doc_name.replace('_', ' ').title()  # Format nicely
                    formatted_results.append(f"{doc_name} reports that: {result['text']}")
                
                response.message = "\n\n".join(formatted_results)
        
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
