"""Package for application configuration."""

from .config import Settings, init_db
from .cors import setup_cors
from .llm import LLMConfig, MockChatModel, IntentType, RouterResponse

settings = Settings()

__all__ = [
    "settings", 
    "setup_cors", 
    "init_db",
    "LLMConfig",
    "MockChatModel",
    "IntentType",
    "RouterResponse"
]

