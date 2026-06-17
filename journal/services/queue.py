"""Work-queue helpers built on the Django ORM.

Workers claim rows with ``SELECT ... FOR UPDATE SKIP LOCKED`` (via
``select_for_update(skip_locked=True)``) inside a short transaction, then
release the lock before doing slow network work — identical semantics to the
original raw-SQL pipeline.
"""
from django.db import transaction
from django.utils import timezone

from journal.models import (
    Journal,
    Page,
    PageContentEmbedding,
    PageMetadata,
    PageMetadataTag,
    PageSummaryEmbedding,
)

# --- OCR pages --------------------------------------------------------------

def claim_page() -> Page | None:
    """Claim the next pending page, marking it 'processing'."""
    with transaction.atomic():
        page = (
            Page.objects.select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("journal_id", "page_number")
            .first()
        )
        if page is None:
            return None
        page.status = "processing"
        page.save(update_fields=["status"])
        return page


def complete_page(page: Page, ocr_text: str, provider: str, model: str) -> None:
    page.status = "done"
    page.ocr_text = ocr_text
    page.ocr_provider = provider
    page.ocr_model = model
    page.processed_at = timezone.now()
    page.save(update_fields=["status", "ocr_text", "ocr_provider", "ocr_model", "processed_at"])


def fail_page(page: Page, error: str) -> None:
    page.status = "failed"
    page.error = error
    page.processed_at = timezone.now()
    page.save(update_fields=["status", "error", "processed_at"])


def reset_pending() -> int:
    """Reset all non-done pages back to pending (for re-enqueue)."""
    return Page.objects.filter(status__in=["failed", "processing"]).update(
        status="pending", error=None
    )


# --- Metadata jobs ----------------------------------------------------------

def enqueue_metadata_jobs() -> int:
    """Create pending metadata jobs for done pages that don't have one yet."""
    page_ids = (
        Page.objects.filter(status="done")
        .exclude(id__in=PageMetadata.objects.values("page_id"))
        .values_list("id", flat=True)
    )
    objs = [PageMetadata(page_id=pid) for pid in page_ids]
    PageMetadata.objects.bulk_create(objs)
    return len(objs)


def claim_metadata_job() -> PageMetadata | None:
    with transaction.atomic():
        job = (
            PageMetadata.objects.select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("id")
            .first()
        )
        if job is None:
            return None
        job.status = "processing"
        job.save(update_fields=["status"])
        return job


def complete_metadata_job(job: PageMetadata, date_value, summary, tags) -> None:
    with transaction.atomic():
        job.status = "done"
        job.date_value = date_value
        job.summary = summary
        job.processed_at = timezone.now()
        job.save(update_fields=["status", "date_value", "summary", "processed_at"])
        PageMetadataTag.objects.bulk_create(
            [PageMetadataTag(page_metadata=job, tag=t.strip().lower()) for t in tags]
        )


def fail_metadata_job(job: PageMetadata, error: str) -> None:
    job.status = "failed"
    job.error = error
    job.processed_at = timezone.now()
    job.save(update_fields=["status", "error", "processed_at"])


# --- Summary embeddings -----------------------------------------------------

def enqueue_embedding_jobs() -> int:
    """Create embedding jobs for pages that have a summary."""
    page_ids = (
        PageMetadata.objects.filter(status="done", summary__isnull=False)
        .exclude(page_id__in=PageSummaryEmbedding.objects.values("page_id"))
        .values_list("page_id", flat=True)
    )
    objs = [PageSummaryEmbedding(page_id=pid) for pid in page_ids]
    PageSummaryEmbedding.objects.bulk_create(objs)
    return len(objs)


def claim_embedding_job() -> PageSummaryEmbedding | None:
    with transaction.atomic():
        job = (
            PageSummaryEmbedding.objects.select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("id")
            .first()
        )
        if job is None:
            return None
        job.status = "processing"
        job.save(update_fields=["status"])
        return job


def complete_embedding_job(job: PageSummaryEmbedding, embedding: list[float]) -> None:
    job.status = "done"
    job.embedding = embedding
    job.processed_at = timezone.now()
    job.save(update_fields=["status", "embedding", "processed_at"])


def fail_embedding_job(job: PageSummaryEmbedding, error: str) -> None:
    job.status = "failed"
    job.error = error
    job.processed_at = timezone.now()
    job.save(update_fields=["status", "error", "processed_at"])


# --- Content embeddings -----------------------------------------------------

def enqueue_content_embedding_jobs() -> int:
    """Create content embedding jobs for all done pages that have OCR text."""
    page_ids = (
        Page.objects.filter(status="done", ocr_text__isnull=False)
        .exclude(id__in=PageContentEmbedding.objects.values("page_id"))
        .values_list("id", flat=True)
    )
    objs = [PageContentEmbedding(page_id=pid) for pid in page_ids]
    PageContentEmbedding.objects.bulk_create(objs)
    return len(objs)


def claim_content_embedding_job() -> PageContentEmbedding | None:
    with transaction.atomic():
        job = (
            PageContentEmbedding.objects.select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("id")
            .first()
        )
        if job is None:
            return None
        job.status = "processing"
        job.save(update_fields=["status"])
        return job


def complete_content_embedding_job(job: PageContentEmbedding, embedding: list[float]) -> None:
    job.status = "done"
    job.embedding = embedding
    job.processed_at = timezone.now()
    job.save(update_fields=["status", "embedding", "processed_at"])


def fail_content_embedding_job(job: PageContentEmbedding, error: str) -> None:
    job.status = "failed"
    job.error = error
    job.processed_at = timezone.now()
    job.save(update_fields=["status", "error", "processed_at"])


def reset_embeddings() -> dict:
    """Clear all stored embeddings and mark jobs pending for a full re-embed."""
    counts = {}
    counts["summary"] = PageSummaryEmbedding.objects.update(
        status="pending", embedding=None, error=None
    )
    counts["content"] = PageContentEmbedding.objects.update(
        status="pending", embedding=None, error=None
    )
    return counts


# --- Read helpers -----------------------------------------------------------

def get_page_ocr_text(page_id: int) -> str | None:
    return Page.objects.filter(id=page_id).values_list("ocr_text", flat=True).first()


def get_page_summary(page_id: int) -> str | None:
    return (
        PageMetadata.objects.filter(page_id=page_id, status="done")
        .values_list("summary", flat=True)
        .first()
    )


# --- Export -----------------------------------------------------------------

def export_all_json() -> list[dict]:
    """Export all journals with their pages' OCR content."""
    result = []
    for j in Journal.objects.order_by("filename"):
        pages = j.pages.order_by("page_number")
        result.append(
            {
                "filename": j.filename,
                "file_path": j.file_path,
                "page_count": j.page_count,
                "indexed_at": j.indexed_at.isoformat() if j.indexed_at else None,
                "pages": [
                    {
                        "page_number": p.page_number,
                        "status": p.status,
                        "ocr_text": p.ocr_text,
                        "ocr_provider": p.ocr_provider,
                        "ocr_model": p.ocr_model,
                        "processed_at": p.processed_at.isoformat() if p.processed_at else None,
                    }
                    for p in pages
                ],
            }
        )
    return result
