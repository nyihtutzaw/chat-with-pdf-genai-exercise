# LLM Router Implementation

## Overview
This document describes the implementation of the LLM Router, which classifies user queries and routes them to the appropriate handler.

## Files Structure
```
app/
├── api/
│   ├── endpoints/
│   │   └── chat.py          # Chat API endpoints
│   └── models/
│       └── chat.py          # Request/Response models
├── core/
│   └── config/
│       └── llm_config.py    # LLM configuration and types
└── services/
    └── llm_router.py        # Core routing logic
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements/llm_requirements.txt
```

2. Set up environment variables in `.env`:
```env
OPENAI_API_KEY=your-api-key-here
```

## Usage

### API Endpoint
```
POST /api/v1/chat
Content-Type: application/json

{
    "message": "your message here",
    "session_id": "optional-session-id"
}
```

### Example Responses

1. **Greeting**:
```json
{
    "intent": "greeting",
    "message": "Hello! How can I assist you with the PDF documents today?",
    "needs_clarification": false,
    "clarification_questions": []
}
```

2. **Web Search**:
```json
{
    "intent": "web_search",
    "message": "I'll help you find that information online. Could you please clarify what you're looking for?",
    "needs_clarification": true,
    "clarification_questions": [
        "What specific information are you looking for?",
        "Are you looking for recent information or something specific?"
    ]
}
```

3. **PDF Query**:
```json
{
    "intent": "pdf_query",
    "message": "I'll search through the PDF documents for that information.",
    "needs_clarification": false,
    "clarification_questions": []
}
```

## Testing

You can test the endpoint using curl:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

## Next Steps

1. Implement actual PDF query handling
2. Add web search integration
3. Implement session management for conversation history
4. Add more sophisticated intent detection
5. Implement rate limiting and caching
