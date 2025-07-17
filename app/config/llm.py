from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

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

class LLMConfig:
    def __init__(
        self, 
        openai_api_key: str, 
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.1
    ):
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
        self._intent_classifier = None
        
    @property
    def is_configured(self) -> bool:
        return bool(self.openai_api_key)
    
    @property
    def llm(self):
        if not self._llm:
            self._llm = ChatOpenAI(
                api_key=self.openai_api_key,
                model_name=self.model_name,
                temperature=self.temperature
            )
        return self._llm
    
    def get_intent_classifier(self):
        if not self._intent_classifier:
            intent_prompt = """
            Classify the user's intent based on their message. 
            Choose one of: greeting, pdf_query, web_search, or clarification_needed.
            
            User message: {message}
            
            Response format (JSON):
            {{
                "intent": "one_of_the_intent_types",
                "confidence": 0.0-1.0,
                "reasoning": "brief_explanation"
            }}
            """
            
            prompt = ChatPromptTemplate.from_template(intent_prompt)
            self._intent_classifier = (
                {"message": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
        return self._intent_classifier
