"""
Entry point của toàn bộ pipeline.
Docker sẽ chạy file này mỗi ngày.

Luồng:
  1. Đọc biến môi trường từ file .env (nếu chạy local)
  2. Scrape bài mới/thay đổi từ Zendesk
  3. Upload delta lên OpenAI Vector Store
  4. Gắn Vector Store vào Assistant
"""

# python-dotenv: đọc file .env và nạp vào os.environ
# load_dotenv() phải gọi TRƯỚC khi import các module dùng os.environ
from dotenv import load_dotenv
load_dotenv()  # đọc file .env trong thư mục hiện tại

# Import sau khi đã load .env
from scraper.scrape import scrape
from uploader.upload import upload_changed_files, attach_vector_store_to_assistant, get_client


def main():
    print("=" * 50)
    print("OptiBot daily sync — START")
    print("=" * 50)

    # --- Bước 1: Scrape ---
    # Trả về list slug của bài mới/thay đổi
    changed_slugs = scrape()

    # --- Bước 2: Upload ---
    # Nếu không có gì thay đổi, hàm này vẫn chạy nhưng không upload gì
    vector_store_id = upload_changed_files(changed_slugs)

    # --- Bước 3: Gắn vào Assistant ---
    # Làm mỗi lần để đảm bảo assistant luôn dùng đúng vector store
    client = get_client()
    attach_vector_store_to_assistant(client, vector_store_id)

    print("=" * 50)
    print("OptiBot daily sync — DONE")
    print("=" * 50)


# Đây là cách Python chạy file trực tiếp
# Khi Docker chạy "python main.py", điều kiện này là True
# Khi file được import bởi file khác, điều kiện này là False
if __name__ == "__main__":
    main()
