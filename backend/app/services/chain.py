import os
import logging
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from .prompts import prompt
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from .qdrant_service import get_documents_by_file, get_semantic_documents
from app.models.debug_models import DebugResult

logger = logging.getLogger(__name__)

def format_docs(documents):
    if not documents:
        return "NO_REPOSITORY_CONTEXT"

    formatted = []
    seen = set()

    for i, doc in enumerate(documents, 1):

        path = doc.metadata.get(
            "path",
            "UNKNOWN_FILE"
        )
        chunk_id = (
            path,
            doc.page_content
        )

        if chunk_id in seen:
            continue

        seen.add(chunk_id)
        formatted.append(
            f"""
--- RETRIEVED CHUNK {i} ---

FILE:
{path}
CODE:
{doc.page_content}
--- END CHUNK ---
"""
        )

    if not formatted:
        return "NO_REPOSITORY_CONTEXT"

    return "\n".join(formatted)


def retrieve_context(data):
    """
    Retrieval pipeline:
    1. Exact active-file retrieval
    2. Semantic retrieval using error + active code
    3. Merge and deduplicate
    """

    error_message = data.get("errorMessage", "")
    active_file = data.get("activeFile", "")
    active_code = data.get("activeCode", "")
    terminal_logs = data.get("terminalLogs", "")
    diagnostics = data.get("diagnostics", [])
    repo = data.get("repo", "")

    # Log incoming data
    logger.info("========== RETRIEVAL INPUT ==========")
    logger.info("Repository received by chain: %r", repo)
    logger.info("Active file: %r", active_file)
    logger.info("Active code length: %s", len(active_code))
    logger.info("Error message length: %s", len(error_message))
    logger.info("Terminal logs length: %s", len(terminal_logs))
    logger.info("Diagnostics count: %s", len(diagnostics))

    # 1. Exact retrieval
    exact_documents = []

    if active_file and repo:
        exact_documents = get_documents_by_file(active_file, repo)

    # 2. Build semantic query BEFORE logging its length
    semantic_query = f"""
ERROR:
{error_message}

ACTIVE FILE:
{active_file}

ACTIVE CODE:
{active_code}

TERMINAL LOGS:
{terminal_logs}

DIAGNOSTICS:
{diagnostics}
"""

    logger.info("Semantic query length: %s", len(semantic_query))

    # 3. Semantic retrieval
    semantic_documents = get_semantic_documents(
        semantic_query,
        repo,
        k=8,
    )

    # 4. Merge and deduplicate
    combined_documents = []
    seen = set()

    for doc in exact_documents + semantic_documents:
        key = (
            doc.metadata.get("path", ""),
            doc.page_content,
        )

        if key not in seen:
            seen.add(key)
            combined_documents.append(doc)

    logger.info("========== RETRIEVAL RESULTS ==========")
    logger.info("Exact chunks: %s", len(exact_documents))
    logger.info("Semantic chunks: %s", len(semantic_documents))
    logger.info("Final chunks: %s", len(combined_documents))
    logger.info("======================================")

    return {
        "repository_context": format_docs(combined_documents),
        "errorMessage": error_message,
        "activeFile": active_file,
        "activeCode": active_code,
        "terminalLogs": terminal_logs,
        "diagnostics": diagnostics,
        "repo": repo,
    }
    
#model="gemini-3.8-flash","gemini-2.5-flash"
@lru_cache(maxsize=1)
def get_main_chain():

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL"),
        temperature=0,
        api_key=os.getenv("GEMINI_API_KEY")
    )

    structured_llm = llm.with_structured_output(DebugResult)
    retrieval_chain = RunnableLambda(retrieve_context)

    return (retrieval_chain | prompt | structured_llm)