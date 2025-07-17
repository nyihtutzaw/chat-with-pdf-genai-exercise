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
    follow_up_questions: List[str]

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
    
    async def generate_follow_ups(self, state: GraphState) -> Dict[str, any]:
        """Generate follow-up questions based on conversation context."""
        conversation = conversation_manager.get_conversation(state["session_id"])
        
        # Get conversation context
        context = conversation.get_context()
        last_intent = context.get('last_intent')
        topics = context.get('conversation_topics', [])
        
        # Get recent messages for context
        context_messages = conversation.get_messages(limit=5)
        
        # Create prompt for follow-up generation
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI assistant helping with a conversation. 
            Generate 2-3 relevant follow-up questions based on the conversation history.
            Focus on the most recent topics and maintain context.
            
            Current conversation topics: {topics}
            Last detected intent: {intent}"""),
            ("human", """Conversation history (most recent first):
            {conversation}
            
            Generate 2-3 specific follow-up questions that would help continue this conversation naturally.
            Format each question on a new line.
            Questions:""")
        ])
        
        # Create the chain
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            # Get follow-up questions
            follow_ups = await chain.ainvoke({
                "conversation": "\n".join(
                    f"{msg['role']}: {msg['content']}" 
                    for msg in reversed(context_messages)  # Show in chronological order
                ),
                "topics": ", ".join(topics[-3:]) if topics else "No specific topics yet",
                "intent": last_intent or "Not specified"
            })
            
            # Parse the response into a list of questions
            questions = [
                q.strip() 
                for q in follow_ups.split("\n") 
                if q.strip() and not q.strip().startswith(("1.", "2.", "3.", "-", "*"))
            ][:3]  # Limit to 3 questions
            
            # Store follow-up questions in conversation state
            conversation.add_follow_up_questions(questions)
            
            return {
                "follow_up_questions": questions,
                "metadata": {
                    "intent": last_intent,
                    "topics": topics[-3:]
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return {"follow_up_questions": []}
    
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
        
        # Get current follow-up questions from conversation state
        current_follow_ups = conversation.get_follow_up_questions()
        
        # Return updated state with follow-up questions
        return {
            "messages": [],
            "follow_up_questions": current_follow_ups,
            "metadata": {
                "session_id": conversation.session_id,
                "updated_at": conversation.updated_at.isoformat()
            }
        }

# Initialize with default LLM
conversation_graph = ConversationGraph()
