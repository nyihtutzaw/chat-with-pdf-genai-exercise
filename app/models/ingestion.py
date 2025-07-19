from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from app.db.base import Base

from pydantic import BaseModel, Field
from typing import Optional



class IngestionStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
class Ingestion(Base):
    __tablename__ = "ingestions"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(500), nullable=False)
    status = Column(SQLEnum(IngestionStatus), default=IngestionStatus.STARTED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    error_message = Column(String(500), nullable=True)
    total_documents = Column(Integer, default=0)
    processed_documents = Column(Integer, default=0)





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
