from django.core.management.base import BaseCommand
from django.db.models import Count

from journal.models import Journal, Page


class Command(BaseCommand):
    help = "Show pipeline status counts"

    def handle(self, *args, **options):
        self.stdout.write(f"Journals: {Journal.objects.count()}")
        rows = (
            Page.objects.values("status").annotate(cnt=Count("id")).order_by("status")
        )
        for r in rows:
            self.stdout.write(f"  Pages {r['status']}: {r['cnt']}")
