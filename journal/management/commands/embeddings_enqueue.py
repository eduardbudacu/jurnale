from django.core.management.base import BaseCommand

from journal.services import queue


class Command(BaseCommand):
    help = "Create embedding jobs for pages with summaries"

    def handle(self, *args, **options):
        count = queue.enqueue_embedding_jobs()
        self.stdout.write(f"Enqueued {count} embedding jobs.")
