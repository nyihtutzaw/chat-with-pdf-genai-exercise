# LLM Router Design

## Overview
The LLM Router is responsible for determining the appropriate action based on user input. It classifies queries into different categories and routes them to the appropriate handler.

## Categories
1. **Greeting** - Simple greetings or casual conversation
2. **PDF Query** - Questions about the PDF content
3. **Web Search** - Queries that require web search
4. **Clarification Needed** - When the query is ambiguous

## Implementation Details

### Router LLM
- Uses OpenAI's GPT model for classification
- Takes user input and returns a structured response with:
  - `intent`: The determined intent (greeting, pdf_query, web_search, clarification_needed)
  - `message`: A friendly message to the user
  - `needs_clarification`: Boolean indicating if clarification is needed
  - `clarification_questions`: List of questions to ask for clarification if needed

### API Endpoint
```
POST /api/v1/chat
{
    "message": "user's message",
    "session_id": "optional-session-id"
}
```

### Response Format
```json
{
    "intent": "greeting",
    "message": "Hello! How can I assist you today?",
    "needs_clarification": false,
    "clarification_questions": []
}
```

## Error Handling
- Invalid API key
- Rate limiting
- Timeout from OpenAI API
- Invalid input format
