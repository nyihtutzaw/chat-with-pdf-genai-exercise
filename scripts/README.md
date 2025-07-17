# PDF Ingestion Script

This directory contains scripts for processing PDF documents and storing them in a vector database for semantic search.

## Scripts

### `ingest_pdfs.py`

The main script for processing PDFs and storing them in the vector database.

#### Usage

```bash
# Process PDFs with default settings
python scripts/ingest_pdfs.py

# Process PDFs from a specific directory
python scripts/ingest_pdfs.py --pdf-dir /path/to/pdfs

# Clear existing vectors before ingestion
python scripts/ingest_pdfs.py --clear

# Set log level
python scripts/ingest_pdfs.py --log-level DEBUG
```

#### Command-line Arguments

- `--pdf-dir`: Directory containing PDF files (default: `./data/pdfs`)
- `--clear`: Clear existing vectors before ingestion (default: `False`)
- `--log-level`: Set the logging level (default: `INFO`)

### `pdf_processor.py`

Handles PDF text extraction and chunking.

### `vector_store.py`

Manages document embeddings and storage in Qdrant.

## Running with Docker

1. Place your PDF files in `./data/pdfs`
2. Start the services:
   ```bash
   docker-compose up -d qdrant
   docker-compose up pdf_ingestion
   ```

3. To clear and re-ingest all documents:
   ```bash
   docker-compose run --rm pdf_ingestion python scripts/ingest_pdfs.py --clear
   ```

## Configuration

Configuration is handled through environment variables. You can set them in a `.env` file:

```ini
# PDF Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=documents

# Logging
LOG_LEVEL=INFO
```

## Logs

Logs are written to `./logs/ingestion.log` by default.
