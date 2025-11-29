"""
OMedia - Media Organizer Application
FastAPI main entry point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import init_db, close_db
from .routers import share_import, manual_organize, jobs, recognize, rules, config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Media Organizer Application for normalizing media files",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    share_import.router,
    prefix=f"{settings.api_prefix}/share",
    tags=["Share Import"]
)

app.include_router(
    manual_organize.router,
    prefix=f"{settings.api_prefix}/organize",
    tags=["Manual Organize"]
)

app.include_router(
    jobs.router,
    prefix=f"{settings.api_prefix}/jobs",
    tags=["Jobs"]
)

app.include_router(
    recognize.router,
    prefix=f"{settings.api_prefix}/recognize",
    tags=["Recognition"]
)

app.include_router(
    rules.router,
    prefix=f"{settings.api_prefix}/rules",
    tags=["Transfer Rules"]
)

app.include_router(
    config.router,
    prefix=f"{settings.api_prefix}/config",
    tags=["Configuration"]
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

