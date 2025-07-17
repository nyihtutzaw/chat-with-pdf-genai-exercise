from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from .config import settings

def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    cors_origins = []
    
    # Ensure we have a list of origins
    if isinstance(settings.BACKEND_CORS_ORIGINS, str):
        cors_origins = [origin.strip() for origin in settings.BACKEND_CORS_ORIGINS.split(",")]
    elif isinstance(settings.BACKEND_CORS_ORIGINS, list):
        cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    
    # If no origins are specified, default to allowing all
    if not cors_origins:
        cors_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
