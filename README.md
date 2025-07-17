# Chat with PDF - Academic Paper Q&A System

A sophisticated backend system for intelligent question-answering over academic PDF papers using FastAPI and modern AI technologies.

## Features

- **FastAPI** backend with async support and automatic API documentation
- **Multi-Agent Architecture** for handling complex queries
- **Retrieval-Augmented Generation (RAG)** for accurate, source-based answers
- **Session-based Memory** for contextual conversations
- **Web Search Integration** for queries requiring external information
- **Containerized** with Docker for easy deployment
- **Production-ready** configuration with environment variables
- **CORS** support for frontend integration
- **Health Check** endpoint for monitoring
- **Interactive API Documentation** with Swagger UI and ReDoc

## Prerequisites

- Python 3.10+
- Docker 20.10+ and Docker Compose v2.0+
- Git
- (Optional) OpenAI API key for LLM integration

## Quick Start

### With Docker (Recommended)

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/chat-with-pdf.git
   cd chat-with-pdf
   ```

2. Copy the example environment file and update with your settings:

   ```bash
   cp .env.example .env
   # Edit .env file with your API keys and settings
   ```

3. Build and start the services:

   ```bash
   docker-compose up --build -d
   ```

4. Access the API:

   - API: http://localhost:8000
   - Swagger UI: http://localhost:8000/api/v1/docs
   - ReDoc: http://localhost:8000/api/v1/redoc

### Local Development

1. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:

   ```bash
   cp .env.example .env
   # Edit .env file with your settings
   ```

4. Run the development server:

   ```bash
   uvicorn app.main:app --reload
   ```

## Project Structure

```text
chat-with-pdf/
├── app/                           # Main application package
│   ├── api/                       # API endpoints and routes
│   │   ├── __init__.py
│   │   ├── routers/               # API route modules
│   │   │   ├── __init__.py
│   │   │   ├── chat.py            # Chat endpoints
│   │   │   └── health.py          # Health check endpoint
│   │   └── dependencies.py        # API dependencies
│   │
│   ├── config/                    # Configuration management
│   │   ├── __init__.py
│   │   ├── config.py              # Main configuration
│   │   └── cors.py                # CORS configuration
│   │
│   └── main.py                    # Application entry point
│
├── data/                          # Data directory for PDF storage
│   └── .gitkeep
│
├── tests/                         # Test files (to be added)
│   └── __init__.py
│
├── .dockerignore
├── .env.example                  # Example environment variables
├── .gitignore
├── .pre-commit-config.yaml       # Pre-commit hooks configuration
├── docker-compose.yml            # Docker Compose configuration
├── Dockerfile                    # Docker configuration
├── pyproject.toml               # Project metadata and build configuration
├── README.md                    # This file
└── requirements.txt             # Project dependencies
```

## API Documentation

### Health Check
- `GET /api/v1/health` - Check API health status

### Chat

- `POST /api/v1/ask` - Ask a question about PDF content

  Request body:

  ```json
  {
    "question": "What is the main contribution of this paper?",
    "session_id": "optional-session-id"
  }
  ```

## Development

### Environment Variables

Create a `.env` file based on `.env.example` and configure:

3. **Run the development server**
   ```bash
   uvicorn app.main:app --reload
   ```

## License

This project is licensed under the MIT License.
