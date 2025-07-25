"""
Water Accounting Service
Section-level water delivery tracking and efficiency monitoring
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
from dotenv import load_dotenv

from .api import router
from .database import init_db, close_db
from .config import get_settings
from .middleware import add_metrics_middleware
from .utils.logging import setup_logging

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Starting Water Accounting Service...")
    
    # Initialize database connections
    await init_db()
    
    # Initialize any background tasks or connections
    logger.info("Water Accounting Service started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Water Accounting Service...")
    await close_db()
    logger.info("Water Accounting Service shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Water Accounting Service",
    description="Section-level water delivery tracking and efficiency monitoring for Munbon Irrigation System",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics middleware
add_metrics_middleware(app)

# Include routers
app.include_router(router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "water-accounting",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        reload=settings.DEBUG
    )