# PDF Document Ingestion Service

## Overview
The PDF Ingestion Service is a Docker-based microservice that processes PDF documents, stores their content in a Qdrant vector database for semantic search, and tracks ingestion status in MySQL. The service automatically processes documents placed in a designated directory.

## Architecture

### Components
1. **PDF Processor** (`scripts/pdf_processor.py`)
   - Handles PDF text extraction and chunking
   - Processes documents with configurable chunking parameters
   - Extracts metadata and page information

2. **Vector Store** (`app/core/vector_store.py`)
   - Manages Qdrant vector database interactions
   - Handles embedding generation using sentence-transformers
   - Implements document storage and retrieval with metadata

3. **Ingestion Tracker** (`app/utils/ingestion_tracker.py`)
   - Tracks ingestion status in MySQL
   - Provides real-time progress updates
   - Handles error tracking and retries

4. **API Endpoints** (`app/api/endpoints/ingestion.py`)
   - REST API for managing and monitoring ingestion
   - Supports querying ingestion status and history

### Key Features
- **Automatic Status Tracking**: Tracks ingestion status in MySQL
- **Environment-Aware**: Works in both Docker and local development
- **Efficient Processing**: Batches documents for better performance
- **Robust Error Handling**: Comprehensive error handling and logging
- **Containerized**: Runs in Docker for easy deployment
- **Configuration via Environment Variables**: All settings are configurable

## Prerequisites
- Docker and Docker Compose
- At least 4GB of free memory for the Qdrant container
- MySQL 8.0+ (included in Docker Compose)

## Quick Start

1. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env if needed
   ```

2. **Start the services**:
   ```bash
   docker-compose up -d
   ```

3. **Place PDFs** in the `data/pdfs` directory:
   ```bash
   mkdir -p data/pdfs
   cp your-documents/*.pdf data/pdfs/
   ```

4. **Monitor ingestion**:
   ```bash
   # View logs
   docker-compose logs -f pdf_ingestion
   
   # Check API documentation
   open http://localhost:8000/api/v1/docs
   ```

## Configuration

### Environment Variables
Edit the `.env` file to configure:

```env
# MySQL Configuration
MYSQL_HOST=localhost  # 'mysql' in Docker
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
MYSQL_ROOT_PASSWORD=

# Qdrant Configuration
QDRANT_URL=http://localhost:6333  # 'http://qdrant:6333' in Docker
QDRANT_COLLECTION=documents

# Processing Parameters
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
BATCH_SIZE=32
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Application Settings
LOG_LEVEL=INFO
DEBUG=true
```

### Directory Structure
```
.
├── data/
│   ├── pdfs/          # Place PDFs here for processing
│   └── processed/     # Successfully processed PDFs are moved here
├── app/
│   ├── core/          # Core functionality
│   ├── models/        # Database models
│   ├── schemas/       # Pydantic schemas
│   └── utils/         # Utility functions
├── scripts/           # Processing scripts
└── tests/             # Test files
```

## API Endpoints

### List All Ingestion Records
```
GET /api/v1/ingestion/
```

### Get Ingestion Status
```
GET /api/v1/ingestion/{ingestion_id}
```

### Get Ingestion by File Path
```
GET /api/v1/ingestion/by-path/{file_path:path}
```