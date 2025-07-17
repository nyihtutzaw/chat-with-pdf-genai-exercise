from enum import Enum
from pydantic import BaseModel, Field
from typing import List

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

class LLMConfig:
    def __init__(self, openai_api_key: str, model_name: str = "gpt-3.5-turbo"):
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        
    @property
    def is_configured(self) -> bool:
        return bool(self.openai_api_key)
