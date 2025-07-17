"""Chat endpoint implementation using LangChain."""
import logging
import os
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException

from app.services.langchain_router import LangChainRouter
from app.config.llm import LLMConfig, IntentType
from app.api.models.chat import ChatRequest, ChatResponse
from app.core.vector_store import VectorStore

# Configure logger
logger = logging.getLogger(__name__)
router = APIRouter()

# Get OpenAI API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize LLM config and router
llm_config = LLMConfig(openai_api_key=openai_api_key)
llm_router = LangChainRouter(llm_config)
vector_store = VectorStore()

def _format_search_results(search_results: List[Dict[str, Any]]) -> str:
    """Format search results into a user-friendly string."""
    if not search_results:
        return "I couldn't find any relevant information in the documents."
    
    formatted = []
    for i, result in enumerate(search_results[:3], 1):
        # Get the text content from the result
        content = result.get('text', '').strip()
        if not content:
            continue  # Skip results with no content
            
        # Get metadata and source information
        metadata = result.get('metadata', {})
        source = metadata.get('source', 'Unknown Document')
        
        # Format the source name
        if '/' in source:
            source = source.split('/')[-1]  # Get just the filename
        if '.' in source:
            source = source.split('.')[0]  # Remove file extension
        # Clean up the source name
        source = source.replace('_', ' ').replace('-', ' ').title()
        
        # Format the result as "document_name reports that ..."
        # Ensure the content starts with a capital letter and ends with a period
        content = content[0].upper() + content[1:]
        if not content.endswith(('.', '!', '?')):
            content += '.'
            
        formatted_entry = f"{source} reports that {content}"
        
        # Add page number if available
        if 'page' in metadata:
            formatted_entry += f" (Page {metadata['page']})"
            
        formatted.append(formatted_entry)
    
    # If we filtered out all results due to empty content
    if not formatted:
        return "I found some results, but they don't contain any text content."
        
    # Join with double newlines for better readability
    return "\n\n".join(formatted)

async def _process_chat_request(chat_request: ChatRequest) -> ChatResponse:
    """Process a chat request and return the appropriate response."""
    # If web search is forced, perform it immediately
    if chat_request.force_web_search:
        return await llm_router.route_query(
            user_message=chat_request.message,
            force_web_search=True
        )
    
    # First, try to answer from PDFs
    search_results = vector_store.search_similar(
        chat_request.message,
        min_similarity=0.5
    )
    
    if search_results:
        # Found relevant information in PDFs
        return ChatResponse(
            intent=IntentType.PDF_QUERY,
            message=_format_search_results(search_results),
            needs_clarification=False
        )
    
    # No relevant information found in PDFs
    response = await llm_router.route_query(
        user_message=chat_request.message,
        force_web_search=False
    )
    
    # If the intent wasn't a greeting, inform user about searching the web
    if response.intent != IntentType.GREETING:
        response.message = "The system should recognize this is not covered in the PDFs and search the web."
    
    return response

@router.post("/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest) -> ChatResponse:
    """
    Handle chat messages and route them appropriately.
    
    Args:
        chat_request: The chat request containing the message and options
        
    Returns:
        ChatResponse: The response to the user's message
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    if not llm_config.is_configured:
        raise HTTPException(
            status_code=500,
            detail="LLM service is not properly configured. Please check the API key."
        )
    
    try:
        return await _process_chat_request(chat_request)
    except Exception as e:
        logger.error("Error processing chat request: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}"
        ) from e
