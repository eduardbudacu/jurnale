from django.core.management.base import BaseCommand

from journal.services.embeddings_worker import run_embedding_workers


class Command(BaseCommand):
    help = "Run summary embedding workers"

    def add_arguments(self, parser):
        parser.add_argument(
            "-n", "--workers", type=int, default=2,
            help="Number of worker threads (default: 2)",
        )

    def handle(self, *args, **options):
        n = options["workers"]
        self.stdout.write(f"Starting {n} embedding worker(s)...")
        run_embedding_workers(n)
