
import traceback

from fastapi import APIRouter, HTTPException

from app.models.debug_models import DebugRequest

router = APIRouter()


@router.post("/debug")
def debug(request: DebugRequest):
    try:
        # Import services only when a debug request arrives.
        from app.services.indexing import index_project
        from app.services.chain import get_main_chain

        print("New Debug Request")
        print("\nRepository:", request.repo)
        print("\nBranch:", request.branch)
        print("\nActive File:", request.activeFile)
        print("\nActive Code:", request.activeCode)
        print("\nError:", request.errorMessage)
        print("\nTerminal Logs:", request.terminalLogs)
        print("\nDiagnostics:", request.diagnostics)

        # Index the repository or reuse the existing index.
        index_result = index_project(
            repo=request.repo,
            branch=request.branch,
        )

        debug_input = {
            "errorMessage": request.errorMessage,
            "terminalLogs": request.terminalLogs,
            "workspacePath": request.workspacePath,
            "activeFile": request.activeFile,
            "activeCode": request.activeCode,
            "diagnostics": [
                diagnostic.model_dump()
                for diagnostic in request.diagnostics
            ],
        }

        # Run the existing debugging chain.
        chain_result = get_main_chain().invoke(debug_input)

        # Support Pydantic model results and dictionary results.
        if hasattr(chain_result, "model_dump"):
            answer = chain_result.model_dump()
        else:
            answer = chain_result

        return {
            "success": True,
            "index": index_result,
            "answer": answer,
        }

    except Exception as e:
        print(f"Debug request failed: {e}")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e
