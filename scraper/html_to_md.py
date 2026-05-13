"""
Chuyển đổi HTML của một bài Zendesk thành Markdown sạch.
"""

# BeautifulSoup: thư viện đọc và chỉnh sửa HTML
from bs4 import BeautifulSoup

# markdownify: chuyển HTML tag thành cú pháp Markdown
from markdownify import markdownify

# re: thư viện xử lý chuỗi bằng Regular Expression
import re


def html_to_markdown(html: str, title: str, article_url: str) -> str:
    """
    Nhận vào:
      html        - nội dung HTML thô của bài viết
      title       - tiêu đề bài viết
      article_url - URL gốc (dùng để ghi vào đầu file và cho AI trích dẫn)

    Trả ra:
      Chuỗi Markdown sạch
    """

    # --- Bước A: Dùng BeautifulSoup phân tích cú pháp HTML ---
    # "lxml" là parser (bộ phân tích) HTML nhanh và chịu lỗi tốt
    soup = BeautifulSoup(html, "lxml")

    # --- Bước B: Xóa các thẻ không cần thiết ---
    # Những thẻ này thường chứa nav, quảng cáo, script JS, CSS...
    # Nếu không xóa, Markdown sẽ rất bẩn
    for tag in soup.select(
        "nav, footer, header, script, style, "
        "[role='navigation'], .header, .footer, .ads"
    ):
        tag.decompose()  # decompose() = xóa thẻ khỏi cây DOM hoàn toàn

    # --- Bước C: Chuyển HTML đã làm sạch → Markdown ---
    body_md = markdownify(
        str(soup),          # chuyển soup object về chuỗi HTML
        heading_style="ATX",  # dùng # ## ### thay vì === ---
        bullets="-",          # dùng dấu - cho bullet list
    )

    # --- Bước D: Dọn dẹp khoảng trắng thừa ---
    # \n{3,} = 3 dòng trống trở lên → thay bằng 2 dòng trống
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)

    # .strip() xóa khoảng trắng/dòng trống ở đầu và cuối chuỗi
    body_md = body_md.strip()

    # --- Bước E: Ghép thành file Markdown hoàn chỉnh ---
    # Dòng "Article URL:" rất quan trọng — AI sẽ dùng để trích dẫn nguồn
    return f"# {title}\n\nArticle URL: {article_url}\n\n{body_md}\n"
