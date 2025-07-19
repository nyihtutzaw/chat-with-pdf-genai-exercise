import logging
from enum import Enum
from typing import Dict, Any, List, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

class MockChatModel(BaseChatModel):
    """Mock LLM for development purposes when no API key is provided."""
    
    def _generate(
        self, messages: List[Union[HumanMessage, SystemMessage]], **kwargs
    ) -> ChatResult:
        """Mock response generation."""
        if any("hello" in msg.content.lower() for msg in messages if hasattr(msg, 'content')):
            response = "Hello! How can I help you today?"
        elif any("pdf" in msg.content.lower() for msg in messages if hasattr(msg, 'content')):
            response = "I can help you with PDF-related questions. What would you like to know?"
        else:
            response = "This is a mock response. In production, I would analyze your query and provide a detailed response."
            
        return ChatResult(
            generations=[{
                'message': AIMessage(content=response),
                'text': response
            }]
        )
    
    def _llm_type(self) -> str:
        return "mock-chat-model"


class IntentType(str, Enum):
    GREETING = "greeting"
    PDF_QUERY = "pdf_query"
    WEB_SEARCH = "web_search"
    CLARIFICATION_NEEDED = "clarification_needed"

class RouterResponse(BaseModel):
    intent: IntentType
    message: str
    needs_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

from app.config.config import settings

class LLMConfig:
    def __init__(
        self, 
        openai_api_key: str = None, 
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.1
    ):
        # Get API key from environment variables if not provided
        self.openai_api_key = openai_api_key or settings.OPENAI_API_KEY
        self.model_name = model_name
        
        # Only validate API key if we're not in debug mode
        if not settings.DEBUG and not self.openai_api_key:
            raise ValueError("OpenAI API key is required. Please set OPENAI_API_KEY environment variable.")
            
        # If in debug mode and no API key, use a mock LLM
        self._use_mock = settings.DEBUG and not self.openai_api_key
        self.temperature = temperature
        self._llm = None
        self._intent_classifier = None
        
    @property
    def is_configured(self) -> bool:
        return bool(self.openai_api_key)
    
    @property
    def llm(self):
        """Lazy initialization of the LLM."""
        if self._llm is None:
            if self._use_mock:
                logger.warning("Using mock LLM for development. Set OPENAI_API_KEY for real responses.")
                self._llm = MockChatModel()
            else:
                self._llm = ChatOpenAI(
                    model_name=self.model_name,
                    temperature=self.temperature,
                    openai_api_key=self.openai_api_key
                )
        return self._llm
