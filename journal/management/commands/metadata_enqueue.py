from django.core.management.base import BaseCommand

from journal.services import queue


class Command(BaseCommand):
    help = "Create metadata extraction jobs for OCR-done pages"

    def handle(self, *args, **options):
        count = queue.enqueue_metadata_jobs()
        self.stdout.write(f"Enqueued {count} metadata jobs.")
