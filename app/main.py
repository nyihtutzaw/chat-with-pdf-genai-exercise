from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Import configurations
from app.config import settings, setup_cors as cors

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for intelligent question-answering over academic papers",
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

# Models
class QuestionRequest(BaseModel):
    """Request model for asking questions."""
    question: str
    session_id: Optional[str] = None

class AnswerResponse(BaseModel):
    """Response model for answers."""
    answer: str
    sources: List[str] = []
    session_id: str

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

# Example endpoint for asking questions
@app.post(
    f"{settings.API_V1_STR}/ask",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question",
    tags=["Chat"]
)
async def ask_question(question: QuestionRequest):
    """
    Ask a question and get an answer based on the PDF content.
    
    Args:
        question (QuestionRequest): The question and optional session ID.
        
    Returns:
        AnswerResponse: The answer to the question with sources and session ID.
    """
    try:
        # This is a placeholder implementation
        # Will be replaced with actual agent logic
        return AnswerResponse(
            answer=f"Received your question: {question.question}",
            sources=[],
            session_id=question.session_id or "demo-session-id"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

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
