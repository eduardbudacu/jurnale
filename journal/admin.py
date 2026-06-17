from django.contrib import admin

from .models import (
    Journal,
    Page,
    PageContentEmbedding,
    PageMetadata,
    PageMetadataTag,
    PageSummaryEmbedding,
)


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "page_count", "indexed_at")
    search_fields = ("filename",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("id", "journal", "page_number", "status", "ocr_provider", "processed_at")
    list_filter = ("status", "ocr_provider")
    search_fields = ("ocr_text",)
    raw_id_fields = ("journal",)


@admin.register(PageMetadata)
class PageMetadataAdmin(admin.ModelAdmin):
    list_display = ("id", "page", "status", "date_value", "processed_at")
    list_filter = ("status",)
    raw_id_fields = ("page",)


@admin.register(PageMetadataTag)
class PageMetadataTagAdmin(admin.ModelAdmin):
    list_display = ("id", "page_metadata", "tag")
    search_fields = ("tag",)


@admin.register(PageSummaryEmbedding)
class PageSummaryEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "page", "status", "processed_at")
    list_filter = ("status",)
    raw_id_fields = ("page",)


@admin.register(PageContentEmbedding)
class PageContentEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "page", "status", "processed_at")
    list_filter = ("status",)
    raw_id_fields = ("page",)
