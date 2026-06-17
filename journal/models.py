"""ORM models mapped onto the existing Jurnale schema.

Table and column names are pinned to the legacy names so an already-populated
database can be adopted with ``migrate --fake-initial``. Primary keys are plain
``AutoField`` (int4) to match the original ``SERIAL`` columns.
"""
from django.db import models
from django.utils import timezone
from pgvector.django import VectorField

EMBED_DIM = 3072  # text-embedding-3-large

STATUS_CHOICES = [
    ("pending", "pending"),
    ("processing", "processing"),
    ("done", "done"),
    ("failed", "failed"),
]


class Journal(models.Model):
    filename = models.TextField(unique=True)
    file_path = models.TextField()
    page_count = models.IntegerField(null=True, blank=True)
    indexed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "journals"
        ordering = ["filename"]

    def __str__(self):
        return self.filename


class Page(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="pages")
    page_number = models.IntegerField()
    image_path = models.TextField(null=True, blank=True)
    status = models.TextField(default="pending", db_index=True)
    ocr_text = models.TextField(null=True, blank=True)
    ocr_provider = models.TextField(null=True, blank=True)
    ocr_model = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "pages"
        ordering = ["journal_id", "page_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["journal", "page_number"], name="pages_journal_id_page_number_key"
            )
        ]

    def __str__(self):
        return f"{self.journal_id}/p{self.page_number}"


class PageMetadata(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name="metadata")
    status = models.TextField(default="pending", db_index=True)
    date_value = models.TextField(null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "page_metadata"

    def __str__(self):
        return f"metadata(page={self.page_id})"


class PageMetadataTag(models.Model):
    page_metadata = models.ForeignKey(
        PageMetadata, on_delete=models.CASCADE, related_name="tags"
    )
    tag = models.TextField(db_index=True)

    class Meta:
        db_table = "page_metadata_tags"

    def __str__(self):
        return self.tag


class PageSummaryEmbedding(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name="summary_embedding")
    status = models.TextField(default="pending", db_index=True)
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "page_summary_embeddings"

    def __str__(self):
        return f"summary_embedding(page={self.page_id})"


class PageContentEmbedding(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name="content_embedding")
    status = models.TextField(default="pending", db_index=True)
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "page_content_embeddings"

    def __str__(self):
        return f"content_embedding(page={self.page_id})"
