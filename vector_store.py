"""
vector_store.py
Wraps Gemini API's File Search Tool, Google's managed RAG / vector-store
equivalent to OpenAI's Vector Store. Handles:
  - creating (or reusing) a File Search Store
  - uploading files into it (this IS the "programmatic vector store load"
    the take-home requires -- no UI drag-and-drop)
  - deleting + re-uploading a file when it changed (Gemini File Search
    stores don't support in-place update of a document's content)

Docs: https://ai.google.dev/gemini-api/docs/file-search
"""

import os
import logging
from pathlib import Path

from google import genai
from google.genai import types

log = logging.getLogger("vector_store")

STORE_DISPLAY_NAME = os.environ.get("FILE_SEARCH_STORE_NAME", "optibot-mini-clone-kb")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.

• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def get_client() -> genai.Client:
    api_key = os.environ["GEMINI_API_KEY"]
    return genai.Client(api_key=api_key)


def get_or_create_store(client: genai.Client):
    """
    Reuse an existing store by display name if one exists (idempotent across
    daily runs), otherwise create a new one.
    """
    for store in client.file_search_stores.list():
        if store.display_name == STORE_DISPLAY_NAME:
            log.info("Reusing existing File Search Store: %s", store.name)
            return store

    store = client.file_search_stores.create(
        config={"display_name": STORE_DISPLAY_NAME, "embedding_model": EMBEDDING_MODEL}
    )
    log.info("Created new File Search Store: %s", store.name)
    return store


def _find_existing_document(client: genai.Client, store_name: str, display_name: str):
    for doc in client.file_search_stores.documents.list(parent=store_name):
        if doc.display_name == display_name:
            return doc
    return None


def upload_file(client: genai.Client, store_name: str, path: Path, is_update: bool = False) -> dict:
    """
    Upload one markdown file into the store. Chunking is handled automatically
    by the File Search Tool (see README for the chunking-strategy note).
    If is_update, delete the old document version first (Gemini has no
    "replace" endpoint for File Search documents).
    """
    display_name = path.name

    if is_update:
        existing = _find_existing_document(client, store_name, display_name)
        if existing:
            client.file_search_stores.documents.delete(name=existing.name)
            log.info("Deleted old version of %s before re-upload", display_name)

    operation = client.file_search_stores.upload_to_file_search_store(
        file=str(path),
        file_search_store_name=store_name,
        config={"display_name": display_name, "mime_type": "text/markdown"},
    )
    # upload_to_file_search_store returns a long-running operation; wait for it
    while not operation.done:
        operation = client.operations.get(operation)

    return {"file": display_name, "chunks": getattr(operation.response, "chunk_count", None)}


def sync_delta(added: list[Path], updated: list[Path]) -> dict:
    """
    Entry point called by main.py: uploads only the delta (added + updated).
    Returns a summary dict for logging.
    """
    client = get_client()
    store = get_or_create_store(client)

    results = {"added": [], "updated": [], "failed": []}

    for path in added:
        try:
            info = upload_file(client, store.name, path, is_update=False)
            results["added"].append(info)
        except Exception as e:
            log.error("Failed to upload %s: %s", path, e)
            results["failed"].append(str(path))

    for path in updated:
        try:
            info = upload_file(client, store.name, path, is_update=True)
            results["updated"].append(info)
        except Exception as e:
            log.error("Failed to re-upload %s: %s", path, e)
            results["failed"].append(str(path))

    total_files = len(results["added"]) + len(results["updated"])
    total_chunks = sum(
        (r["chunks"] or 0) for r in results["added"] + results["updated"]
    )
    log.info(
        "Vector store sync done: %d files uploaded (%d chunks), %d failed",
        total_files, total_chunks, len(results["failed"]),
    )
    results["store_name"] = store.name
    return results


def sanity_check_query(question: str = "How do I add a YouTube video?") -> str:
    """
    Quick sanity check used to produce the required screenshot: ask the
    assistant a question and print the grounded answer + citations.
    """
    client = get_client()
    store = get_or_create_store(client)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(file_search_store_names=[store.name])
                )
            ],
        ),
    )
    return response.text


if __name__ == "__main__":
    print(sanity_check_query())
