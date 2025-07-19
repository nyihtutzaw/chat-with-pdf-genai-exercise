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

For a detailed [high-level overview of the system architecture and components](ARCHITECTURE_OVERVIEW.md), please see the architecture documentation.

For information about the automated PDF ingestion process, see [Data Ingestion Documentation](DATA_INGESTION.md).
