from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Chat with PDF API"
    VERSION: str = "0.1.0"
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000"
    
    DEBUG: bool = True
    OPENAI_API_KEY: str = "" 
    
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "documents"
    
    MYSQL_HOST: str = "mysql" 
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "chat_user"
    MYSQL_PASSWORD: str = "chat_password"
    MYSQL_DATABASE: str = "chat_with_pdf"
    MYSQL_ROOT_PASSWORD: str = "rootpassword"  
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
        env_prefix=""  # No prefix for environment variables
    )
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Construct the database URI from environment variables."""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
    
 
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    PDF_DIR: Path = DATA_DIR / "pdfs"
    LOG_DIR: Path = BASE_DIR / "logs"
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(LOG_DIR / "ingestion.log")
    
   

settings = Settings()

for directory in [settings.DATA_DIR, settings.PDF_DIR, settings.LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

def init_db():
    import time
    from sqlalchemy import text, create_engine, inspect
    from sqlalchemy.exc import OperationalError, ProgrammingError
    from app.models.ingestion import Base
    
    root_engine = create_engine(
        f"mysql+pymysql://root:{settings.MYSQL_ROOT_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
    )
    
    max_retries = 5
    retry_delay = 5 
    
    for attempt in range(max_retries):
        try:
            with root_engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                conn.execute(text(f"CREATE USER IF NOT EXISTS '{settings.MYSQL_USER}'@'%' IDENTIFIED BY '{settings.MYSQL_PASSWORD}'"))
                conn.execute(text(f"GRANT ALL PRIVILEGES ON `{settings.MYSQL_DATABASE}`.* TO '{settings.MYSQL_USER}'@'%'"))
                conn.execute(text("FLUSH PRIVILEGES"))
                conn.commit()
                break
        except (OperationalError, ProgrammingError) as e:
            if attempt == max_retries - 1:
                print(f"Failed to initialize database: {e}")
                raise
            print(f"Database not ready, retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
    
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    
    for attempt in range(max_retries):
        try:
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            if not existing_tables:
                print("Creating database tables...")
                Base.metadata.create_all(bind=engine)
                print("Database tables created successfully.")
            else:
                print("Database tables already exist.")
            break
        except (OperationalError, ProgrammingError) as e:
            if attempt == max_retries - 1:
                print(f"Failed to create tables: {e}")
                raise
            print(f"Database not ready for table creation, retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

if __name__ != "__main__":
    init_db()
