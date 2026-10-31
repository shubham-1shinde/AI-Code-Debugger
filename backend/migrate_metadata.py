import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables before importing qdrant_service
load_dotenv()

from app.services.qdrant_service import save_repo_metadata


def migrate():
    metadata_path = Path("index_metadata.json")

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {metadata_path.resolve()}"
        )

    print("Loading existing local metadata...")

    with open(metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not metadata:
        print("No existing metadata found.")
        return

    repo = metadata.get("repo")
    branch = metadata.get("branch")
    commit = metadata.get("commit")

    if not repo or not branch or not commit:
        raise ValueError("Invalid metadata file.")

    print(f"Repository: {repo}")
    print(f"Branch: {branch}")
    print(f"Commit: {commit}")
    print(f"Files: {len(metadata.get('files', {}))}")

    print("\nMigrating metadata to Qdrant Cloud...")

    save_repo_metadata(metadata)

    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()