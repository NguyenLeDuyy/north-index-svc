"""
main.py
Daily job entrypoint:
  1. Re-scrape the OptiSigns Help Center -> Markdown files.
  2. Diff against last run's hashes to find added/updated/unchanged files.
  3. Upload only the delta to the Gemini File Search Store.
  4. Log counts (added, updated, skipped) and exit 0.

Run via: docker run -e GEMINI_API_KEY=... <image>
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # reads .env into environment variables, no-op if file absent

from scraper import scrape
from state import diff_against_state, save_state, DEFAULT_STATE_PATH
from vector_store import sync_delta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("main")


def run() -> int:
    log.info("=== OptiBot daily sync job starting ===")

    try:
        files = scrape(min_articles=30)
    except Exception as e:
        log.error("Scrape step failed: %s", e)
        return 1

    if not files:
        log.error("No articles scraped -- aborting before touching the vector store.")
        return 1

    added, updated, skipped, new_state = diff_against_state(files, DEFAULT_STATE_PATH)

    if not added and not updated:
        log.info("No changes detected. added=0 updated=0 skipped=%d", len(skipped))
        save_state(new_state, DEFAULT_STATE_PATH)
        log.info("=== Job finished successfully (nothing to upload) ===")
        return 0

    try:
        results = sync_delta(added, updated)
    except Exception as e:
        log.error("Vector store sync failed: %s", e)
        return 1

    save_state(new_state, DEFAULT_STATE_PATH)

    log.info(
        "=== Job finished: added=%d updated=%d skipped=%d failed=%d ===",
        len(results["added"]), len(results["updated"]), len(skipped), len(results["failed"]),
    )
    return 0 if not results["failed"] else 1


if __name__ == "__main__":
    sys.exit(run())
