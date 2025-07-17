import logging
import traceback
from typing import Optional
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.crud import crud_ingestion
from app.models.ingestion import IngestionStatus
from app.schemas.ingestion import IngestionCreate, IngestionUpdate

class IngestionTracker:
    """
    Helper class to track PDF ingestion status in the database.
    
    This class provides methods to track the progress of PDF file ingestion,
    including starting, updating, and completing the ingestion process.
    It maintains a database connection to persist the ingestion status.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize the tracker for a specific file.
        
        Args:
            file_path: Path to the file being ingested
        """
        self.file_path = str(file_path)
        self.ingestion_id = None
        self.db: Optional[Session] = None
        self._connect()
    
    def _connect(self):
        """
        Initialize database connection.
        
        Raises:
            RuntimeError: If database connection cannot be established
        """
        try:
            self.db = next(get_db())
        except Exception as e:
            raise RuntimeError("Failed to connect to the database") from e
    
    def _ensure_connection(self):
        """
        Ensure we have an active database connection.
        
        Will attempt to reconnect if the connection is lost.
        """
        try:
            if self.db is None or not self.db.is_active:
                self._connect()
        except Exception as e:
            raise RuntimeError("Failed to maintain database connection") from e
    
    def start_ingestion(self) -> int:
        """
        Mark ingestion as started in the database.
        
        Returns:
            int: The ID of the created ingestion record
            
        Raises:
            RuntimeError: If ingestion record cannot be created
        """
        try:
            self._ensure_connection()
            ingestion = crud_ingestion.create_ingestion(
                self.db,
                IngestionCreate(
                    file_path=self.file_path,
                    status=IngestionStatus.STARTED,
                    total_documents=0,
                    processed_documents=0
                )
            )
            self.ingestion_id = ingestion.id
            return self.ingestion_id
        except Exception as e:
            raise RuntimeError(f"Failed to start ingestion tracking: {str(e)}") from e
    
    def update_status(
        self,
        status: IngestionStatus,
        total_documents: Optional[int] = None,
        processed_documents: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update the ingestion status in the database.
        
        Args:
            status: The new status of the ingestion
            total_documents: Optional total number of documents to process
            processed_documents: Optional number of documents processed so far
            error_message: Optional error message if the ingestion failed
            
        Returns:
            bool: True if the update was successful, False otherwise
            
        Raises:
            ValueError: If ingestion was not started or update fails
            RuntimeError: If database operation fails
        """
        try:
            if self.ingestion_id is None:
                raise ValueError("Ingestion not started. Call start_ingestion() first.")
                
            self._ensure_connection()
            
            update_data = {"status": status}
            if total_documents is not None:
                update_data["total_documents"] = total_documents
            if processed_documents is not None:
                update_data["processed_documents"] = processed_documents
            if error_message is not None:
                update_data["error_message"] = error_message
                
            # First get the ingestion record
            db_ingestion = crud_ingestion.get_ingestion(self.db, ingestion_id=self.ingestion_id)
            if not db_ingestion:
                raise ValueError(f"No ingestion found with ID {self.ingestion_id}")
                
            # Then update it
            result = crud_ingestion.update_ingestion(
                self.db,
                db_ingestion=db_ingestion,
                ingestion_update=IngestionUpdate(**update_data)
            )
            
            if not result:
                raise ValueError(f"Failed to update status to {status}")
                
            return True
            
        except Exception as e:
            raise RuntimeError(f"Failed to update ingestion status: {str(e)}") from e
        
    def mark_in_progress(self, total_documents: int) -> bool:
        """
        Mark ingestion as in progress with the total number of documents to process.
        
        Args:
            total_documents: Total number of documents to be processed
            
        Returns:
            bool: True if the update was successful
            
        Raises:
            RuntimeError: If the status update fails
        """
        return self.update_status(
            status=IngestionStatus.IN_PROGRESS,
            total_documents=total_documents,
            processed_documents=0
        )
        
    def update_progress(self, processed_documents: int) -> bool:
        """
        Update the progress of document processing.
        
        Args:
            processed_documents: Number of documents processed so far
            
        Returns:
            bool: True if the update was successful
            
        Raises:
            RuntimeError: If the progress update fails
        """
        return self.update_status(
            status=IngestionStatus.IN_PROGRESS,
            processed_documents=processed_documents
        )
        
    def mark_completed(self, processed_documents: int) -> bool:
        """
        Mark ingestion as successfully completed.
        
        Args:
            processed_documents: Total number of documents processed
            
        Returns:
            bool: True if the update was successful
            
        Raises:
            RuntimeError: If the completion status update fails
        """
        return self.update_status(
            status=IngestionStatus.COMPLETED,
            processed_documents=processed_documents
        )
        
    def mark_failed(self, error_message: str) -> bool:
        """
        Mark ingestion as failed with an error message.
        
        Args:
            error_message: Description of the error that caused the failure
            
        Returns:
            bool: True if the failure status was recorded successfully
            
        Raises:
            RuntimeError: If the failure status update fails
        """
        return self.update_status(
            status=IngestionStatus.FAILED,
            error_message=error_message
        )
        
    def __enter__(self):
        """
        Context manager entry point.
        
        Returns:
            IngestionTracker: The current instance
            
        Raises:
            RuntimeError: If ingestion cannot be started
        """
        self.start_ingestion()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.
        
        Handles cleanup and ensures proper status is set if an exception occurred.
        """
        try:
            if exc_type is not None:
                error_msg = f"{exc_type.__name__}: {str(exc_val)}"
                if exc_tb:
                    error_msg += f"\n{''.join(traceback.format_tb(exc_tb))}"
                self.mark_failed(error_msg)
            
            if self.db:
                self.db.close()
                
        except Exception as e:
            # Log any errors during cleanup but don't mask the original exception
            logger = logging.getLogger(__name__)
            logger.error(f"Error during ingestion tracker cleanup: {str(e)}")
            
        # Don't suppress any exceptions
        return False
