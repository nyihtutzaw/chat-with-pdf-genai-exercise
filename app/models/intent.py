from enum import Enum
from pydantic import BaseModel

class IntentLabel(str, Enum):
    GREETING = "greeting"
    PDF_QUERY = "pdf_query"
    WEB_SEARCH = "web_search"
    CLARIFICATION_NEEDED = "clarification_needed"

class IntentPrediction(BaseModel):
    intent: IntentLabel
    confidence: float
    reasoning: str
