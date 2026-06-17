from django.core.management.base import BaseCommand

from journal.services import queue


class Command(BaseCommand):
    help = "Create content embedding jobs for OCR-done pages"

    def handle(self, *args, **options):
        count = queue.enqueue_content_embedding_jobs()
        self.stdout.write(f"Enqueued {count} content embedding jobs.")
