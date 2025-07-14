import logging
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from datetime import datetime
from pathlib import Path
from app.config import settings
from app.routers import jobs
from app.models import HealthResponse, ErrorResponse
from app.workers import health_check, get_job_stats
from app.services.storage import storage_manager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = structlog.get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Automated Sermon Content Workflow - Speech-to-Text Service",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for local storage
if settings.storage.type == "local":
    static_path = Path(settings.storage.local_path)
    if static_path.exists():
        app.mount("/files", StaticFiles(directory=str(static_path)), name="files")

# Include routers
app.include_router(jobs.router, prefix="/api/v1")


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with service information"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "docs_url": "/docs" if settings.debug else None,
        "api_endpoints": {
            "transcribe": "/api/v1/jobs/transcribe",
            "upload": "/api/v1/jobs/transcribe/upload",
            "job_status": "/api/v1/jobs/{job_id}",
            "list_jobs": "/api/v1/jobs/",
            "health": "/health",
            "stats": "/stats"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    try:
        # Check worker health
        worker_health = health_check()
        
        # Check storage health
        storage_health = storage_manager.health_check()
        
        # Determine overall health
        overall_status = "healthy"
        if worker_health.get("status") != "healthy" or storage_health.get("status") != "healthy":
            overall_status = "unhealthy"
        
        return HealthResponse(
            status=overall_status,
            version=settings.app_version,
            timestamp=datetime.utcnow(),
            dependencies={
                "worker": worker_health.get("status", "unknown"),
                "storage": storage_health.get("status", "unknown"),
                "stt": worker_health.get("services", {}).get("stt", {}).get("status", "unknown")
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            version=settings.app_version,
            timestamp=datetime.utcnow(),
            dependencies={"error": str(e)}
        )


@app.get("/stats")
async def stats():
    """Get service statistics"""
    try:
        # Get job statistics
        job_stats = get_job_stats()
        
        # Get storage statistics
        storage_stats = storage_manager.get_storage_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "jobs": job_stats,
            "storage": storage_stats,
            "configuration": {
                "storage_type": settings.storage.type,
                "stt_language": settings.stt.language_code,
                "stt_model": settings.stt.model,
                "cost_limit_usd": settings.stt.cost_limit_usd
            }
        }
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/config")
async def config():
    """Get service configuration (debug only)"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "storage": {
            "type": settings.storage.type,
            "local_path": settings.storage.local_path,
            "max_file_size_mb": settings.storage.max_file_size_mb,
            "max_processing_time_seconds": settings.storage.max_processing_time_seconds
        },
        "stt": {
            "language_code": settings.stt.language_code,
            "model": settings.stt.model,
            "cost_limit_usd": settings.stt.cost_limit_usd
        },
        "subtitle": {
            "max_line_length": settings.subtitle.max_line_length,
            "max_lines": settings.subtitle.max_lines
        }
    }


# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="Not Found",
            message="The requested resource was not found"
        ).dict()
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred"
        ).dict()
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Storage type: {settings.storage.type}")
    logger.info(f"STT language: {settings.stt.language_code}")
    
    # Create necessary directories
    for path in [settings.storage.local_path, "./data/raw", "./data/processed"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    
    logger.info("Application startup completed")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info(f"Shutting down {settings.app_name}")
    # Add cleanup tasks here if needed
    logger.info("Application shutdown completed")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    ) 