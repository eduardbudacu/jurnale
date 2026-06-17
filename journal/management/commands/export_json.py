import json

from django.core.management.base import BaseCommand

from journal.services import queue


class Command(BaseCommand):
    help = "Export all OCR content to JSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "-o", "--output", default="export.json",
            help="Output file path (default: export.json)",
        )

    def handle(self, *args, **options):
        data = queue.export_all_json()
        output_path = options["output"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        total_pages = sum(len(j["pages"]) for j in data)
        self.stdout.write(
            f"Exported {len(data)} journals ({total_pages} pages) to {output_path}"
        )
