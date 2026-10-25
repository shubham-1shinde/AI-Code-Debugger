import logging
import traceback
import json
import time

from fastapi import APIRouter, HTTPException, Request
from app.models.debug_models import DebugRequest

router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)


@router.post("/debug")
def debug(request: DebugRequest, http_request: Request):
    start_time = time.time()

    try:
        # Import services only when a debug request arrives.
        from app.services.indexing import index_project
        from app.services.chain import get_main_chain

        logger.info("=" * 70)
        logger.info("NEW DEBUG REQUEST RECEIVED")
        logger.info("=" * 70)

        # Log request metadata
        logger.info("HTTP Method: %s", http_request.method)
        logger.info("Request URL: %s", http_request.url)
        logger.info("Client Address: %s", http_request.client.host if http_request.client else "Unknown")
        logger.info("Content-Type: %s", http_request.headers.get("content-type"))
        logger.info("Content-Length: %s", http_request.headers.get("content-length"))

        # Log the parsed request data
        logger.info("FRONTEND DATA RECEIVED:")
        logger.info("Repository: %s", request.repo)
        logger.info("Branch: %s", request.branch)
        logger.info("Active File: %s", request.activeFile)
        logger.info("Workspace Path: %s", request.workspacePath)
        logger.info("Error Message: %s", request.errorMessage)
        logger.info("Terminal Logs: %s", request.terminalLogs)
        logger.info("Diagnostics: %s", request.diagnostics)

        # Check whether important fields are populated
        logger.info("FIELD VALIDATION:")
        logger.info("repo present: %s", bool(request.repo))
        logger.info("branch present: %s", bool(request.branch))
        logger.info("activeFile present: %s", bool(request.activeFile))
        logger.info("activeCode present: %s", bool(request.activeCode))
        logger.info("errorMessage present: %s", bool(request.errorMessage))
        logger.info("terminalLogs present: %s", bool(request.terminalLogs))
        logger.info("diagnostics count: %d", len(request.diagnostics or []))
        logger.info("activeCode length: %d", len(request.activeCode or ""))
        logger.info("terminalLogs length: %d", len(request.terminalLogs or ""))

        # Index the repository
        logger.info("Starting repository indexing...")
        index_result = index_project(
            repo=request.repo,
            branch=request.branch,
        )
        logger.info("Repository indexing finished: %s", index_result)

        # Prepare input for the debugging chain
        debug_input = {
            "errorMessage": request.errorMessage,
            "terminalLogs": request.terminalLogs,
            "workspacePath": request.workspacePath,
            "activeFile": request.activeFile,
            "activeCode": request.activeCode,
            "diagnostics": [
                diagnostic.model_dump()
                if hasattr(diagnostic, "model_dump")
                else diagnostic
                for diagnostic in (request.diagnostics or [])
            ],
        }

        logger.info("Debug chain input prepared.")
        logger.info(
            "Debug input summary: %s",
            json.dumps(
                {
                    "errorMessage_length": len(request.errorMessage or ""),
                    "terminalLogs_length": len(request.terminalLogs or ""),
                    "workspacePath": request.workspacePath,
                    "activeFile": request.activeFile,
                    "activeCode_length": len(request.activeCode or ""),
                    "diagnostics_count": len(debug_input["diagnostics"]),
                },
                default=str,
            ),
        )

        # Run the debugging chain
        logger.info("Invoking debugging chain...")
        chain_result = get_main_chain().invoke(debug_input)
        logger.info("Debugging chain completed successfully.")

        # Support Pydantic model results and dictionary results
        if hasattr(chain_result, "model_dump"):
            answer = chain_result.model_dump()
        else:
            answer = chain_result

        elapsed = round(time.time() - start_time, 2)
        logger.info("Total request processing time: %s seconds", elapsed)
        logger.info("DEBUG REQUEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

        return {
            "success": True,
            "index": index_result,
            "answer": answer,
        }

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)

        logger.error("DEBUG REQUEST FAILED after %s seconds: %s", elapsed, str(e))
        logger.error("Exception type: %s", type(e).__name__)
        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.info("=" * 70)

        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
