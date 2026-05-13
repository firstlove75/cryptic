"""
Convert a Zendesk article's HTML body into clean Markdown.
"""

from bs4 import BeautifulSoup
from markdownify import markdownify
import re


def html_to_markdown(html: str, title: str, article_url: str) -> str:
    """
    Args:
      html        - raw HTML body of the article
      title       - article title
      article_url - canonical URL (embedded so the AI can cite it)

    Returns:
      Clean Markdown string
    """

    # --- Step A: Parse HTML with BeautifulSoup ---
    # "lxml" is a fast, fault-tolerant HTML parser
    soup = BeautifulSoup(html, "lxml")

    # --- Step B: Strip noise tags ---
    # These typically contain nav, ads, JS, CSS — dirty Markdown otherwise
    for tag in soup.select(
        "nav, footer, header, script, style, "
        "[role='navigation'], .header, .footer, .ads"
    ):
        tag.decompose()  # remove tag and its children from the DOM tree

    # --- Step C: Convert cleaned HTML → Markdown ---
    body_md = markdownify(
        str(soup),
        heading_style="ATX",  # use # ## ### instead of === ---
        bullets="-",
    )

    # --- Step D: Normalise whitespace ---
    # Collapse 3+ consecutive blank lines down to 2
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)
    body_md = body_md.strip()

    # --- Step E: Assemble final Markdown file ---
    # The "Article URL:" line is critical — the AI reads it for citations
    return f"# {title}\n\nArticle URL: {article_url}\n\n{body_md}\n"
