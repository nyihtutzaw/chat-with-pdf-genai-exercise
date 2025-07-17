from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class IngestionStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class IngestionBase(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file being processed")
    status: IngestionStatus = Field(default=IngestionStatus.STARTED, description="Current status of ingestion")
    error_message: Optional[str] = Field(None, description="Error message if ingestion failed")
    total_documents: int = Field(default=0, description="Total number of documents to process")
    processed_documents: int = Field(default=0, description="Number of documents processed so far")

class IngestionCreate(IngestionBase):
    pass

class IngestionUpdate(BaseModel):
    status: Optional[IngestionStatus] = None
    error_message: Optional[str] = None
    total_documents: Optional[int] = None
    processed_documents: Optional[int] = None

class IngestionInDBBase(IngestionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Ingestion(IngestionInDBBase):
    pass

class IngestionInDB(IngestionInDBBase):
    pass
