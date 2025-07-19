"""Chat endpoint implementation with conversation management."""
import logging
import uuid
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status

from app.api.models.chat import ChatRequest, ChatResponse, ClearSessionResponse
from app.core.vector_store import vector_store
from app.agents.orchestrator import AgentOrchestrator
from app.services.conversation.state import conversation_manager

# Configure logger
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize the agent orchestrator
agent_orchestrator = AgentOrchestrator(vector_store)

def _format_conversation_history(messages: list) -> list:
    """Format conversation messages into a consistent dictionary format."""
    formatted_messages = []
    for msg in messages:
        if hasattr(msg, 'to_dict'):
            # Handle Message objects
            msg_dict = msg.to_dict()
            formatted_messages.append({
                "role": msg_dict["role"],
                "content": msg_dict["content"],
                **msg_dict.get("metadata", {})
            })
        elif isinstance(msg, dict):
            # Handle dictionary messages
            formatted_messages.append({
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
                **msg.get("metadata", {})
            })
    return formatted_messages

async def _process_with_agent(conversation, message: str, session_id: str, force_web_search: bool = False) -> dict:
    """Process a message through the agent workflow.
    
    Args:
        conversation: The conversation object
        message: The user's message
        session_id: The conversation session ID
        force_web_search: If True, forces a web search regardless of message content
    """
    try:
        result = await agent_orchestrator.process_message(
            message=message,
            session_id=session_id,
            force_web_search=force_web_search
        )
        
        # Ensure we have a valid response message
        response_message = result.get("message") or result.get("response")
        response_message = response_message or "I'm not sure how to respond to that."
        
        # Prepare metadata for assistant's response
        assistant_metadata = result.get("metadata", {})
        if not isinstance(assistant_metadata, dict):
            assistant_metadata = {}
            
        # Add assistant's response to conversation
        conversation.add_message(
            role="assistant", 
            content=response_message,
            **assistant_metadata
        )
        
        return {
            "result": result,
            "response_message": response_message,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "success": False
        }

def _create_error_response(request_id: str, chat_request: ChatRequest, error: str) -> dict:
    """Create an error response dictionary."""
    return {
        "intent": "error",
        "message": "I encountered an error processing your request. Please try again.",
        "session_id": chat_request.session_id,
        "clarification_questions": [],
       
        "metadata": {
            "request_id": request_id,
            "error": error,
            "success": False
        }
    }

async def _process_chat_request(chat_request: ChatRequest) -> Dict[str, Any]:
    """Process a chat request using the agent workflow.
    
    This function:
    1. Gets or creates a conversation session
    2. Processes the user's message through the agent workflow
    3. Updates the conversation history
    4. Returns a properly formatted response
    
    Args:
        chat_request: The incoming chat request with message and metadata
        
    Returns:
        A dictionary with all fields required by the ChatResponse model
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    request_id = str(uuid.uuid4())[:8]
    logger.info("Processing request ID %s: %s", request_id, chat_request.message)
    
    try:
        # Get or create conversation
        conversation = conversation_manager.get_conversation(chat_request.session_id)
        
        # Add user message to conversation with metadata
        user_msg_metadata = {}
        if hasattr(chat_request, 'metadata'):
            user_msg_metadata.update(chat_request.metadata)
        
        # Add force_web_search flag to metadata if it's True
        if hasattr(chat_request, 'force_web_search') and chat_request.force_web_search:
            user_msg_metadata['force_web_search'] = True
            
        conversation.add_message(
            role="user", 
            content=chat_request.message,
            **user_msg_metadata
        )
        
        # Process through agent workflow
        logger.debug("Sending to agent workflow: %s", chat_request.message)
        agent_result = await _process_with_agent(
            conversation=conversation,
            message=chat_request.message,
            session_id=chat_request.session_id,
            force_web_search=getattr(chat_request, 'force_web_search', False)
        )
        
        if not agent_result.get("success"):
            # Add error message to conversation
            conversation.add_message(
                role="assistant",
                content="I'm sorry, I encountered an error processing your request.",
                error=agent_result.get("error", "Unknown error"),
                success=False
            )
            return _create_error_response(request_id, chat_request, str(agent_result.get("error")))
        
        # Get conversation history in the required format
        conversation_history = _format_conversation_history(conversation.get_messages())
        
        # Prepare response data
        result = agent_result["result"]
        response_message = agent_result["response_message"]
        intent = result.get("intent", "response")
        
        # Prepare response with all required fields for ChatResponse
        response_data = {
            "intent": intent,
            "message": response_message,
            "session_id": chat_request.session_id,
            "search_results": result.get("search_results") or [],
            "conversation_history": conversation_history,
            "metadata": {
                "request_id": request_id,
                "session_id": chat_request.session_id,
                "intent": intent,
                "success": True,
                **result.get("metadata", {})
            }
        }
        
        logger.debug("Prepared response: %s", {
            k: v for k, v in response_data.items() 
            if k not in ["conversation_history", "metadata"]
        })
        
        return response_data
        
    except Exception as e:
        logger.error("Error in chat processing (request %s): %s", request_id, str(e), exc_info=True)
        error_response = _create_error_response(request_id, chat_request, str(e))
        
        # Add error to conversation if possible
        if 'conversation' in locals():
            conversation.add_message(
                role="assistant",
                content=error_response["message"],
                error=str(e),
                success=False
            )
            error_response["conversation_history"] = _format_conversation_history(conversation.get_messages())
            
        return error_response

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
        logger.error("Error clearing session: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while clearing the session"
        ) from e
