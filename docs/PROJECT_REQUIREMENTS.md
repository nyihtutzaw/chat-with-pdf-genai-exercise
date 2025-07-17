# Chat with PDF - Project Requirements Document

## Project Overview

This document outlines the requirements, architecture, data flow, and file structure for the "Chat with PDF" project - a backend system that enables intelligent question-answering over a corpus of academic papers using modern LLM architectures.

## Core Requirements

### Functional Requirements

1. **PDF Document Processing**
   - Ingest and process academic papers in PDF format
   - Extract text content and relevant metadata
   - Store processed content in a vector database for efficient retrieval

2. **Question Answering**
   - Answer user questions based on the content of provided PDF documents
   - Handle ambiguous queries with clarification mechanisms
   - Support follow-up questions within a user session
   - Provide sources/references for answers when available

3. **Web Search Integration**
   - Perform web searches when explicitly requested by the user
   - Fall back to web search when answers cannot be found in the PDF corpus
   - Integrate with web search APIs (Tavily, DuckDuckGo, or SerpAPI)

4. **Session Management**
   - Maintain conversation context within a user session
   - Support clearing of session memory
   - Handle one user session at a time (multi-user support not required)

### Technical Requirements

1. **Backend Framework**
   - Programming Language: Python
   - Application Server: FastAPI or Flask
   - RESTful API endpoints for question answering and memory management

2. **LLM Integration**
   - Use any LLM provider (OpenAI, Anthropic, etc.)
   - Implement LangChain and/or LlamaIndex for LLM orchestration
   - Apply Retrieval-Augmented Generation (RAG) techniques

3. **Multi-Agent Architecture**
   - Implement LangGraph-based multi-agent system
   - Design agents with specific responsibilities and clear interfaces
   - Orchestrate agent interactions for complex query handling

4. **Containerization**
   - Provide Docker and docker-compose configuration
   - Enable easy local deployment and testing

## Data Flow

```
┌─────────────┐     ┌───────────────┐     ┌─────────────────┐
│ PDF Documents│────▶│ PDF Ingestion │────▶│ Vector Database │
└─────────────┘     └───────────────┘     └────────┬────────┘
                                                  │
                                                  ▼
┌─────────────┐     ┌───────────────┐     ┌─────────────────┐
│  User Query  │────▶│  Orchestrator │◀───▶│   PDF QA Agent  │
└──────┬──────┘     │     Agent     │     └─────────────────┘
       │            └───────┬───────┘
       │                    │
       │                    ▼
┌──────▼──────┐     ┌───────────────┐     ┌─────────────────┐
│   Response   │◀────│  Router Agent │◀───▶│ Web Search Agent│
└─────────────┘     └───────┬───────┘     └────────┬────────┘
                           │                       │
                           ▼                       ▼
                    ┌───────────────┐     ┌─────────────────┐
                    │Clarifier Agent│     │   Web Search    │
                    └───────────────┘     │      API        │
                                          └─────────────────┘
```

### Query Processing Flow

1. **User Query Submission**
   - User submits a question via API
   - Query is received by the Orchestrator Agent

2. **Query Analysis and Routing**
   - Orchestrator passes query to Router Agent
   - Router determines if query is:
     - Ambiguous (needs clarification)
     - Answerable from PDFs
     - Requires web search
     - Explicitly requests web search

3. **Clarification Process** (if needed)
   - Ambiguous queries are sent to Clarifier Agent
   - Clarifier formulates clarification questions
   - User provides additional context
   - Refined query is routed appropriately

4. **PDF-Based Answering**
   - PDF QA Agent retrieves relevant chunks from vector database
   - LLM generates answer based on retrieved content
   - Sources are tracked and included in response

5. **Web Search Process** (if needed)
   - Web Search Agent formulates search query
   - Query is sent to selected web search API
   - Results are processed and formatted
   - LLM generates answer based on search results

6. **Response Generation**
   - Final answer is compiled with sources
   - Response is returned to user via API
   - Conversation context is updated in session memory

## Architecture

### Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  LangGraph Framework                     │
│                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐    │
│  │ Orchestrator│──▶│   Router    │──▶│  Clarifier  │    │
│  │    Agent    │◀──│    Agent    │◀──│    Agent    │    │
│  └─────────────┘   └─────────────┘   └─────────────┘    │
│         │                │                              │
│         │                │                              │
│         ▼                ▼                              │
│  ┌─────────────┐   ┌─────────────┐                      │
│  │   PDF QA    │   │ Web Search  │                      │
│  │    Agent    │   │    Agent    │                      │
│  └─────────────┘   └─────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

1. **Orchestrator Agent**
   - Entry point for user queries
   - Manages overall conversation flow
   - Coordinates between other agents
   - Handles final response formatting

2. **Router Agent**
   - Analyzes query intent and content
   - Decides appropriate processing path
   - Routes queries to specialized agents
   - Combines responses when necessary

3. **Clarifier Agent**
   - Detects ambiguous or vague queries
   - Generates clarification questions
   - Refines queries based on user feedback
   - Improves query specificity

4. **PDF QA Agent**
   - Retrieves relevant content from vector database
   - Generates answers based on PDF content
   - Handles follow-up questions with context
   - Provides source citations

5. **Web Search Agent**
   - Formulates effective search queries
   - Interacts with web search APIs
   - Processes and filters search results
   - Generates answers from web content

### System Components

1. **API Layer**
   - RESTful endpoints for user interaction
   - Request validation and error handling
   - Response formatting and status codes

2. **Vector Database**
   - Stores embeddings of PDF content
   - Enables semantic search over documents
   - Supports efficient retrieval of relevant chunks

3. **Memory Management**
   - Maintains conversation history
   - Stores relevant context for follow-up questions
   - Supports memory clearing functionality

4. **LLM Integration**
   - Connects to LLM provider APIs
   - Handles prompt engineering and context management
   - Manages token limits and rate limiting

## File Structure

```
chat-with-pdf/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point
│   ├── api/                     # API endpoints
│   │   ├── __init__.py
│   │   └── routes.py            # API routes definition
│   ├── agents/                  # Multi-agent architecture
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Main agent orchestrator
│   │   ├── clarifier.py         # Agent for handling ambiguous queries
│   │   ├── pdf_qa.py            # Agent for PDF-based QA
│   │   ├── web_search.py        # Agent for web search
│   │   └── router.py            # Agent for routing between PDF and web
│   ├── core/                    # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration settings
│   │   └── memory.py            # Session-based memory management
│   ├── services/                # External services integration
│   │   ├── __init__.py
│   │   ├── llm.py               # LLM provider integration
│   │   ├── web_search.py        # Web search API integration
│   │   └── pdf_ingestion.py     # PDF processing and ingestion
│   └── utils/                   # Utility functions
│       ├── __init__.py
│       └── helpers.py           # Helper functions
├── data/                        # Data storage
│   ├── pdfs/                    # PDF storage
│   └── vector_store/            # Vector embeddings storage
├── scripts/
│   └── ingest_pdfs.py           # Script to ingest PDFs into vector store
├── tests/                       # Unit and integration tests
│   ├── __init__.py
│   ├── test_api.py
│   └── test_agents.py
├── .env.example                 # Example environment variables
├── .gitignore                   # Git ignore file
├── Dockerfile                   # Docker configuration
├── docker-compose.yml           # Docker Compose configuration
├── requirements.txt             # Python dependencies
├── PROJECT_REQUIREMENTS.md      # This document
└── README.md                    # Project documentation
```

## API Endpoints

### Question Answering

```
POST /api/v1/ask
```

Request Body:
```json
{
  "question": "How many examples are enough for good accuracy?",
  "session_id": "user123",
  "force_web_search": false
}
```

Response:
```json
{
  "answer": "The number of examples needed for good accuracy depends on the dataset and the accuracy target. According to Smith et al. (2023), for text classification tasks, at least 100 examples per class are typically needed to achieve 85% accuracy with transformer models.",
  "sources": [
    {
      "document": "Smith_et_al_2023.pdf",
      "page": 7,
      "text": "Our experiments show that 100 examples per class yields 85% accuracy on average across tested datasets."
    }
  ],
  "clarification_needed": false,
  "web_search_used": false,
  "confidence": 0.87
}
```

### Memory Management

```
DELETE /api/v1/memory/{session_id}
```

Response:
```json
{
  "status": "success",
  "message": "Memory cleared for session user123"
}
```

## Real-World Scenarios

### 1. Ambiguous Questions

Example: "How many examples are enough for good accuracy?"

System should:
- Detect ambiguity ("enough" is vague)
- Request clarification about dataset and accuracy target
- Use clarified information to provide a specific answer

### 2. PDF-Only Queries

Example: "Which prompt template gave the highest zero-shot accuracy on Spider in Zhang et al. (2024)?"

System should:
- Identify this as a PDF-specific query
- Retrieve relevant content from Zhang et al. paper
- Provide the specific answer (SimpleDDL-MD-Chat template with 65-72% EX)

### 3. Out-of-Scope Queries

Example: "What did OpenAI release this month?"

System should:
- Recognize this is not covered in the PDFs
- Initiate web search automatically
- Return information from recent web sources
- Indicate that the answer came from web search, not PDFs

## Future Improvements

1. **Multi-User Support**
   - Extend memory management for multiple concurrent users
   - Implement user authentication and authorization

2. **Enhanced PDF Processing**
   - Improve handling of tables, figures, and mathematical notation
   - Add support for extracting and reasoning over charts and diagrams

3. **Advanced Clarification**
   - Implement more sophisticated disambiguation techniques
   - Support multi-turn clarification dialogues

4. **Performance Optimization**
   - Implement caching for common queries
   - Optimize vector retrieval for larger document sets

5. **Expanded Web Search**
   - Integrate with additional search providers
   - Implement web content summarization and fact-checking

6. **UI Integration**
   - Develop a simple web interface for direct interaction
   - Add visualization of sources and confidence levels
