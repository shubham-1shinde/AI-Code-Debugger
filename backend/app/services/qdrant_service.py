import time
import logging
import re
from pathlib import Path
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
)


QDRANT_PATH = str(
    Path(__file__).resolve().parents[2] / "qdrant_data"
)

EMBEDDING_SIZE = 768

# Load the embedding model only when it is first needed.
_embeddings = None

# Reuse vector stores for repositories already accessed.
_vector_stores = {}

# Initialize the local Qdrant client.
client = QdrantClient(path=QDRANT_PATH)


def get_embeddings():
    global _embeddings

    if _embeddings is None:
        print("Loading Hugging Face embedding model...")

        _embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-2",
            output_dimensionality=EMBEDDING_SIZE,
        )

        print("Embedding model loaded successfully.")

    return _embeddings


def get_collection_name(repo: str) -> str:
    """Generate a Qdrant collection name for a repository."""
    safe_repo = re.sub(r"[^a-zA-Z0-9_]", "_", repo)
    return f"repo_{safe_repo.lower()}"


def collection_exists(repo: str) -> bool:
    """Check whether a repository collection exists."""
    collection_name = get_collection_name(repo)

    collections = client.get_collections()

    return any(
        collection.name == collection_name
        for collection in collections.collections
    )


def create_collection(repo: str):
    """Create a collection if it does not already exist."""
    collection_name = get_collection_name(repo)

    if collection_exists(repo):
        return

    print(f"Creating Qdrant collection: {collection_name}")

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=EMBEDDING_SIZE,
            distance=Distance.COSINE,
        ),
    )

    print("Qdrant collection created successfully.")


def get_vector_store(repo: str):
    """Get or initialize the vector store for a repository."""
    if repo not in _vector_stores:
        collection_name = get_collection_name(repo)

        create_collection(repo)

        _vector_stores[repo] = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=get_embeddings(),
        )

    return _vector_stores[repo]


def create_store_from_documents(documents, repo: str):
    """Create a vector store and add documents."""
    if not documents:
        return

    collection_name = get_collection_name(repo)

    print(
        f"Creating Qdrant store with {len(documents)} chunks..."
    )

    create_collection(repo)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=get_embeddings(),
    )

    vector_store.add_documents(documents=documents)

    _vector_stores[repo] = vector_store

    print("Qdrant vector store created successfully.")


logger = logging.getLogger(__name__)

def add_documents(documents, repo: str):
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
                    raise

                # Back off: 30, 60, then 120 seconds.
                delay = 30 * (2 ** attempt)
                logger.warning(
                    "Gemini rate limit reached. "
                    "Retrying batch in %s seconds.",
                    delay,
                )
                time.sleep(delay)

        # Small pause between successful batches.
        if start + batch_size < len(documents):
            time.sleep(2)

    logger.info("Qdrant update completed for %s", repo)

def delete_file_vectors(file_path: str, repo: str):
    """Delete all vectors associated with a specific file."""
    if not collection_exists(repo):
        return

    collection_name = get_collection_name(repo)

    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="metadata.path",
                    match=MatchValue(value=file_path),
                )
            ]
        ),
    )

    print(
        f"Deleted vectors for {file_path} "
        f"from {collection_name}"
    )


def get_documents_by_file(
    file_path: str,
    repo: str,
    limit: int = 100,
):
    """Retrieve stored chunks for an exact file path."""
    if not file_path or not collection_exists(repo):
        return []

    collection_name = get_collection_name(repo)

    print(f"\nExact file retrieval: {file_path}")

    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.path",
                    match=MatchValue(value=file_path),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    documents = []

    for point in points:
        payload = point.payload or {}
        page_content = payload.get("page_content", "")
        metadata = payload.get("metadata", {})

        if page_content:
            documents.append(
                Document(
                    page_content=page_content,
                    metadata=metadata,
                )
            )

    print(f"Exact file chunks found: {len(documents)}")

    return documents


def get_retriever(repo: str, k: int = 8):
    """Get a semantic retriever for a repository."""
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

    retriever = get_retriever(repo, k)

    return retriever.invoke(query)


def close_qdrant():
    """Close the Qdrant client."""
    global _embeddings

    try:
        client.close()
    except Exception:
        pass

    _vector_stores.clear()
    _embeddings = None
