from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.models.ingestion import Ingestion, IngestionStatus
from app.schemas.ingestion import IngestionCreate, IngestionUpdate

def get_ingestion(db: Session, ingestion_id: int) -> Optional[Ingestion]:
   
    return db.query(Ingestion).filter(Ingestion.id == ingestion_id).first()

def get_ingestion_by_filepath(db: Session, file_path: str) -> Optional[Ingestion]:
   
    return db.query(Ingestion).filter(Ingestion.file_path == file_path).order_by(Ingestion.created_at.desc()).first()

def get_ingestions(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    status: Optional[IngestionStatus] = None
) -> List[Ingestion]:
   
    query = db.query(Ingestion)
    if status is not None:
        query = query.filter(Ingestion.status == status)
    return query.offset(skip).limit(limit).all()

def create_ingestion(db: Session, ingestion: IngestionCreate) -> Ingestion:
   
    db_ingestion = Ingestion(**ingestion.dict())
    db.add(db_ingestion)
    db.commit()
    db.refresh(db_ingestion)
    return db_ingestion

def update_ingestion(
    db: Session, 
    db_ingestion: Ingestion, 
    ingestion_update: IngestionUpdate
) -> Ingestion:
   
    update_data = ingestion_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_ingestion, field, value)
    db_ingestion.updated_at = datetime.utcnow()
    db.add(db_ingestion)
    db.commit()
    db.refresh(db_ingestion)
    return db_ingestion

def update_ingestion_status(
    db: Session,
    ingestion_id: int,
    status: IngestionStatus,
    error_message: Optional[str] = None,
    total_documents: Optional[int] = None,
    processed_documents: Optional[int] = None,
) -> Optional[Ingestion]:
   
    db_ingestion = get_ingestion(db, ingestion_id)
    if not db_ingestion:
        return None
        
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    if error_message is not None:
        update_data["error_message"] = error_message
    if total_documents is not None:
        update_data["total_documents"] = total_documents
    if processed_documents is not None:
        update_data["processed_documents"] = processed_documents
    
    for field, value in update_data.items():
        setattr(db_ingestion, field, value)
    
    db.add(db_ingestion)
    db.commit()
    db.refresh(db_ingestion)
    return db_ingestion

def delete_ingestion(db: Session, ingestion_id: int) -> bool:
   
    db_ingestion = get_ingestion(db, ingestion_id)
    if not db_ingestion:
        return False
    db.delete(db_ingestion)
    db.commit()
    return True
