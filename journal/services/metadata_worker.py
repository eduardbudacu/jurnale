import json
import os
import threading
import time

import requests
from django.db import connection

from . import queue

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
METADATA_MODEL = os.environ.get("METADATA_MODEL", "gemma3:12b")
POLL_INTERVAL = float(os.environ.get("METADATA_POLL_INTERVAL", "1.0"))

PROMPT_TEMPLATE = """Analyze the following journal page text and extract metadata.
Return ONLY valid JSON with this exact structure, no other text:
{{"date": "the date if mentioned (e.g. 'January 5, 2013') or null", "summary": "a 1-2 sentence summary of the page content", "tags": ["tag1", "tag2"]}}

Tags should be lowercase single words or short phrases describing key themes (e.g. "travel", "family", "work", "health", "weather", "emotions", "food", "school", "friends", "holiday").
Extract at most 5 tags.

Page text:
{text}"""


def _extract_metadata(ocr_text: str) -> dict:
    """Call Ollama to extract metadata from OCR text."""
    prompt = PROMPT_TEMPLATE.format(text=ocr_text[:4000])

    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": METADATA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json()["response"]

    # Try to extract JSON from the response. Sometimes the model wraps it in
    # markdown code blocks.
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    result = json.loads(text)
    return {
        "date": result.get("date") if result.get("date") != "null" else None,
        "summary": result.get("summary"),
        "tags": result.get("tags", []),
    }


def _worker_loop(worker_id: int):
    """Single worker loop: claim metadata jobs and process them."""
    print(f"Metadata worker {worker_id} started — model={METADATA_MODEL}")

    idle_count = 0
    try:
        while True:
            job = queue.claim_metadata_job()
            if job is None:
                idle_count += 1
                if idle_count >= 5:
                    print(f"Worker {worker_id}: no more pending jobs. Exiting.")
                    break
                time.sleep(POLL_INTERVAL)
                continue

            idle_count = 0
            meta_id = job.id
            page_id = job.page_id
            print(f"Worker {worker_id}: processing metadata job {meta_id} (page_id={page_id})")

            try:
                ocr_text = queue.get_page_ocr_text(page_id)
                if not ocr_text:
                    queue.fail_metadata_job(job, "No OCR text available")
                    continue

                result = _extract_metadata(ocr_text)
                queue.complete_metadata_job(
                    job,
                    date_value=result["date"],
                    summary=result["summary"],
                    tags=result["tags"],
                )
                tag_str = ", ".join(result["tags"]) if result["tags"] else "none"
                print(f"Worker {worker_id}: done — date={result['date']}, tags=[{tag_str}]")
            except Exception as e:
                print(f"Worker {worker_id}: FAILED — {e}")
                queue.fail_metadata_job(job, str(e))
    finally:
        connection.close()

    print(f"Metadata worker {worker_id} finished.")


def run_metadata_workers(n: int = 2):
    """Spawn n worker threads to process metadata jobs."""
    if n == 1:
        _worker_loop(0)
        return

    threads = []
    for i in range(n):
        t = threading.Thread(target=_worker_loop, args=(i,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("All metadata workers finished.")
