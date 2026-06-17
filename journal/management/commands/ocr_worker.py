from django.core.management.base import BaseCommand

from journal.services.worker import run_worker


class Command(BaseCommand):
    help = "Run OCR worker (processes pending pages, exits when queue empty)"

    def handle(self, *args, **options):
        run_worker()
