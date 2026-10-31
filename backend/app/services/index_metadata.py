from app.services.qdrant_service import (
    load_repo_metadata,
    save_repo_metadata,
)


def load_metadata(repo: str, branch: str):
    return load_repo_metadata(repo, branch)


def save_metadata(metadata: dict):
    return save_repo_metadata(metadata)