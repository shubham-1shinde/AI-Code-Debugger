import logging
import os
import re
import time

from pathlib import PurePosixPath

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointIdsList,
)

logger = logging.getLogger(__name__)


# ============================================================
# QDRANT CLOUD CONFIGURATION
# ============================================================

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

EMBEDDING_SIZE = 768

if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError(
        "Missing QDRANT_URL or QDRANT_API_KEY environment variables"
    )

# Connect to Qdrant Cloud instead of local storage
client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    timeout=120,
)

logger.info("Qdrant Cloud client initialized")


# ============================================================
# GLOBAL VARIABLES
# ============================================================

_embeddings = None
_vector_stores = {}


# ============================================================
# GEMINI EMBEDDINGS
# ============================================================

def get_embeddings():
    global _embeddings

    if _embeddings is None:
        logger.info("Initializing Gemini embedding model")

        _embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            output_dimensionality=EMBEDDING_SIZE,
        )

    return _embeddings


# ============================================================
# FILE PATH NORMALIZATION
# ============================================================

def normalize_file_path(path: str) -> str:

    path = str(path or "").replace("\\", "/").strip()

    path = str(PurePosixPath(path))

    while path.startswith("./"):
        path = path[2:]

    return path.strip("/")


# ============================================================
# COLLECTION MANAGEMENT
# ============================================================

def get_collection_name(repo: str) -> str:

    safe_repo = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        repo
    )

    return f"repo_{safe_repo.lower()}"


def collection_exists(repo: str) -> bool:

    name = get_collection_name(repo)

    return any(
        item.name == name
        for item in client.get_collections().collections
    )


def create_collection(repo: str):

    name = get_collection_name(repo)

    if collection_exists(repo):
        return

    logger.info("Creating Qdrant Cloud collection: %s", name)

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=EMBEDDING_SIZE,
            distance=Distance.COSINE,
        ),
    )


# ============================================================
# VECTOR STORE
# ============================================================

def get_vector_store(repo: str):
    """
    Create or retrieve the LangChain vector store
    connected to Qdrant Cloud.
    """

    if repo not in _vector_stores:

        create_collection(repo)

        _vector_stores[repo] = QdrantVectorStore(
            client=client,
            collection_name=get_collection_name(repo),
            embedding=get_embeddings(),
        )

    return _vector_stores[repo]


# ============================================================
# CREATE STORE FROM DOCUMENTS
# ============================================================

def create_store_from_documents(documents, repo: str):

    if not documents:
        return

    vector_store = get_vector_store(repo)

    vector_store.add_documents(documents=documents)

    logger.info(
        "Stored %s documents in %s",
        len(documents),
        get_collection_name(repo),
    )


# ============================================================
# TRANSIENT ERROR DETECTION
# ============================================================

def _is_transient_error(exc: Exception) -> bool:

    message = str(exc).upper()

    return any(
        marker in message
        for marker in (
            "429",
            "503",
            "UNAVAILABLE",
            "RESOURCE_EXHAUSTED",
            "500",
            "502",
            "504",
            "INTERNAL",
            "DEADLINE_EXCEEDED",
            "TIMEOUT",
            "CONNECTION",
        )
    )


# ============================================================
# ADD DOCUMENTS WITH RETRIES
# ============================================================

def add_documents(documents, repo: str):
    """
    Insert documents in batches with retry handling
    for temporary Gemini API and connection failures.
    """

    if not documents:
        return

    vector_store = get_vector_store(repo)

    batch_size = 5
    max_attempts = 5

    for start in range(0, len(documents), batch_size):

        batch = documents[start:start + batch_size]

        batch_number = start // batch_size + 1

        for attempt in range(max_attempts):

            try:

                vector_store.add_documents(
                    documents=batch
                )

                logger.info(
                    "Embedded batch %s for %s",
                    batch_number,
                    repo,
                )

                break

            except Exception as exc:

                if (
                    not _is_transient_error(exc)
                    or attempt == max_attempts - 1
                ):

                    logger.exception(
                        "Embedding batch %s failed for %s",
                        batch_number,
                        repo,
                    )

                    raise

                delay = min(15 * (2 ** attempt), 120)

                logger.warning(
                    "Temporary Gemini/Qdrant failure. "
                    "Repository=%s, batch=%s, attempt=%s/%s, "
                    "retry_in=%ss, error=%s",
                    repo,
                    batch_number,
                    attempt + 1,
                    max_attempts,
                    delay,
                    str(exc)[:300],
                )

                time.sleep(delay)

        if start + batch_size < len(documents):
            time.sleep(3)

    logger.info("Qdrant Cloud update completed for %s", repo)


# ============================================================
# DOCUMENT METADATA HELPERS
# ============================================================

def _get_stored_path(payload: dict) -> str:

    metadata = payload.get("metadata") or {}

    if not isinstance(metadata, dict):
        metadata = {}

    return (
        metadata.get("path")
        or metadata.get("file_path")
        or payload.get("metadata.path")
        or payload.get("path")
        or payload.get("file_path")
        or ""
    )


def _get_document_metadata(payload: dict) -> dict:

    metadata = payload.get("metadata") or {}

    if not isinstance(metadata, dict):
        metadata = {}

    metadata = dict(metadata)

    path = _get_stored_path(payload)

    if path and not metadata.get("path"):
        metadata["path"] = path

    return metadata


# ============================================================
# DELETE FILE VECTORS
# ============================================================

def delete_file_vectors(file_path: str, repo: str):
    """
    Delete all vector chunks belonging to a specific file.
    """

    if not collection_exists(repo):
        return

    name = get_collection_name(repo)

    target = normalize_file_path(file_path)

    if not target:
        return

    ids = []

    offset = None

    while True:

        points, next_offset = client.scroll(
            collection_name=name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:

            payload = point.payload or {}

            stored = normalize_file_path(
                _get_stored_path(payload)
            )

            if stored and (
                stored == target
                or stored.endswith("/" + target)
            ):

                ids.append(point.id)

        if next_offset is None:
            break

        offset = next_offset

    if ids:

        client.delete(
            collection_name=name,
            points_selector=PointIdsList(
                points=ids
            ),
            wait=True,
        )

    _vector_stores.pop(repo, None)

    logger.info(
        "Deleted %s vectors for %s from %s",
        len(ids),
        file_path,
        name,
    )


# ============================================================
# GET DOCUMENTS BY FILE
# ============================================================

def get_documents_by_file(
    file_path: str,
    repo: str,
    limit: int = 100,
):
    """
    Retrieve all stored chunks belonging to a file.
    """

    if not file_path or limit <= 0 or not collection_exists(repo):
        return []

    name = get_collection_name(repo)

    requested = normalize_file_path(file_path)

    documents = []

    offset = None

    while True:

        points, next_offset = client.scroll(
            collection_name=name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:

            payload = point.payload or {}

            stored = normalize_file_path(
                _get_stored_path(payload)
            )

            if not stored or not (
                stored == requested
                or stored.endswith("/" + requested)
            ):
                continue

            content = payload.get("page_content", "")

            if not content:

                logger.warning(
                    "Matched file but page_content is missing. "
                    "Payload keys: %s",
                    list(payload.keys()),
                )

                continue

            documents.append(
                Document(
                    page_content=content,
                    metadata=_get_document_metadata(payload),
                )
            )

            if len(documents) >= limit:
                break

        if len(documents) >= limit or next_offset is None:
            break

        offset = next_offset

    logger.info(
        "Exact retrieval found %s chunks for %s",
        len(documents),
        requested,
    )

    return documents


# ============================================================
# RETRIEVER
# ============================================================

def get_retriever(repo: str, k: int = 8):

    return get_vector_store(repo).as_retriever(
        search_kwargs={
            "k": k
        }
    )


# ============================================================
# SEMANTIC SEARCH
# ============================================================

def get_semantic_documents(
    query: str,
    repo: str,
    k: int = 8,
):
    """
    Perform semantic search against Qdrant Cloud.
    """

    if not query or not collection_exists(repo):
        return []

    name = get_collection_name(repo)

    try:

        info = client.get_collection(name)

        logger.info(
            "Semantic search collection=%s, points_count=%s",
            name,
            info.points_count,
        )

        if not info.points_count:
            return []

        documents = get_retriever(repo, k).invoke(query)

        logger.info(
            "Semantic retrieval returned %s documents",
            len(documents),
        )

        return documents

    except Exception:

        logger.exception(
            "Semantic retrieval failed for repository %s",
            repo,
        )

        raise


# ============================================================
# CONNECTION TEST
# ============================================================

def test_qdrant_connection():

    try:

        collections = client.get_collections()

        logger.info("Qdrant Cloud connected successfully!")

        for collection in collections.collections:

            logger.info(
                "Available collection: %s",
                collection.name,
            )

        return True

    except Exception:

        logger.exception("Qdrant Cloud connection failed")

        return False


# ============================================================
# CLOSE CONNECTION
# ============================================================

def close_qdrant():
    global _embeddings

    try:

        client.close()

        logger.info("Qdrant Cloud connection closed")

    except Exception:

        logger.exception("Error closing Qdrant client")

    _vector_stores.clear()

    _embeddings = None


# ============================================================
# LOCAL CONNECTION TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    test_qdrant_connection()