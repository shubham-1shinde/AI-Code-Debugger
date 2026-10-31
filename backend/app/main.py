import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables before importing application modules
load_dotenv()

# Import API router and Qdrant connection functions
from app.api.debug import router
from app.services.qdrant_service import (
    test_qdrant_connection,
    close_qdrant,
)


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)

logger = logging.getLogger(__name__)


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting AI Code Debugger...")

    # Test Qdrant Cloud connection
    try:
        connected = test_qdrant_connection()

        if connected:
            logger.info("Qdrant Cloud connection successful")
        else:
            logger.error("Qdrant Cloud connection failed")

    except Exception:
        logger.exception("Error connecting to Qdrant Cloud")

    yield

    # Application shutdown
    logger.info("Shutting down AI Code Debugger...")

    close_qdrant()

    logger.info("AI Code Debugger shutdown completed")


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Code Debugger",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(
    router,
    prefix="/api",
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "AI Code Debugger",
    }