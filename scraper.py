"""
scraper.py
Pulls published articles from the OptiSigns (Zendesk) Help Center via the
public Help Center API and converts each one into a clean Markdown file.

Zendesk Help Center API docs:
https://developer.zendesk.com/api-reference/help_center/help-center-api/articles/

No auth is required to read *published* articles from a public Help Center.
"""

import os
import re
import time
import logging
from pathlib import Path

import requests
from markdownify import markdownify as html_to_md
from slugify import slugify

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scraper")

HELP_CENTER_BASE = os.environ.get(
    "ZENDESK_HELP_CENTER_URL", "https://support.optisigns.com"
)
LOCALE = os.environ.get("ZENDESK_LOCALE", "en-us")
ARTICLES_ENDPOINT = f"{HELP_CENTER_BASE}/api/v2/help_center/{LOCALE}/articles.json"
PAGE_SIZE = 100  # Zendesk max per_page

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data/articles"))


def fetch_all_articles(min_articles: int = 30) -> list[dict]:
    """
    Page through the Zendesk Help Center API and return published articles.
    Stops once we've paged through everything (Zendesk paginates via `next_page`).
    """
    articles = []
    url = f"{ARTICLES_ENDPOINT}?per_page={PAGE_SIZE}"

    while url:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        batch = [a for a in payload.get("articles", []) if not a.get("draft", False)]
        articles.extend(batch)
        log.info("Fetched %d articles (running total: %d)", len(batch), len(articles))

        url = payload.get("next_page")  # Zendesk gives a full next-page URL or None
        if url:
            time.sleep(0.3)  # be polite to the API

    if len(articles) < min_articles:
        log.warning(
            "Only found %d articles; task asks for >= %d. "
            "Check locale/category filters if this looks wrong.",
            len(articles), min_articles,
        )

    return articles


def clean_markdown(html_body: str, article_url: str) -> str:
    """
    Convert Zendesk's HTML article body into clean Markdown:
    - strip nav/promo cruft Zendesk sometimes injects
    - keep headings, links, code blocks
    - prepend an 'Article URL:' line so the assistant can cite it verbatim
    """
    if not html_body:
        return f"Article URL: {article_url}\n\n*(No content)*\n"

    md = html_to_md(
        html_body,
        heading_style="ATX",
        bullets="-",
        code_language="",
        strip=["script", "style", "nav", "footer", "iframe"],
    )

    # Collapse 3+ blank lines down to 2, trim trailing whitespace per line
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()

    return f"Article URL: {article_url}\n\n{md}\n"


def save_article(article: dict) -> Path:
    title = article["title"]
    slug = slugify(title)[:80] or f"article-{article['id']}"
    out_path = OUTPUT_DIR / f"{slug}.md"

    body_md = clean_markdown(article.get("body", ""), article.get("html_url", ""))
    content = f"# {title}\n\n{body_md}"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def scrape(min_articles: int = 30) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    articles = fetch_all_articles(min_articles=min_articles)

    written = []
    for article in articles:
        path = save_article(article)
        written.append(path)

    log.info("Wrote %d markdown files to %s", len(written), OUTPUT_DIR)
    return written


if __name__ == "__main__":
    scrape()
