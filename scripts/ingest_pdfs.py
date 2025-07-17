#!/usr/bin/env python3
"""
PDF Ingestion Script

This script processes PDF files from the data/pdfs directory and stores their content
in a Qdrant vector database for semantic search.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from tqdm import tqdm

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.pdf_processor import PDFProcessor
from app.core.vector_store import VectorStore
from app.config.config import settings

# Configure logging
def setup_logging():
    """Configure logging to both console and file."""
    settings.LOG_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(settings.LOG_LEVEL)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setLevel(settings.LOG_LEVEL)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

def process_pdfs(
    input_dir: Path,
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int
) -> int:
    """Process all PDFs in the given directory and store in vector database.
    
    Args:
        input_dir: Directory containing PDF files to process
        collection_name: Name of the Qdrant collection
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        batch_size: Number of chunks to process in a batch
        clear_existing: Whether to clear existing vectors before ingestion
        
    Returns:
        Number of document chunks processed and stored
        
    Raises:
        FileNotFoundError: If input directory doesn't exist
        Exception: For any processing or storage errors
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    logger.info(f"Starting PDF ingestion from {input_dir}")
    logger.info(f"Using collection: {collection_name}")
    logger.info(f"Chunk size: {chunk_size}, Overlap: {chunk_overlap}, Batch size: {batch_size}")
    
    # Set the collection name in settings
    from app.config.config import settings
    settings.QDRANT_COLLECTION = collection_name
    
    # Initialize components
    pdf_processor = PDFProcessor(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    vector_store = VectorStore()
    
    # Always clear the collection before ingestion to prevent duplicates
    logger.warning("Clearing existing vectors in collection before ingestion")
    vector_store.clear_collection()
    
    try:
        # Process PDFs and store in vector database
        chunks = []
        total_stored = 0
        
        for chunk in tqdm(
            pdf_processor.process_directory(input_dir),
            desc="Processing PDFs",
            unit="chunk"
        ):
            # Convert chunk to document format
            document = {
                'text': chunk['text'],
                'metadata': {
                    'source': chunk['source'],
                    'page': chunk['page'],
                    'chunk': chunk['chunk_num'],
                    'total_chunks': chunk['total_chunks']
                }
            }
            chunks.append(document)
            
            # Process in batches
            if len(chunks) >= batch_size:
                vector_store.store_documents(chunks)
                total_stored += len(chunks)
                chunks = []
                logger.debug(f"Processed {total_stored} chunks so far")
        
        # Process any remaining chunks
        if chunks:
            vector_store.store_documents(chunks)
            total_stored += len(chunks)
        
        logger.info(f"Successfully processed {total_stored} chunks from {input_dir}")
        return total_stored
        
    except Exception as e:
        logger.error(f"Error during PDF ingestion: {str(e)}", exc_info=True)
        raise

def main() -> None:
    """Main entry point for PDF ingestion."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Ingest PDFs into Qdrant vector store.")
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing PDF files to process"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=os.getenv("QDRANT_COLLECTION", "pdf_documents"),
        help="Qdrant collection name (default: pdf_documents)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=int(os.getenv("CHUNK_SIZE", "1000")),
        help="Chunk size for text splitting (default: 1000)"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=int(os.getenv("CHUNK_OVERLAP", "200")),
        help="Chunk overlap for text splitting (default: 200)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation (default: 32)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=args.log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        total_processed = process_pdfs(
            input_dir=Path(args.input_dir),
            collection_name=args.collection,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size
        )
        
        if total_processed > 0:
            logger.info(f"Successfully processed {total_processed} document chunks")
        else:
            logger.warning("No documents were processed")
            
    except Exception as e:
        logger.error(f"PDF ingestion failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
