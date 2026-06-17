from django.core.management.base import BaseCommand

from journal.services import queue


class Command(BaseCommand):
    help = "Clear all embeddings and mark pending (re-embed after model change)"

    def handle(self, *args, **options):
        counts = queue.reset_embeddings()
        self.stdout.write(
            f"Reset embeddings to pending: {counts['summary']} summary, "
            f"{counts['content']} content."
        )
