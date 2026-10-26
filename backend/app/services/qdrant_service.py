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

#model="gemini-embedding-2",
def get_embeddings():
    global _embeddings

    if _embeddings is None:
        logger.info("Initializing Gemini embedding model")
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            output_dimensionality=EMBEDDING_SIZE,
        )

    return _embeddings


def normalize_file_path(path: str) -> str:
    path = str(path or "").replace("\\", "/").strip()
    path = str(PurePosixPath(path))

    while path.startswith("./"):
        path = path[2:]

    return path.strip("/")


def get_collection_name(repo: str) -> str:
    safe_repo = re.sub(r"[^a-zA-Z0-9_]", "_", repo)
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

    logger.info("Creating Qdrant collection: %s", name)

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=EMBEDDING_SIZE,
            distance=Distance.COSINE,
        ),
    )


def get_vector_store(repo: str):
    """Create the collection before constructing the vector store."""
    if repo not in _vector_stores:
        create_collection(repo)

        _vector_stores[repo] = QdrantVectorStore(
            client=client,
            collection_name=get_collection_name(repo),
            embedding=get_embeddings(),
        )

    return _vector_stores[repo]


def create_store_from_documents(documents, repo: str):
    if not documents:
        return

    get_vector_store(repo).add_documents(documents=documents)

    logger.info(
        "Stored %s documents in %s",
        len(documents),
        get_collection_name(repo),
    )


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
        )
    )


def add_documents(documents, repo: str):
    """Insert documents with retries for transient embedding failures."""
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
                vector_store.add_documents(documents=batch)

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
                    "Temporary Gemini API failure. "
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

    logger.info("Qdrant update completed for %s", repo)


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


def delete_file_vectors(file_path: str, repo: str):
    if not collection_exists(repo):
        return

    name = get_collection_name(repo)
    target = normalize_file_path(file_path)
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
            points_selector=PointIdsList(points=ids),
            wait=True,
        )

    _vector_stores.pop(repo, None)

    logger.info(
        "Deleted %s vectors for %s from %s",
        len(ids),
        file_path,
        name,
    )


def get_documents_by_file(
    file_path: str,
    repo: str,
    limit: int = 100,
):
    if not file_path or not collection_exists(repo):
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


def get_retriever(repo: str, k: int = 8):
    return get_vector_store(repo).as_retriever(
        search_kwargs={"k": k}
    )


def get_semantic_documents(
    query: str,
    repo: str,
    k: int = 8,
):
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


def close_qdrant():
    global _embeddings

    try:
        client.close()
    except Exception:
        logger.exception("Error closing Qdrant client")

    _vector_stores.clear()
    _embeddings = None
