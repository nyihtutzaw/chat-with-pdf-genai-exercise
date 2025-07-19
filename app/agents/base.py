"""Base agent implementation."""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
   
    def __init__(self, name: str):
      
        self.name = name
    
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
      
        pass
