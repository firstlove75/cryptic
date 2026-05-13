"""
Upload file Markdown lên OpenAI Vector Store.
Chỉ upload bài mới/đã thay đổi (danh sách nhận từ scraper).
"""

import os
import json
from pathlib import Path
from openai import OpenAI  # SDK chính thức của OpenAI

ARTICLES_DIR = Path("articles")

# File JSON lưu mapping: slug → openai_file_id
# Dùng để xóa file cũ trước khi upload phiên bản mới
UPLOAD_STATE_FILE = Path(".upload_state.json")

# Tên của Vector Store trên OpenAI (để tìm lại nếu đã tạo)
VECTOR_STORE_NAME = "optisigns-kb"


# -----------------------------------------------------------------
# Khởi tạo OpenAI client
# -----------------------------------------------------------------

def get_client() -> OpenAI:
    """
    Tạo OpenAI client từ API key trong biến môi trường.
    Nếu thiếu key → báo lỗi rõ ràng ngay.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Thiếu OPENAI_API_KEY trong environment variables")
    return OpenAI(api_key=api_key)


# -----------------------------------------------------------------
# Hàm phụ trợ
# -----------------------------------------------------------------

def load_upload_state() -> dict:
    """Đọc trạng thái upload cũ. {} nếu chưa có."""
    if UPLOAD_STATE_FILE.exists():
        return json.loads(UPLOAD_STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_upload_state(state: dict):
    """Lưu trạng thái upload xuống đĩa."""
    UPLOAD_STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def get_or_create_vector_store(client: OpenAI) -> str:
    """
    Tìm Vector Store đã tạo theo tên.
    Nếu chưa tồn tại → tạo mới.
    Trả về vector_store_id (dạng 'vs_xxx').
    """
    # Liệt kê tất cả vector stores của account
    stores = client.vector_stores.list()

    for store in stores.data:
        if store.name == VECTOR_STORE_NAME:
            print(f"Found existing vector store: {store.id}")
            return store.id

    # Chưa có → tạo mới
    new_store = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"Created new vector store: {new_store.id}")
    return new_store.id


def delete_old_file(client: OpenAI, vector_store_id: str, file_id: str):
    """
    Xóa file cũ khỏi Vector Store và khỏi OpenAI Files.
    Cần làm trước khi upload phiên bản mới để tránh duplicate.
    """
    try:
        # Bước 1: Gỡ file khỏi vector store
        client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        # Bước 2: Xóa file khỏi OpenAI hoàn toàn
        client.files.delete(file_id)
    except Exception as e:
        # Không dừng chương trình nếu xóa thất bại
        # (file có thể đã bị xóa thủ công trước đó)
        print(f"  Warning: could not delete old file {file_id}: {e}")


# -----------------------------------------------------------------
# Hàm chính
# -----------------------------------------------------------------

def upload_changed_files(changed_slugs: list[str]) -> str:
    """
    Upload các file Markdown đã thay đổi lên OpenAI Vector Store.

    Args:
      changed_slugs: danh sách slug từ hàm scrape()

    Returns:
      vector_store_id — để attach vào Assistant
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

        is_update = slug in state  # bài đã upload trước đó?

        # Xóa phiên bản cũ nếu là bài cập nhật
        if is_update:
            print(f"  Updating: {slug}")
            delete_old_file(client, vector_store_id, state[slug])
        else:
            print(f"  Adding: {slug}")

        # Mở file và upload lên OpenAI
        # "rb" = read binary — OpenAI cần bytes, không phải string
        with open(filepath, "rb") as f:
            uploaded_file = client.files.create(
                file=f,
                purpose="assistants",  # mục đích: dùng cho Assistant
            )

        # Gắn file vừa upload vào Vector Store
        client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=uploaded_file.id,
        )

        # Lưu mapping slug → file_id để lần sau biết file nào cần xóa
        state[slug] = uploaded_file.id

        if is_update:
            updated += 1
        else:
            added += 1

    # Lưu trạng thái
    save_upload_state(state)

    total = len(state)
    print(f"\nUpload complete — added={added}  updated={updated}")
    print(f"Total files in vector store: {total}")

    return vector_store_id


def attach_vector_store_to_assistant(client: OpenAI, vector_store_id: str):
    """
    Gắn Vector Store vào Assistant để nó có thể tìm kiếm trong đó.
    """
    assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")
    if not assistant_id:
        raise ValueError("Thiếu OPENAI_ASSISTANT_ID trong environment variables")

    client.beta.assistants.update(
        assistant_id,
        tool_resources={
            "file_search": {
                "vector_store_ids": [vector_store_id]
            }
        },
    )
    print(f"Attached vector store {vector_store_id} to assistant {assistant_id}")
