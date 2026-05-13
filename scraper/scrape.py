"""
Tải bài viết từ Zendesk Help Center API của OptiSigns,
chuyển sang Markdown, lưu vào thư mục articles/.

Phát hiện bài mới/thay đổi bằng cách so sánh MD5 hash.
"""

import requests    # gửi HTTP request
import hashlib     # tạo MD5 hash để so sánh nội dung
import json        # đọc/ghi file JSON (lưu hash cũ)
import os          # đọc biến môi trường, kiểm tra file
from pathlib import Path  # thao tác đường dẫn file kiểu hiện đại

# Import hàm chuyển đổi HTML → Markdown từ file cùng thư mục
from scraper.html_to_md import html_to_markdown

# -----------------------------------------------------------------
# Cấu hình
# -----------------------------------------------------------------

# API endpoint của Zendesk — trả về JSON danh sách bài viết
# per_page=100 : lấy 100 bài mỗi trang (tối đa Zendesk cho phép)
BASE_URL = (
    "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
    "?per_page=100"
)

# Thư mục lưu file .md
ARTICLES_DIR = Path("articles")

# File JSON lưu hash của từng bài — dùng để phát hiện bài thay đổi
HASH_FILE = Path(".article_hashes.json")


# -----------------------------------------------------------------
# Hàm phụ trợ
# -----------------------------------------------------------------

def fetch_all_articles() -> list[dict]:
    """
    Gọi Zendesk API, lấy toàn bộ bài viết.
    Zendesk dùng pagination: mỗi response có trường 'next_page'
    nếu còn trang tiếp theo.
    """
    articles = []
    url = BASE_URL  # bắt đầu từ trang 1

    while url:  # lặp cho đến khi không còn trang tiếp theo
        print(f"  Fetching: {url}")
        response = requests.get(url, timeout=30)

        # raise_for_status(): nếu HTTP status là 4xx/5xx thì ném exception
        # — tốt hơn là để code chạy tiếp với dữ liệu rỗng/sai
        response.raise_for_status()

        data = response.json()  # parse JSON → Python dict

        # data["articles"] là list các bài trong trang này
        articles.extend(data["articles"])

        # next_page = None nếu đây là trang cuối
        url = data.get("next_page")

    return articles


def compute_hash(text: str) -> str:
    """Tạo MD5 hash của một chuỗi — dùng để so sánh nội dung."""
    # encode("utf-8"): chuyển string → bytes (hashlib cần bytes)
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def load_hashes() -> dict:
    """
    Đọc file hash cũ từ đĩa.
    Trả về {} nếu file chưa tồn tại (lần chạy đầu tiên).
    """
    if HASH_FILE.exists():
        return json.loads(HASH_FILE.read_text(encoding="utf-8"))
    return {}


def save_hashes(hashes: dict):
    """Ghi dict hash xuống file JSON."""
    HASH_FILE.write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def article_slug(article: dict) -> str:
    """
    Tạo tên file từ URL bài viết.
    Ví dụ: URL = ".../360001234567-how-to-add-youtube"
           → slug = "360001234567-how-to-add-youtube"
    """
    # html_url ví dụ: "https://support.optisigns.com/hc/en-us/articles/360001234567-how-to-add-youtube"
    # .rstrip("/")  : xóa dấu / cuối nếu có
    # .split("/")   : tách theo /
    # [-1]          : lấy phần tử cuối cùng
    return article["html_url"].rstrip("/").split("/")[-1]


# -----------------------------------------------------------------
# Hàm chính
# -----------------------------------------------------------------

def scrape() -> list[str]:
    """
    Chạy toàn bộ pipeline scrape:
      1. Tải danh sách bài từ Zendesk
      2. So sánh hash — bỏ qua bài không thay đổi
      3. Chuyển HTML → Markdown, lưu file
      4. Cập nhật hash file
      5. Trả về danh sách slug của bài đã thay đổi (để upload)

    Returns:
      List[str] — các slug cần upload lên OpenAI
    """
    ARTICLES_DIR.mkdir(exist_ok=True)  # tạo thư mục nếu chưa có

    print("Fetching articles from Zendesk...")
    articles = fetch_all_articles()
    print(f"Total articles found: {len(articles)}")

    hashes = load_hashes()  # hash của lần chạy trước

    added = 0
    updated = 0
    skipped = 0
    changed_slugs = []  # danh sách bài cần upload

    for article in articles:
        slug = article_slug(article)
        body_html = article.get("body") or ""  # nội dung HTML của bài

        # Tính hash của nội dung mới
        new_hash = compute_hash(body_html)

        # Nếu hash giống lần trước → bài không thay đổi → bỏ qua
        if hashes.get(slug) == new_hash:
            skipped += 1
            continue  # nhảy sang bài tiếp theo

        # Bài mới hoặc đã thay đổi → xử lý
        markdown = html_to_markdown(
            html=body_html,
            title=article["title"],
            article_url=article["html_url"],
        )

        filepath = ARTICLES_DIR / f"{slug}.md"
        is_new = not filepath.exists()  # file chưa tồn tại = bài mới

        # Ghi file Markdown
        filepath.write_text(markdown, encoding="utf-8")

        # Cập nhật hash
        hashes[slug] = new_hash
        changed_slugs.append(slug)

        if is_new:
            added += 1
        else:
            updated += 1

    # Lưu hash mới xuống đĩa
    save_hashes(hashes)

    # In tổng kết
    print(f"\nScrape complete — added={added}  updated={updated}  skipped={skipped}")
    return changed_slugs
