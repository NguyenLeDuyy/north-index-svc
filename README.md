# OptiBot Mini-Clone

A minimal clone of OptiSigns' support bot: scrapes the public Help Center,
loads it into a Gemini File Search Store (Google's managed RAG/vector store),
and re-syncs daily via a Dockerized job.

## How it works

1. **`scraper.py`** — pulls all published articles from the Zendesk Help
   Center API (`/api/v2/help_center/en-us/articles.json`, paginated), strips
   nav/promo HTML, and converts each to clean Markdown under
   `data/articles/<slug>.md`, prefixed with an `Article URL:` line so the
   assistant can cite sources.
2. **`state.py`** — hashes each markdown file (SHA-256) and diffs against
   `state/hashes.json` from the previous run to classify files as
   added / updated / skipped.
3. **`vector_store.py`** — creates (or reuses) a Gemini **File Search
   Store** and uploads only the delta via the API (`file_search_stores`,
   `documents.upload`) — no UI drag-and-drop. Updated files are deleted and
   re-uploaded, since File Search documents are immutable once indexed.
4. **`main.py`** — orchestrates the three steps above, logs
   `added / updated / skipped` counts, and exits 0 on success (non-zero on
   failure, so a scheduler can alert).

## Chunking strategy

Chunking is handled automatically by Gemini's File Search Tool at index
time — no manual splitting needed. Each Markdown file is uploaded as one
document; Gemini semantically chunks it internally using
`gemini-embedding-001`.

## Run locally

```bash
cp .env.sample .env   # fill in GEMINI_API_KEY
pip install -r requirements.txt
python main.py
```

## Run in Docker (one-shot)

```bash
docker build -t optibot-mini-clone .
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/state:/app/state \
  -e GEMINI_API_KEY=your-key-here \
  optibot-mini-clone
```
Volumes for `data/` and `state/` are required so delta-detection persists
between runs — without them every run looks like a fresh "all added".

## Deploy as a daily job

Deployed on **[cloud provider — e.g. Railway / Render / Fly.io]** as a
scheduled job running once every 24h, with `data/` and `state/` mounted to
a persistent volume. Job logs: **[link to logs / last run artifact]**.

## Sanity check

`python vector_store.py` asks the assistant *"How do I add a YouTube
video?"* and prints the grounded, cited answer.
Screenshot: **[screenshot.png]**

## Assumptions / notes

- Only published (non-draft) articles are scraped.
- The Help Center API used here is public/unauthenticated (standard for
  Zendesk Help Centers open to end users); no API key needed for reads.
