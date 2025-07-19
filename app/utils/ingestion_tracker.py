import logging
import traceback
from typing import Optional
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.crud import crud_ingestion
from app.models.ingestion import IngestionStatus,IngestionCreate, IngestionUpdate

class IngestionTracker:
   
    
    def __init__(self, file_path: str):
      
        self.file_path = str(file_path)
        self.ingestion_id = None
        self.db: Optional[Session] = None
        self._connect()
    
    def _connect(self):
        try:
            self.db = next(get_db())
        except Exception as e:
            raise RuntimeError("Failed to connect to the database") from e
    
    def _ensure_connection(self):
        try:
            if self.db is None or not self.db.is_active:
                self._connect()
        except Exception as e:
            raise RuntimeError("Failed to maintain database connection") from e
    
    def start_ingestion(self) -> int:
      
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
                
            db_ingestion = crud_ingestion.get_ingestion(self.db, ingestion_id=self.ingestion_id)
            if not db_ingestion:
                raise ValueError(f"No ingestion found with ID {self.ingestion_id}")
                
            
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
       
        return self.update_status(
            status=IngestionStatus.IN_PROGRESS,
            total_documents=total_documents,
            processed_documents=0
        )
        
    def update_progress(self, processed_documents: int) -> bool:
      
        return self.update_status(
            status=IngestionStatus.IN_PROGRESS,
            processed_documents=processed_documents
        )
        
    def mark_completed(self, processed_documents: int) -> bool:
      
        return self.update_status(
            status=IngestionStatus.COMPLETED,
            processed_documents=processed_documents
        )
        
    def mark_failed(self, error_message: str) -> bool:
      
        return self.update_status(
            status=IngestionStatus.FAILED,
            error_message=error_message
        )
        
    def __enter__(self):
      
        self.start_ingestion()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
      
        try:
            if exc_type is not None:
                error_msg = f"{exc_type.__name__}: {str(exc_val)}"
                if exc_tb:
                    error_msg += f"\n{''.join(traceback.format_tb(exc_tb))}"
                self.mark_failed(error_msg)
            
            if self.db:
                self.db.close()
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error during ingestion tracker cleanup: {str(e)}")
            
        return False
