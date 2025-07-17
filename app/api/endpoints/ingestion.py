import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from pathlib import Path

from app import crud, schemas
from app.db.base import get_db

# Configure logger
logger = logging.getLogger(__name__)

# Error message constants
INGESTION_NOT_FOUND = "Ingestion not found"
INGESTION_NOT_FOUND_FOR_FILE = "No ingestion record found for file: {}"

router = APIRouter()

@router.get("/ingestions/", response_model=List[schemas.Ingestion])
def list_ingestions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all ingestion records with pagination.
    
    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        
    Returns:
        List of ingestion records
    """
    return crud.get_ingestions(db, skip=skip, limit=limit)

@router.get("/ingestions/{ingestion_id}", response_model=schemas.Ingestion)
def read_ingestion(
    ingestion_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific ingestion record by ID.
    
    Args:
        ingestion_id: ID of the ingestion record to retrieve
        
    Returns:
        The requested ingestion record
        
    Raises:
        HTTPException: 404 if ingestion record is not found
    """
    db_ingestion = crud.get_ingestion(db, ingestion_id=ingestion_id)
    if db_ingestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=INGESTION_NOT_FOUND
        )
    return db_ingestion

@router.get("/ingestions/file/{file_path:path}", response_model=schemas.Ingestion)
def read_ingestion_by_filepath(
    file_path: str,
    db: Session = Depends(get_db)
):
    """
    Get ingestion record by file path.
    
    Args:
        file_path: Path of the file to get ingestion status for
        
    Returns:
        The ingestion record for the specified file
        
    Raises:
        HTTPException: 404 if no ingestion record is found for the file
    """
    db_ingestion = crud.get_ingestion_by_filepath(db, file_path=file_path)
    if db_ingestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=INGESTION_NOT_FOUND_FOR_FILE.format(file_path)
        )
    return db_ingestion

@router.get("/status/{file_path:path}", response_model=schemas.Ingestion)
async def get_ingestion_status(
    file_path: str,
    db: Session = Depends(get_db)
):
    """
    Get the ingestion status for a specific file.
    
    Args:
        file_path: Path to the file to check status for
        
    Returns:
        Ingestion status with details including:
        - status: Current status (started, in_progress, completed, failed)
        - file_path: Path to the file being processed
        - processed_documents: Number of documents processed
        - total_documents: Total number of documents to process
        - error_message: Error details if processing failed
        - created_at: When the ingestion started
        - updated_at: Last status update time
    
    Raises:
        HTTPException: 404 if no ingestion record is found for the file
    """
    try:
        # Normalize the file path for consistent lookups
        normalized_path = str(Path(file_path).resolve())
        
        # Get the most recent ingestion record for this file
        ingestion = crud.get_ingestion_by_filepath(db, file_path=normalized_path)
        
        if not ingestion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=INGESTION_NOT_FOUND_FOR_FILE.format(file_path)
            )
        
        return ingestion
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the error and return a 500 response
        logger.error(f"Error getting ingestion status for {file_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving ingestion status"
        )
