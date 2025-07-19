import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Generator

from pypdf import PdfReader
from tqdm import tqdm

from app.config.config import settings

logger = logging.getLogger(__name__)

class PDFProcessor:
    """Handles PDF text extraction and chunking."""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """Initialize the PDF processor with chunking settings."""
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be smaller than chunk size")
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """Extract text from a PDF file, returning a list of (page_num, text) tuples."""
        try:
            with open(pdf_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                return [
                    (i + 1, re.sub(r'\s+', ' ', page.extract_text()).strip())
                    for i, page in enumerate(pdf_reader.pages)
                    if page.extract_text().strip()
                ]
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            raise
    
    def _create_chunk(self, chunks: List[str], current_chunk: List[str]) -> None:
        if current_chunk:
            chunks.append(' '.join(current_chunk))
    
    def _should_finalize_chunk(self, current_length: int, sentence: str) -> bool:
        return current_length + len(sentence) > self.chunk_size and current_length > 0
    
    def _prepare_next_chunk(self, current_chunk: List[str]) -> Tuple[List[str], int]:
        overlap = max(0, len(current_chunk) - self.chunk_overlap)
        next_chunk = current_chunk[-overlap:] if overlap > 0 else []
        next_length = sum(len(s) + 1 for s in next_chunk)
        return next_chunk, next_length
    
    def _chunk_text(self, text: str) -> List[str]:
        if not text.strip():
            return []
        
        sentences = [s.strip() for s in re.split(r'(?<=[.!?]) +', text) if s.strip()]
        if not sentences:
            return []
            
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            if self._should_finalize_chunk(current_length, sentence):
                self._create_chunk(chunks, current_chunk)
                current_chunk, current_length = self._prepare_next_chunk(current_chunk)
                
            current_chunk.append(sentence)
            current_length += len(sentence) + 1  # +1 for space
            
            if current_length >= self.chunk_size:
                self._create_chunk(chunks, current_chunk)
                current_chunk, current_length = self._prepare_next_chunk(current_chunk)
        
        # Add the last chunk if not empty
        self._create_chunk(chunks, current_chunk)
        return chunks
    
    def process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        logger.info(f"Processing PDF: {pdf_path.name}")
        chunks = []
        
        try:
            page_texts = self._extract_text_from_pdf(pdf_path)
            
            for page_num, text in page_texts:
                # Split text into chunks
                page_chunks = self._chunk_text(text)
                
                # Create chunk metadata
                for i, chunk in enumerate(page_chunks, 1):
                    chunk_metadata = {
                        "text": chunk,
                        "source": pdf_path.name,
                        "page": page_num,
                        "chunk_num": i,
                        "total_chunks": len(page_chunks)
                    }
                    chunks.append(chunk_metadata)
                    
            logger.info(f"Processed {len(chunks)} chunks from {pdf_path.name}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path.name}: {str(e)}", exc_info=True)
            raise
    
    def process_directory(self, pdf_dir: Path) -> Generator[Dict[str, Any], None, None]:
        if not pdf_dir.exists():
            raise FileNotFoundError(f"Directory not found: {pdf_dir}")
            
        pdf_files = sorted(pdf_dir.glob("*.pdf"))  # Sort for consistent ordering
        if not pdf_files:
            logger.warning(f"No PDF files found in {pdf_dir}")
            return
            
        logger.info(f"Found {len(pdf_files)} PDF files to process in {pdf_dir}")
        processed_files = 0
        
        for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
            try:
                chunks = self.process_pdf(pdf_file)
                for chunk in chunks:
                    yield chunk
                processed_files += 1
                
            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {str(e)}", exc_info=True)
                continue
                
        logger.info(f"Successfully processed {processed_files}/{len(pdf_files)} PDF files")
