from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Chat with PDF API"
    VERSION: str = "0.1.0"
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    
    # CORS Configuration - can be a string or list of strings
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000"
    
    # Application Settings
    DEBUG: bool = True
    
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

# Create settings instance
settings = Settings()
