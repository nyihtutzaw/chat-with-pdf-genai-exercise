from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import configurations
from app.config import settings, init_db
from app.api.endpoints import ingestion as ingestion_endpoints
from app.api.endpoints import chat as chat_endpoints

# Initialize database
init_db()

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for intelligent question-answering over academic papers with PDF ingestion tracking",
    version=settings.VERSION,
    debug=settings.DEBUG,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(
    ingestion_endpoints.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["ingestions"],
)

# Include chat router
app.include_router(
    chat_endpoints.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["chat"],
)

# Health check endpoint
@app.get(f"{settings.API_V1_STR}/health", summary="Health Check", tags=["Monitoring"])
async def health_check():
    """
    Check the health status of the API.
    
    Returns:
        dict: Status information including version and debug mode.
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "debug": settings.DEBUG
    }

# Root endpoint
@app.get(
    "/",
    include_in_schema=False,
    tags=["Root"]
)
async def root():
    """
    Root endpoint that provides basic API information.
    
    Returns:
        dict: Welcome message and API information.
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "redoc": f"{settings.API_V1_STR}/redoc"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level="debug" if settings.DEBUG else "info"
    )
