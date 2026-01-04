"""
Text-to-Linux-OS Builder - Main FastAPI Application
"""
# Load environment variables BEFORE importing other modules
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging
import os

from backend.database.db import init_db
from backend.api import chatbot, builder, projects

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Text-to-Linux-OS Builder",
    description="AI-powered custom Linux ISO generator",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(chatbot.router)
app.include_router(builder.router)
app.include_router(projects.router)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Text-to-Linux-OS Builder")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Check for required environment variables
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set - chatbot will not work")

    # Create required directories
    os.makedirs("./builds", exist_ok=True)
    os.makedirs("./cache/packages", exist_ok=True)
    os.makedirs("./data", exist_ok=True)

    logger.info("Application startup complete")


@app.get("/")
async def root():
    """Serve the main application page"""
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "text-to-linux-os-builder",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
