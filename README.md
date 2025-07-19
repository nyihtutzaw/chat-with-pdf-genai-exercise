# Chat with PDF - AI-Powered Document Assistant

## Quick Start with Docker

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- OpenAI API key

### Running the Application

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd chat-with-pdf
   ```

2. **Set up environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   nano .env
   ```

3. **Build and start the services**:

   ```bash
   docker-compose up -d --build
   ```

   This will start:
   - Web application (FastAPI)
   - Qdrant vector database
   - Redis for caching
   - Monitoring tools

4. **Add PDF documents**:

   Place your PDF files in the `data/pdfs` directory. The system will automatically process and index them when the container starts.

5. **Access the application**:
   > **Note**: The first startup may take a few minutes as it processes and indexes your PDFs.
   - Web Interface: [http://localhost:8000](http://localhost:8000)
   - API Documentation: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
   - Qdrant Dashboard: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### Stopping the Application

To stop all services:

```bash
docker-compose down
```

### Viewing Logs

View application logs:

```bash
docker-compose logs -f web
```

View Qdrant logs:

```bash
docker-compose logs -f qdrant
```

## Documentation

### Core Architecture
- [System Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md) - High-level overview of system components and technologies
- [Agent Orchestration](docs/AGENT_ORCHESTRATION.md) - How agents work together to process queries
- [Intent Clarification](docs/INTENT_CLARIFICATION.md) - How the system handles ambiguous queries
- [Data Ingestion](docs/DATA_INGESTION.md) - Details on how documents are processed and indexed

### Agent Documentation
- [Response Agent](docs/RESPONSE_AGENT.md) - Formats and presents search results to users
- [Web Search Agent](docs/WEB_SEARCH_AGENT.md) - Handles web search functionality
- [PDF Query Agent](docs/PDF_QUERY_AGENT.md) - Processes and retrieves information from PDF documents

### Project Analysis
- [Limitations and Future Improvements](docs/limitations_and_improvements.md) - Current limitations and proposed enhancements for the system
