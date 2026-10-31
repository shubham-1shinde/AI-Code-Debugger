from pathlib import Path

from .github_service import (
    get_branch_commit,
    download_repository,
    extract_repository_files,
)

from .file_hasher import get_file_hash
from .code_chunker import chunk_file

from .qdrant_service import (
    add_documents,
    delete_file_vectors,
    load_repo_metadata,
    save_repo_metadata,
)


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

    # ========================================================
    # 1. GET LATEST GITHUB COMMIT
    # ========================================================

    current_commit = get_branch_commit(repo, branch)

    print(f"Current commit: {current_commit}")

    # ========================================================
    # 2. LOAD PREVIOUS METADATA FROM QDRANT CLOUD
    # ========================================================

    metadata = load_repo_metadata(repo, branch)

    # ========================================================
    # 3. CHECK WHETHER REPOSITORY IS ALREADY INDEXED
    # ========================================================

    if (
        metadata
        and metadata.get("indexed") is True
        and metadata.get("repo") == repo
        and metadata.get("branch") == branch
        and metadata.get("commit") == current_commit
    ):

        print("\nProject already indexed.")
        print("Commit SHA matches previous metadata.")
        print("No changes detected.")
        print("Skipping repository indexing.\n")

        return {
            "status": "unchanged",
            "message": "Project already indexed.",
            "repo": repo,
            "branch": branch,
            "commit": current_commit,
            "changed_files": 0,
            "deleted_files": 0,
            "chunks": 0,
        }

    # ========================================================
    # 4. GET PREVIOUS FILE METADATA
    # ========================================================

    old_files = (
        metadata.get("files", {})
        if metadata
        and metadata.get("repo") == repo
        and metadata.get("branch") == branch
        else {}
    )

    # ========================================================
    # 5. DOWNLOAD AND EXTRACT REPOSITORY
    # ========================================================

    print("\nDownloading repository...")

    zip_file = download_repository(
        repo,
        current_commit,
    )

    try:
        extracted_files = extract_repository_files(zip_file)
    finally:
        zip_file.close()

    current_files = {
        path: content
        for path, content in extracted_files.items()
        if is_supported_file(path)
    }

    del extracted_files

    print(f"Supported files found: {len(current_files)}")

    # ========================================================
    # 6. COMPARE FILE HASHES
    # ========================================================

    changed_files = []
    deleted_files = []
    current_hashes = {}

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

    # ========================================================
    # 7. DETECT DELETED FILES
    # ========================================================

    for path in old_files:

        if path not in current_files:
            deleted_files.append(path)

    print(f"\nChanged files: {len(changed_files)}")
    print(f"Deleted files: {len(deleted_files)}")

    # ========================================================
    # 8. BUILD NEW FILE METADATA
    # ========================================================

    new_file_metadata = {
        path: {
            "file_hash": file_hash,
            "commit": current_commit,
        }
        for path, file_hash in current_hashes.items()
    }

    new_metadata = {
        "indexed": True,
        "repo": repo,
        "branch": branch,
        "commit": current_commit,
        "files": new_file_metadata,
    }

    # ========================================================
    # 9. NO SOURCE FILE CHANGES
    # ========================================================

    if not changed_files and not deleted_files:

        print(
            "\nCommit changed, but no supported source files changed."
        )

        # Update the commit SHA in Qdrant metadata.
        save_repo_metadata(new_metadata)

        return {
            "status": "unchanged_source",
            "repo": repo,
            "branch": branch,
            "commit": current_commit,
            "changed_files": 0,
            "deleted_files": 0,
            "chunks": 0,
        }

    # ========================================================
    # 10. DELETE OLD VECTORS FOR CHANGED/DELETED FILES
    # ========================================================

    files_to_delete = {
        path
        for path, _, _, _ in changed_files
    }

    files_to_delete.update(deleted_files)

    for path in files_to_delete:

        print(f"Removing old vectors: {path}")

        delete_file_vectors(
            file_path=path,
            repo=repo,
        )

    # ========================================================
    # 11. INDEX ONLY NEW AND MODIFIED FILES
    # ========================================================

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

            add_documents(
                documents=chunks,
                repo=repo,
            )

            total_chunks += len(chunks)

        del chunks

    # ========================================================
    # 12. SAVE METADATA ONLY AFTER SUCCESSFUL INDEXING
    # ========================================================

    save_repo_metadata(new_metadata)

    print("\nIndexing completed successfully.")

    print(f"Updated files: {len(changed_files)}")
    print(f"Deleted files: {len(deleted_files)}")
    print(f"New chunks: {total_chunks}")

    return {
        "status": "updated",
        "repo": repo,
        "branch": branch,
        "commit": current_commit,
        "changed_files": len(changed_files),
        "deleted_files": len(deleted_files),
        "chunks": total_chunks,
    }