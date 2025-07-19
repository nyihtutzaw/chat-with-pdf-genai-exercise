#!/usr/bin/env python3

import argparse
import logging
import sys
import time
from pathlib import Path

from tqdm import tqdm

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.pdf_processor import PDFProcessor
from app.services.vector_store import VectorStore
from app.config.config import settings
from app.utils.ingestion_tracker import IngestionTracker

# Configure logging
def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Always show INFO and above in console
    console_handler.setFormatter(formatter)
    
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setLevel(settings.LOG_LEVEL)
    file_handler.setFormatter(formatter)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()

def process_pdfs(
    input_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int
) -> int:
    
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {input_dir}")
        return 0
    
    vector_store = VectorStore()
    
    pdf_processor = PDFProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    total_stored = 0
    
    try:
        for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
            file_path = str(pdf_file.absolute())
            logger.info(f"Processing {pdf_file.name}")
            
            tracker = IngestionTracker(file_path)
            try:
                tracker.start_ingestion()
                
                chunks = pdf_processor.process_pdf(pdf_file)
                tracker.mark_in_progress(total_documents=len(chunks))
                
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    vector_store.store_documents(batch)
                    total_stored += len(batch)
                    tracker.update_progress(processed_documents=total_stored)
                    logger.debug(f"Processed {total_stored} chunks so far")
                
                tracker.mark_completed(processed_documents=total_stored)
                
            except Exception as e:
                error_msg = f"Error processing {pdf_file.name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                if 'tracker' in locals():
                    tracker.mark_failed(error_message=error_msg)
                raise
            finally:
                if 'tracker' in locals() and tracker.db:
                    tracker.db.close()
        
        logger.info(f"Successfully processed {total_stored} chunks from {input_dir}")
        return total_stored
        
    except Exception as e:
        logger.error(f"Fatal error during PDF ingestion: {str(e)}", exc_info=True)
        raise

def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs into vector database with status tracking")
    parser.add_argument(
        "--input-dir",
        type=str,
        default=str(settings.PDF_DIR),
        help=f"Directory containing PDFs (default: {settings.PDF_DIR})"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=settings.QDRANT_COLLECTION,
        help=f"Qdrant collection name (default: {settings.QDRANT_COLLECTION})"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=settings.CHUNK_SIZE,
        help=f"Chunk size in characters (default: {settings.CHUNK_SIZE})"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=settings.CHUNK_OVERLAP,
        help=f"Chunk overlap in characters (default: {settings.CHUNK_OVERLAP})"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Number of chunks to process in a batch (default: 32)"
    )
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting PDF ingestion from {args.input_dir}")
        logger.info(f"Using collection: {args.collection}")
        logger.info(f"Chunk size: {args.chunk_size}, Overlap: {args.chunk_overlap}, Batch size: {args.batch_size}")
        
        start_time = time.time()
        
        total_processed = process_pdfs(
            input_dir=Path(args.input_dir),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Successfully processed {total_processed} chunks in {elapsed:.2f} seconds")
        return 0
        
    except Exception as e:
        logger.error(f"PDF ingestion failed: {str(e)}", exc_info=True)
        return 1
    finally:
        from app.db.base import engine
        engine.dispose()

if __name__ == "__main__":
    main()
