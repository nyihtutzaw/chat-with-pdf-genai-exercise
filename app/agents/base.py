"""Base agent implementation."""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """Base class for all agents.
    
    This abstract base class defines the interface that all agents must implement.
    Each agent must implement the `process` method which takes a state dictionary
    and returns an updated state dictionary.
    """
    
    def __init__(self, name: str):
        """Initialize the base agent with a name.
        
        Args:
            name: A unique identifier for the agent
        """
        self.name = name
    
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the input state and return an updated state.
        
        Args:
            state: A dictionary containing the current conversation state
            
        Returns:
            The updated state dictionary
        """
        pass
