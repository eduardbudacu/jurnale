from django.core.management.base import BaseCommand

from journal.services.metadata_worker import run_metadata_workers


class Command(BaseCommand):
    help = "Run metadata extraction workers (Ollama)"

    def add_arguments(self, parser):
        parser.add_argument(
            "-n", "--workers", type=int, default=2,
            help="Number of worker threads (default: 2)",
        )

    def handle(self, *args, **options):
        n = options["workers"]
        self.stdout.write(f"Starting {n} metadata worker(s)...")
        run_metadata_workers(n)
