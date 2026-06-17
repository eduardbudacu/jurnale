from django.core.management.base import BaseCommand

from journal.services.indexer import index_all


class Command(BaseCommand):
    help = "Scan PDFs, extract pages, populate database"

    def handle(self, *args, **options):
        index_all()
