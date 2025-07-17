"""Chat endpoint implementation with conversation management."""
import logging
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status

from app.api.models.chat import ChatRequest, ChatResponse, ClearSessionResponse, IntentType
from app.config.config import settings
from app.config.llm import LLMConfig
from app.core.vector_store import vector_store
from app.services.conversation.state import conversation_manager
from app.services.langchain_router import LangChainRouter

# Configure logger
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

def _format_search_results(search_results: List[Dict[str, Any]]) -> str:
    """Format search results into a user-friendly string."""
    if not search_results:
        return "I couldn't find any relevant information in the documents."
    
    formatted = []
    for result in search_results[:3]:
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

# Initialize LLM configuration with OpenAI API key from settings
try:
    llm_config = LLMConfig(openai_api_key=settings.OPENAI_API_KEY)
    router_llm = LangChainRouter(llm_config)
except ValueError as e:
    logger.error(f"Failed to initialize LLM configuration: {str(e)}")
    raise RuntimeError("Failed to initialize language model configuration. Please check your API keys.")

async def _process_chat_request(chat_request: ChatRequest) -> Dict[str, Any]:
    """Process a chat request and return the appropriate response."""
    # Get or create conversation
    conversation = conversation_manager.get_conversation(chat_request.session_id)
    
    # Add user message to conversation
    conversation.add_message("user", chat_request.message, **chat_request.metadata)
    
    # Route the message based on intent
    router_response = await router_llm.route_query(
        chat_request.message,
        force_web_search=chat_request.force_web_search
    )
    
    # Handle different intents
    if router_response.intent == IntentType.PDF_QUERY and not chat_request.force_web_search:
        # Search the vector store for relevant documents
        search_results = vector_store.search_similar(
            query=chat_request.message,
            limit=3
        )
        response_message = _format_search_results(search_results)
    else:
        # If the response suggests a web search but force_web_search is False, modify the message
        if router_response.metadata and router_response.metadata.get('suggest_web_search') and not chat_request.force_web_search:
            response_message = "The system should recognize this is not covered in the PDFs and search the web."
        else:
            response_message = router_response.message
    
    # Add assistant's response to conversation
    conversation.add_message("assistant", response_message)
    
    # Get the conversation history for context
    conversation_history = conversation.get_messages()
    
    return {
        "intent": router_response.intent.value,
        "message": response_message,
        "session_id": conversation.session_id,
        "needs_clarification": router_response.needs_clarification,
        "clarification_questions": router_response.clarification_questions or [],
        "follow_up_questions": router_response.follow_up_questions or [],
        "conversation_history": conversation_history,
        "metadata": router_response.metadata or {}
    }

@router.post("", response_model=ChatResponse)
async def chat(chat_request: ChatRequest) -> ChatResponse:
    """
    Handle chat messages with conversation management.
    
    Args:
        chat_request: The chat request containing the message and session ID
        
    Returns:
        ChatResponse: The response to the user's message with conversation context
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        response_data = await _process_chat_request(chat_request)
        return ChatResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing chat request: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your message"
        ) from e

@router.post("/sessions/{session_id}/clear", response_model=ClearSessionResponse)
async def clear_session(session_id: str) -> ClearSessionResponse:
    """
    Clear the conversation history for a specific session.
    
    Args:
        session_id: The ID of the session to clear
        
    Returns:
        ClearSessionResponse: Status of the operation
    """
    try:
        conversation_manager.clear_conversation(session_id)
        return ClearSessionResponse(
            status="success",
            message=f"Session {session_id} cleared successfully"
        )
    except Exception as e:
        logger.error("Error clearing session %s: %s", session_id, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while clearing the session"
        ) from e
