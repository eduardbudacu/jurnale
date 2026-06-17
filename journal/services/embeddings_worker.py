import os
import threading
import time

from django.db import connection

from . import queue
from .embeddings import describe, embed_text

POLL_INTERVAL = float(os.environ.get("EMBEDDING_POLL_INTERVAL", "1.0"))


def _worker_loop(worker_id: int):
    """Single worker loop: claim summary-embedding jobs and process them."""
    print(f"Embedding worker {worker_id} started — model={describe()}")

    idle_count = 0
    try:
        while True:
            job = queue.claim_embedding_job()
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
            print(f"Worker {worker_id}: processing embedding job {job_id} (page_id={page_id})")

            try:
                summary = queue.get_page_summary(page_id)
                if not summary:
                    queue.fail_embedding_job(job, "No summary available")
                    continue

                embedding = embed_text(summary)
                queue.complete_embedding_job(job, embedding)
                print(f"Worker {worker_id}: done — dim={len(embedding)}")
            except Exception as e:
                print(f"Worker {worker_id}: FAILED — {e}")
                queue.fail_embedding_job(job, str(e))
    finally:
        connection.close()

    print(f"Embedding worker {worker_id} finished.")


def run_embedding_workers(n: int = 2):
    """Spawn n worker threads to process embedding jobs."""
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

    print("All embedding workers finished.")
