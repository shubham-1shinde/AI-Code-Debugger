import logging
import re
import time
from pathlib import Path, PurePosixPath

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    PointIdsList,
)

logger = logging.getLogger(__name__)

QDRANT_PATH = str(
    Path(__file__).resolve().parents[2] / "qdrant_data"
)

EMBEDDING_SIZE = 768

_embeddings = None
_vector_stores = {}

client = QdrantClient(path=QDRANT_PATH)


def get_embeddings():
    """Initialize the Gemini embedding model lazily."""
    global _embeddings

    if _embeddings is None:
        logger.info("Loading Gemini embedding model")

        _embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-2",
            output_dimensionality=EMBEDDING_SIZE,
        )

        logger.info("Gemini embedding model loaded")

    return _embeddings


def normalize_file_path(path: str) -> str:
    """Normalize Windows and Linux file paths."""
    normalized = str(path or "").replace("\\", "/").strip()
    normalized = str(PurePosixPath(normalized))

    while normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized.strip("/")


def get_collection_name(repo: str) -> str:
    """Generate a stable collection name for a repository."""
    safe_repo = re.sub(r"[^a-zA-Z0-9_]", "_", repo)
    return f"repo_{safe_repo.lower()}"


def collection_exists(repo: str) -> bool:
    """Check whether a repository collection exists."""
    collection_name = get_collection_name(repo)

    return any(
        collection.name == collection_name
        for collection in client.get_collections().collections
    )


def create_collection(repo: str):
    """Create a repository collection if it does not exist."""
    collection_name = get_collection_name(repo)

    if collection_exists(repo):
        return

    logger.info("Creating Qdrant collection: %s", collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=EMBEDDING_SIZE,
            distance=Distance.COSINE,
        ),
    )

    logger.info("Qdrant collection created: %s", collection_name)


def get_vector_store(repo: str):
    """Get a vector store, creating its collection when necessary."""
    collection_name = get_collection_name(repo)

    if repo not in _vector_stores:
        # Important: indexing calls this function before inserting
        # the first batch, so the collection must be created here.
        create_collection(repo)

        _vector_stores[repo] = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=get_embeddings(),
        )

    return _vector_stores[repo]


def create_store_from_documents(documents, repo: str):
    """Create a vector store and insert documents."""
    if not documents:
        return

    vector_store = get_vector_store(repo)
    vector_store.add_documents(documents=documents)

    logger.info(
        "Stored %s documents in %s",
        len(documents),
        get_collection_name(repo),
    )


def add_documents(documents, repo: str):
    """Insert documents in batches with rate-limit retries."""
    if not documents:
        return

    vector_store = get_vector_store(repo)

    batch_size = 5
    max_attempts = 4

    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]

        for attempt in range(max_attempts):
            try:
                vector_store.add_documents(documents=batch)

                logger.info(
                    "Embedded batch %s for %s",
                    start // batch_size + 1,
                    repo,
                )
                break

            except Exception as exc:
                message = str(exc)
                is_rate_limit = (
                    "429" in message
                    or "RESOURCE_EXHAUSTED" in message
                )

                if not is_rate_limit or attempt == max_attempts - 1:
                    logger.exception(
                        "Failed to add document batch for %s",
                        repo,
                    )
                    raise

                delay = 30 * (2 ** attempt)

                logger.warning(
                    "Embedding rate limit for %s. "
                    "Retrying in %s seconds.",
                    repo,
                    delay,
                )

                time.sleep(delay)

        if start + batch_size < len(documents):
            time.sleep(2)

    logger.info("Qdrant update completed for %s", repo)


def _get_stored_path(payload: dict) -> str:
    """Extract a file path from supported payload layouts."""
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
    """Extract document metadata from a Qdrant payload."""
    metadata = payload.get("metadata") or {}

    if not isinstance(metadata, dict):
        metadata = {}

    metadata = dict(metadata)
    stored_path = _get_stored_path(payload)

    if stored_path and not metadata.get("path"):
        metadata["path"] = stored_path

    return metadata


def delete_file_vectors(file_path: str, repo: str):
    """Delete vectors associated with a file."""
    if not collection_exists(repo):
        return

    collection_name = get_collection_name(repo)
    target_path = normalize_file_path(file_path)
    ids_to_delete = []
    offset = None

    # Scan payloads to handle path separators and metadata layouts
    # consistently. This also avoids relying on one exact filter key.
    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}
            stored_path = normalize_file_path(
                _get_stored_path(payload)
            )

            if (
                stored_path == target_path
                or stored_path.endswith("/" + target_path)
            ):
                ids_to_delete.append(point.id)

        if next_offset is None:
            break

        offset = next_offset

    if ids_to_delete:
        client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=ids_to_delete),
            wait=True,
        )

    _vector_stores.pop(repo, None)

    logger.info(
        "Deleted %s vectors for %s from %s",
        len(ids_to_delete),
        file_path,
        collection_name,
    )


def get_documents_by_file(
    file_path: str,
    repo: str,
    limit: int = 100,
):
    """Retrieve chunks matching a normalized file path."""
    if not file_path:
        return []

    if not collection_exists(repo):
        logger.warning(
            "Exact retrieval skipped: collection missing for %s",
            repo,
        )
        return []

    collection_name = get_collection_name(repo)
    requested_path = normalize_file_path(file_path)

    logger.info(
        "Exact retrieval: collection=%s, file=%s",
        collection_name,
        requested_path,
    )

    documents = []
    offset = None

    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}

            stored_path = normalize_file_path(
                _get_stored_path(payload)
            )

            matches = (
                stored_path == requested_path
                or stored_path.endswith("/" + requested_path)
            )

            if not matches:
                continue

            content = payload.get("page_content", "")

            if not content:
                logger.warning(
                    "Matching path has no page_content. "
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
        "Exact file retrieval found %s chunks for %s",
        len(documents),
        requested_path,
    )

    return documents


def get_retriever(repo: str, k: int = 8):
    """Get a semantic retriever for an indexed repository."""
    vector_store = get_vector_store(repo)

    return vector_store.as_retriever(
        search_kwargs={"k": k}
    )


def get_semantic_documents(
    query: str,
    repo: str,
    k: int = 8,
):
    """Retrieve semantically relevant repository chunks."""
    if not query:
        return []

    if not collection_exists(repo):
        logger.warning(
            "Semantic retrieval skipped: collection missing for %s",
            repo,
        )
        return []

    collection_name = get_collection_name(repo)

    try:
        info = client.get_collection(collection_name)

        logger.info(
            "Semantic search collection=%s, points_count=%s",
            collection_name,
            info.points_count,
        )

        if not info.points_count:
            logger.warning(
                "Collection %s is empty",
                collection_name,
            )
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


def close_qdrant():
    """Close Qdrant and clear cached objects."""
    global _embeddings

    try:
        client.close()
    except Exception:
        logger.exception("Error closing Qdrant client")

    _vector_stores.clear()
    _embeddings = None
