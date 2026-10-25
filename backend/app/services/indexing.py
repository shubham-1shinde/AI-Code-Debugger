
from pathlib import Path

from .github_service import (
    get_branch_commit,
    download_repository,
    extract_repository_files,
)
from .file_hasher import get_file_hash
from .code_chunker import chunk_file
from .index_metadata import load_metadata, save_metadata
from .qdrant_service import add_documents, delete_file_vectors


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
}


def is_supported_file(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def index_project(repo: str, branch: str):
    print("\nStarting project indexing...\n")
    print(f"Repository: {repo}")
    print(f"Branch: {branch}")

    metadata = load_metadata()

    current_commit = get_branch_commit(repo, branch)
    print(f"Current commit: {current_commit}")

    # Skip indexing when this exact commit is already indexed.
    if (
        metadata.get("indexed")
        and metadata.get("repo") == repo
        and metadata.get("branch") == branch
        and metadata.get("commit") == current_commit
    ):
        print("\nProject already indexed.")
        print("No changes detected.")
        print("Skipping indexing.\n")

        return {
            "status": "unchanged",
            "message": "Project already indexed.",
            "commit": current_commit,
        }

    # Download and extract the repository.
    zip_file = download_repository(repo, current_commit)

    try:
        extracted_files = extract_repository_files(zip_file)
    finally:
        zip_file.close()

    current_files = {
        path: content
        for path, content in extracted_files.items()
        if is_supported_file(path)
    }

    # Release the reference to the unfiltered mapping.
    del extracted_files

    print(f"\nSupported files found: {len(current_files)}")

    old_files = metadata.get("files", {})
    changed_files = []
    deleted_files = []
    current_hashes = {}

    # Detect new and modified files.
    for path, content in current_files.items():
        file_hash = get_file_hash(content)
        current_hashes[path] = file_hash

        old_file = old_files.get(path)

        if old_file is None:
            changed_files.append(
                (path, content, file_hash, "added")
            )
        elif old_file.get("file_hash") != file_hash:
            changed_files.append(
                (path, content, file_hash, "modified")
            )

    # Detect deleted files.
    for path in old_files:
        if path not in current_files:
            deleted_files.append(path)

    print(f"Changed files: {len(changed_files)}")
    print(f"Deleted files: {len(deleted_files)}")

    # The commit changed, but no supported source files changed.
    if not changed_files and not deleted_files:
        new_file_metadata = {
            path: {
                "file_hash": file_hash,
                "commit": current_commit,
            }
            for path, file_hash in current_hashes.items()
        }

        metadata = {
            "indexed": True,
            "repo": repo,
            "branch": branch,
            "commit": current_commit,
            "files": new_file_metadata,
        }

        save_metadata(metadata)

        print(
            "\nCommit changed but no supported source files changed."
        )

        return {
            "status": "unchanged_source",
            "commit": current_commit,
        }

    # Delete old vectors for changed and deleted files.
    files_to_delete = {
        path
        for path, _, _, _ in changed_files
    }
    files_to_delete.update(deleted_files)

    for path in files_to_delete:
        print(f"Removing old vectors: {path}")
        delete_file_vectors(path, repo)

    # Process and upload chunks one file at a time.
    # This avoids retaining all generated chunks in memory.
    total_chunks = 0

    for path, content, file_hash, change_type in changed_files:
        print(f"\nProcessing {change_type}: {path}")

        chunks = chunk_file(
            file_path=path,
            content=content,
            file_hash=file_hash,
            commit=current_commit,
        )

        print(f"Created {len(chunks)} chunks")

        if chunks:
            print(f"Adding embeddings for {path}...")
            add_documents(chunks, repo)
            total_chunks += len(chunks)

        del chunks

    # Save accurate metadata for each file.
    new_file_metadata = {
        path: {
            "file_hash": file_hash,
            "commit": current_commit,
        }
        for path, file_hash in current_hashes.items()
    }

    metadata = {
        "indexed": True,
        "repo": repo,
        "branch": branch,
        "commit": current_commit,
        "files": new_file_metadata,
    }

    save_metadata(metadata)

    print("\nIndexing completed successfully.")

    return {
        "status": "updated",
        "commit": current_commit,
        "changed_files": len(changed_files),
        "deleted_files": len(deleted_files),
        "chunks": total_chunks,
    }
