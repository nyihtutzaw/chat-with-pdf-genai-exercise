"""LangGraph workflow for conversation management."""
from typing import Dict, List, TypedDict, Annotated, Optional, Any

import logging
from langgraph.graph import StateGraph, END

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from app.services.conversation.state import conversation_manager

# Set up logging
logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    """State for the conversation graph."""
    session_id: str
    input: str
    messages: Annotated[List[Dict], lambda x, y: x + y]
    response: Optional[str]

class ConversationGraph:
    """Manages conversation flow using LangGraph."""
    
    def __init__(self, llm=None):
        self.llm = llm or ChatOpenAI(temperature=0.7)
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        """Create the conversation workflow."""
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("generate_follow_ups", self.generate_follow_ups)
        workflow.add_node("update_conversation", self.update_conversation)
        
        # Define the graph flow
        workflow.add_edge("generate_response", "generate_follow_ups")
        workflow.add_edge("generate_follow_ups", "update_conversation")
        workflow.add_edge("update_conversation", END)
        
        # Set the entry point
        workflow.set_entry_point("generate_response")
        
        return workflow.compile()
    
    async def generate_response(self, state: GraphState) -> Dict:
        """Generate a response to the user's message."""
        # Get conversation history
        conversation = conversation_manager.get_conversation(state["session_id"])
        
        # Create a prompt with conversation history
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI assistant."),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}")
        ])
        
        # Create the chain
        chain = prompt | self.llm | StrOutputParser()
        
        # Get the response
        response = await chain.ainvoke({
            "input": state["input"],
            "chat_history": [
                (msg["role"], msg["content"]) 
                for msg in conversation.get_messages()
            ]
        })
        
        return {"response": response, "messages": [{"role": "assistant", "content": response}]}
    
    def update_conversation(self, state: GraphState) -> Dict:
        """Update the conversation with the response and follow-ups."""
        conversation = conversation_manager.get_conversation(state["session_id"])
        
        # Add the assistant's response if it exists
        if state.get("response"):
            conversation.add_message("assistant", state["response"])
            
            # Update conversation context with the latest response
            if state.get("intent"):
                conversation.update_context(
                    intent=state["intent"],
                    entities=state.get("entities", {}),
                    topics=state.get("topics", [])
                )
        
        # Return updated state with follow-up questions
        return {
            "messages": [],
            "metadata": {
                "session_id": conversation.session_id,
                "updated_at": conversation.updated_at.isoformat()
            }
        }

# Initialize with default LLM
conversation_graph = ConversationGraph()
