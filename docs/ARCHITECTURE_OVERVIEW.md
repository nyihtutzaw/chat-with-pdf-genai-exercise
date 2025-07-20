# System Architecture Overview

## Technology Stack

### Core Technologies
- **Backend Framework**: FastAPI (Python 3.10+)
- **Vector Database**: Qdrant with cosine similarity search
- **Embedding Model**: SentenceTransformers (all-MiniLM-L6-v2)
- **Web Search**: DuckDuckGo Search API
- **PDF Processing**: PyPDF2 for text extraction
- **Text Processing**: Regular expressions for text cleaning
- **Containerization**: Docker, Docker Compose
- **API Documentation**: Swagger UI (via FastAPI)

## Multi-Agent Architecture

The system follows a multi-agent architecture with the following components:

### AgentOrchestrator

- Central coordinator for all agent interactions
- Routes messages between agents based on intent
- Maintains conversation state and context
- Handles error recovery and fallback mechanisms

### Agent Types

- **PDF Query Agent**: Handles document-related queries using vector similarity search
- **Web Search Agent**: Manages web search functionality using DuckDuckGo API
  - Performs region-specific searches
  - Filters results by time period
  - Applies safe search filtering
  - Removes duplicate results
- **Response Agent**: Formats and presents final responses

### Workflow

1. User message reception
2. Intent classification
3. Agent routing based on intent
4. Response generation and delivery
5. Context maintenance for follow-ups

## Intent Classification

The system classifies user intents into the following categories:

### Classification Categories

- **Greeting**: Initial interactions and salutations
- **PDF Query**: Questions about uploaded documents
- **Web Search**: General knowledge questions
- **Follow-up**: Context-dependent questions
- **Clarification Needed**: Ambiguous or unclear queries

### Classification Process

- **Intent Recognition**: Rule-based classification
- **Context Management**: In-memory conversation state
- **Fallback**: Default to document search for unclassified queries
- **Handling**: Simple routing based on query patterns

## Response Agent

### Responsibilities

- Formats search results from multiple sources
- Generates user-friendly responses
- Handles empty or error states
- Maintains consistent response formatting

### Features

- Context-aware response generation
- Error handling and fallback messages
- Source attribution for information
- Consistent formatting across responses

## Web Search Agent

### Functionality

- Performs asynchronous web searches using DuckDuckGo API
- Retrieves and processes search results
- Handles rate limiting and errors
- Returns structured data for responses

### Implementation

- **Search Integration**: Direct DuckDuckGo API calls
- **Result Processing**: Result filtering and limiting
- **Performance**: Asynchronous processing

## PDF Query Agent

### Document Handling

- **Storage**: Local filesystem with organized directory structure
- **PDF Processing**: PyPDF2 for text extraction
- **Document Formats**: Support for PDF

### Search Capabilities

- Full-text search across documents
- Metadata-based filtering
- Relevance ranking


## Follow-up Handling

### Context Management

- Tracks conversation history
- Maintains entity context
- Handles coreference resolution
- Manages topic continuity

### Features

- Natural follow-up question handling
- Contextual understanding
- Seamless conversation flow
- Fallback to clarification when needed

## Retrieval-Augmented Generation (RAG) Workflow

### Document Processing

- **Text Extraction**: PyPDF2 for PDF text extraction
- **Text Cleaning**: Regex-based whitespace normalization
- **Chunking**: Fixed-size chunks with configurable overlap
- **Embeddings**: SentenceTransformers (all-MiniLM-L6-v2)
- **Vector Storage**: Qdrant with cosine similarity
- **Metadata**: Page numbers and document references

### Retrieval Process

- **Semantic Search**: Cosine similarity on vector embeddings
- **Scoring**: Pure vector similarity scoring
- **Filtering**: Minimum similarity threshold (0.5)
- **Performance**: Batch processing with async/await

### Response Generation

- **LLM**: OpenAI GPT-4 with custom prompt templates
- **Context Management**: Dynamic context window management
- **Citation**: Automatic source attribution with page numbers
- **Validation**: Response quality heuristics and filtering

---


For a detailed explanation of how these components work together, see the [Agent Orchestration Flow](AGENT_ORCHESTRATION.md) documentation.