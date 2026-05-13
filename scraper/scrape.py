"""
Fetch articles from the OptiSigns Zendesk Help Center API,
convert them to Markdown, and save to articles/.

Change detection: compare MD5 hashes between runs.
"""

import requests
import hashlib
import json
from pathlib import Path

from scraper.html_to_md import html_to_markdown

# -----------------------------------------------------------------
# Config
# -----------------------------------------------------------------

# Zendesk API endpoint — returns paginated JSON list of articles
# per_page=100 is the maximum Zendesk allows per request
BASE_URL = (
    "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
    "?per_page=100"
)

ARTICLES_DIR = Path("articles")

# Persists content hashes across runs to detect new/changed articles
HASH_FILE = Path(".article_hashes.json")


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def fetch_all_articles() -> list[dict]:
    """
    Fetch every article from the Zendesk API, following pagination.
    Zendesk includes a 'next_page' URL in each response until the last page.
    """
    articles = []
    url = BASE_URL

    while url:
        print(f"  Fetching: {url}")
        response = requests.get(url, timeout=30)

        # Raise immediately on 4xx/5xx so we don't silently process bad data
        response.raise_for_status()

        data = response.json()
        articles.extend(data["articles"])

        # None on the last page
        url = data.get("next_page")

    return articles


def compute_hash(text: str) -> str:
    """Return the MD5 hex digest of a string."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def load_hashes() -> dict:
    """Load hashes saved from the previous run. Returns {} on first run."""
    if HASH_FILE.exists():
        return json.loads(HASH_FILE.read_text(encoding="utf-8"))
    return {}


def save_hashes(hashes: dict):
    """Persist hash dict to disk as JSON."""
    HASH_FILE.write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def article_slug(article: dict) -> str:
    """
    Derive a filesystem-safe slug from the article URL.

    Example:
      URL   = ".../articles/360001234567-how-to-add-youtube"
      slug  = "360001234567-how-to-add-youtube"
    """
    # html_url: "https://support.optisigns.com/hc/en-us/articles/<slug>"
    # .rstrip("/")  removes a trailing slash if present
    # .split("/")   splits on every slash
    # [-1]          takes the last segment
    return article["html_url"].rstrip("/").split("/")[-1]


# -----------------------------------------------------------------
# Main
# -----------------------------------------------------------------

def scrape() -> list[str]:
    """
    Run the full scrape pipeline:
      1. Fetch all articles from Zendesk
      2. Skip articles whose content hash hasn't changed
      3. Convert changed articles HTML → Markdown and write to disk
      4. Save updated hashes

    Returns:
      List of slugs that were added or updated (to be uploaded to OpenAI)
    """
    ARTICLES_DIR.mkdir(exist_ok=True)

    print("Fetching articles from Zendesk...")
    articles = fetch_all_articles()
    print(f"Total articles found: {len(articles)}")

    hashes = load_hashes()

    added = 0
    updated = 0
    skipped = 0
    changed_slugs = []

    for article in articles:
        slug = article_slug(article)
        body_html = article.get("body") or ""
        new_hash = compute_hash(body_html)

        # Content unchanged — skip
        if hashes.get(slug) == new_hash:
            skipped += 1
            continue

        markdown = html_to_markdown(
            html=body_html,
            title=article["title"],
            article_url=article["html_url"],
        )

        filepath = ARTICLES_DIR / f"{slug}.md"
        is_new = not filepath.exists()

        filepath.write_text(markdown, encoding="utf-8")
        hashes[slug] = new_hash
        changed_slugs.append(slug)

        if is_new:
            added += 1
        else:
            updated += 1

    save_hashes(hashes)

    print(f"\nScrape complete — added={added}  updated={updated}  skipped={skipped}")
    return changed_slugs
