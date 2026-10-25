import os
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from .prompts import prompt
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from .qdrant_service import get_documents_by_file, get_semantic_documents
from app.models.debug_models import DebugResult


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

    exact_documents = []

    if active_file:
        exact_documents = (get_documents_by_file(active_file, repo))

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
    semantic_documents = (
        get_semantic_documents(
            semantic_query,
            repo,
            k=8
        )
    )


    combined_documents = []
    seen = set()

    for doc in exact_documents:

        key = (
            doc.metadata.get("path", ""),
            doc.page_content
        )

        if key not in seen:
            seen.add(key)
            combined_documents.append(doc)

    for doc in semantic_documents:

        key = (
            doc.metadata.get("path", ""),
            doc.page_content
        )

        if key not in seen:
            seen.add(key)
            combined_documents.append(doc)

    print("\nRETRIEVAL")
    print(f"Active file: {active_file}")
    print(f"Exact chunks: {len(exact_documents)}")
    print(f"Semantic chunks: {len(semantic_documents)}")
    print(f"Final chunks: {len(combined_documents)}")

    return {
        "repository_context":
            format_docs(combined_documents),
        "errorMessage":
            error_message,
        "activeFile":
            active_file,
        "activeCode":
            active_code,
        "terminalLogs":
            terminal_logs,
        "diagnostics":
            diagnostics,
        "repo":
            repo,
    }

@lru_cache(maxsize=1)
def get_main_chain():

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        temperature=0,
        api_key=os.getenv(
            "GOOGLE_API_KEY"
        )
    )

    structured_llm = llm.with_structured_output(DebugResult)
    retrieval_chain = RunnableLambda(retrieve_context)

    return (retrieval_chain | prompt | structured_llm)