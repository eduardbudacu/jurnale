import os
import time
from pathlib import Path

from django.db import connection

from . import queue
from .ocr import get_provider

POLL_INTERVAL = float(os.environ.get("WORKER_POLL_INTERVAL", "1.0"))


def run_worker():
    """Main OCR worker loop: claim pages, run OCR, save results."""
    provider_name = os.environ.get("OCR_PROVIDER", "openai")
    model = os.environ.get("OCR_MODEL", None)
    provider = get_provider(provider_name, model=model)

    print(f"Worker started — provider={provider.name}, model={provider.model_name}")

    idle_count = 0
    try:
        while True:
            page = queue.claim_page()
            if page is None:
                idle_count += 1
                if idle_count >= 5:
                    print("No more pending pages. Exiting.")
                    break
                time.sleep(POLL_INTERVAL)
                continue

            idle_count = 0
            image_path = Path(page.image_path)
            print(f"Processing page {page.page_number} (id={page.id}): {image_path.name}")

            try:
                text = provider.ocr(image_path)
                queue.complete_page(page, text, provider.name, provider.model_name)
                print(f"  Done — {len(text)} chars extracted")
            except Exception as e:
                print(f"  FAILED: {e}")
                queue.fail_page(page, str(e))
    finally:
        connection.close()

    print("Worker finished.")
