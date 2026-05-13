"""
Pipeline entry point — Docker runs this file once per day.

Flow:
  1. Load environment variables from .env (local runs only)
  2. Scrape new/changed articles from Zendesk
  3. Upload the delta to the OpenAI Vector Store
  4. Attach the Vector Store to the Assistant
"""

# load_dotenv() must be called before importing modules that read os.environ
from dotenv import load_dotenv
load_dotenv()

from scraper.scrape import scrape
from uploader.upload import upload_changed_files, attach_vector_store_to_assistant, get_client


def main():
    print("=" * 50)
    print("OptiBot daily sync — START")
    print("=" * 50)

    # Step 1: Scrape — returns slugs of articles that are new or changed
    changed_slugs = scrape()

    # Step 2: Upload — no-ops if nothing changed
    vector_store_id = upload_changed_files(changed_slugs)

    # Step 3: Attach — keeps the assistant pointed at the correct vector store
    client = get_client()
    attach_vector_store_to_assistant(client, vector_store_id)

    print("=" * 50)
    print("OptiBot daily sync — DONE")
    print("=" * 50)


# True when Docker runs "python main.py" directly
# False when this file is imported by another module
if __name__ == "__main__":
    main()
