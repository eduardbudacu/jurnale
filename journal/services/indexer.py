import os
from pathlib import Path

import fitz  # PyMuPDF
from django.utils import timezone

from journal.models import Journal, Page

PDF_DIR = Path(os.environ.get("PDF_DIR", "/app/data_pdf"))
IMG_DIR = Path(os.environ.get("IMG_DIR", "/app/data_img"))
DPI = int(os.environ.get("EXTRACT_DPI", "200"))


def extract_pages(pdf_path: Path, out_dir: Path) -> int:
    """Extract each page of a PDF as a PNG image. Returns page count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    zoom = DPI / 72
    mat = fitz.Matrix(zoom, zoom)

    for i, page in enumerate(doc, start=1):
        out_file = out_dir / f"page-{i:03d}.png"
        if out_file.exists() and out_file.stat().st_size > 0:
            continue
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        out_file.write_bytes(png_bytes)
        print(f"  Extracted page {i}/{page_count}")

    doc.close()
    return page_count


def index_all():
    """Scan PDF_DIR, extract pages, populate database."""
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {PDF_DIR}")

    for pdf_path in pdf_files:
        filename = pdf_path.name
        stem = pdf_path.stem
        page_dir = IMG_DIR / f"{stem}_pages"

        print(f"\nIndexing: {filename}")
        page_count = extract_pages(pdf_path, page_dir)
        print(f"  {page_count} pages")

        journal, _ = Journal.objects.update_or_create(
            filename=filename,
            defaults={
                "file_path": str(pdf_path),
                "page_count": page_count,
                "indexed_at": timezone.now(),
            },
        )
        for page_num in range(1, page_count + 1):
            image_path = str(page_dir / f"page-{page_num:03d}.png")
            Page.objects.update_or_create(
                journal=journal,
                page_number=page_num,
                defaults={"image_path": image_path},
            )

    print("\nIndexing complete.")
