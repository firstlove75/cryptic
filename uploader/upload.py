"""
Upload Markdown files to an OpenAI Vector Store.
Only uploads articles that are new or have changed (delta upload).
"""

import os
import json
from pathlib import Path
from openai import OpenAI

ARTICLES_DIR = Path("articles")

# Persists slug → openai_file_id mapping so old files can be deleted on update
UPLOAD_STATE_FILE = Path(".upload_state.json")

VECTOR_STORE_NAME = "optisigns-kb"


# -----------------------------------------------------------------
# Client
# -----------------------------------------------------------------

def get_client() -> OpenAI:
    """Build an OpenAI client from the environment. Fails fast if key is missing."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in environment variables")
    return OpenAI(api_key=api_key)


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def load_upload_state() -> dict:
    """Return the previous upload state, or {} on first run."""
    if UPLOAD_STATE_FILE.exists():
        return json.loads(UPLOAD_STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_upload_state(state: dict):
    """Persist the upload state to disk."""
    UPLOAD_STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def get_or_create_vector_store(client: OpenAI) -> str:
    """
    Look up the vector store by name. Create it if it doesn't exist yet.
    Returns the vector_store_id (e.g. 'vs_xxx').
    """
    stores = client.vector_stores.list()

    for store in stores.data:
        if store.name == VECTOR_STORE_NAME:
            print(f"Found existing vector store: {store.id}")
            return store.id

    new_store = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"Created new vector store: {new_store.id}")
    return new_store.id


def delete_old_file(client: OpenAI, vector_store_id: str, file_id: str):
    """
    Remove a file from the vector store and from OpenAI storage.
    Must be done before uploading the new version to avoid duplicates.
    """
    try:
        # Step 1: detach from vector store
        client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        # Step 2: delete the underlying file object
        client.files.delete(file_id)
    except Exception as e:
        # Don't abort the run — file may have been deleted manually
        print(f"  Warning: could not delete old file {file_id}: {e}")


# -----------------------------------------------------------------
# Main
# -----------------------------------------------------------------

def upload_changed_files(changed_slugs: list[str]) -> str:
    """
    Upload new or updated Markdown files to the OpenAI Vector Store.

    Args:
      changed_slugs: slugs returned by scrape()

    Returns:
      vector_store_id — passed to attach_vector_store_to_assistant()
    """
    if not changed_slugs:
        print("No files to upload.")
        return get_or_create_vector_store(get_client())

    client = get_client()
    state = load_upload_state()
    vector_store_id = get_or_create_vector_store(client)

    added = 0
    updated = 0

    for slug in changed_slugs:
        filepath = ARTICLES_DIR / f"{slug}.md"

        if not filepath.exists():
            print(f"  Skipping {slug} — file not found")
            continue

        is_update = slug in state

        if is_update:
            print(f"  Updating: {slug}")
            delete_old_file(client, vector_store_id, state[slug])
        else:
            print(f"  Adding: {slug}")

        # "rb" = read binary — the OpenAI SDK expects bytes, not a string
        with open(filepath, "rb") as f:
            uploaded_file = client.files.create(
                file=f,
                purpose="assistants",
            )

        client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=uploaded_file.id,
        )

        # Remember the file_id so we can delete it on the next update
        state[slug] = uploaded_file.id

        if is_update:
            updated += 1
        else:
            added += 1

    save_upload_state(state)

    print(f"\nUpload complete — added={added}  updated={updated}")
    print(f"Total files in vector store: {len(state)}")

    return vector_store_id


def attach_vector_store_to_assistant(client: OpenAI, vector_store_id: str):
    """Attach the vector store to the assistant so it can search the docs."""
    assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")
    if not assistant_id:
        raise ValueError("OPENAI_ASSISTANT_ID is not set in environment variables")

    client.beta.assistants.update(
        assistant_id,
        tool_resources={
            "file_search": {
                "vector_store_ids": [vector_store_id]
            }
        },
    )
    print(f"Attached vector store {vector_store_id} to assistant {assistant_id}")
