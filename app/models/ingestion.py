from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from app.db.base import Base

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
