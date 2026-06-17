from django.core.management.base import BaseCommand

from journal.services import queue


class Command(BaseCommand):
    help = "Reset failed/processing pages back to pending"

    def handle(self, *args, **options):
        count = queue.reset_pending()
        self.stdout.write(f"Reset {count} pages back to pending.")
