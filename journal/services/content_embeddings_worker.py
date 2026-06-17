import os
import threading
import time

from django.db import connection

from . import queue
from .embeddings import describe, embed_text

POLL_INTERVAL = float(os.environ.get("EMBEDDING_POLL_INTERVAL", "1.0"))


def _worker_loop(worker_id: int):
    """Single worker loop: claim content-embedding jobs and process them."""
    print(f"Content embedding worker {worker_id} started — model={describe()}")

    idle_count = 0
    try:
        while True:
            job = queue.claim_content_embedding_job()
            if job is None:
                idle_count += 1
                if idle_count >= 5:
                    print(f"Worker {worker_id}: no more pending jobs. Exiting.")
                    break
                time.sleep(POLL_INTERVAL)
                continue

            idle_count = 0
            job_id = job.id
            page_id = job.page_id
            print(f"Worker {worker_id}: processing content embedding job {job_id} (page_id={page_id})")

            try:
                ocr_text = queue.get_page_ocr_text(page_id)
                if not ocr_text:
                    queue.fail_content_embedding_job(job, "No OCR text available")
                    continue

                embedding = embed_text(ocr_text)
                queue.complete_content_embedding_job(job, embedding)
                print(f"Worker {worker_id}: done — dim={len(embedding)}")
            except Exception as e:
                print(f"Worker {worker_id}: FAILED — {e}")
                queue.fail_content_embedding_job(job, str(e))
    finally:
        connection.close()

    print(f"Content embedding worker {worker_id} finished.")


def run_content_embedding_workers(n: int = 2):
    """Spawn n worker threads to process content embedding jobs."""
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

    print("All content embedding workers finished.")
