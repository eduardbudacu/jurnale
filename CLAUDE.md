# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jurnale is a Python 3.12 **Django 6** application that digitizes scanned journal PDFs. It extracts pages as images, runs OCR (OpenAI GPT-4o), extracts metadata and embeddings (Ollama/OpenAI), and serves a Django web dashboard for browsing results. PostgreSQL + pgvector is the backing store, using `SKIP LOCKED` for work queue semantics. (Migrated from Flask + raw psycopg — see `MIGRATION.md`.)

## Architecture

Pipeline stages run as independent workers (Django management commands) sharing a PostgreSQL queue:

```
PDFs → index → ocr_worker (OpenAI) → metadata_worker (Ollama) → embeddings_worker / content_embeddings_worker
```

- `jurnale/` — Django project (`settings.py`, `urls.py`, `wsgi.py`/`asgi.py`)
- `journal/` — the app
  - `models.py` — ORM mapped onto the legacy tables (PKs are `AutoField`; pgvector `VectorField(3072)`)
  - `views.py` — dashboard views (journals, pages, tags, wordcloud, embeddings, search, ask, image); vector similarity uses raw SQL via `django.db.connection`
  - `urls.py` — same URL paths as the old Flask app
  - `admin.py` — admin registrations (`/admin/`)
  - `migrations/0001_initial.py` — enables the `vector` extension, then the tables
  - `management/commands/` — one file per CLI subcommand
  - `services/` — business logic: `queue.py` (ORM claim/complete/fail + enqueue), `indexer.py`, `worker.py`, `metadata_worker.py`, `embeddings_worker.py`, `content_embeddings_worker.py`, `embeddings.py`, `ocr/` (pluggable provider: `base.py` + `openai.py`)
  - `templates/journal/`, `static/journal/`

## Commands

All commands run via `python manage.py <command>` (or `docker compose run --rm web python manage.py <command>`):

| Command | Purpose |
|---|---|
| `index` | Scan `data_pdf/`, extract pages, populate DB |
| `ocr_worker` | Run OCR on pending pages (exits when queue empty) |
| `metadata_enqueue` | Create metadata jobs for OCR-completed pages |
| `metadata_worker -n N` | Run N metadata extraction threads |
| `embeddings_enqueue` | Create summary-embedding jobs for pages with summaries |
| `embeddings_worker -n N` | Run N summary-embedding threads |
| `content_embeddings_enqueue` / `content_embeddings_worker -n N` | Content (OCR-text) embeddings |
| `embeddings_reset` | Clear all embeddings and mark pending (after model change) |
| `status` | Show pipeline progress counts |
| `enqueue` | Reset failed/processing pages to pending |
| `export_json -o FILE` | Export OCR content to JSON |
| `runserver` / gunicorn | Dev / prod dashboard (port 8080) |

## Docker

```bash
docker compose up -d --build db web          # db + dashboard (migrates on startup)
docker compose run --rm web python manage.py status
docker compose --profile pipeline up ...     # optional worker services
```

Dashboard on 8081, PostgreSQL on 5432, optional ByteBase GUI on 8099 (`--profile tools`). See `DEPLOYMENT.md`.

## Local Development (without Docker)

```bash
pip install -r requirements.txt
cp .env.example .env   # set DJANGO_SECRET_KEY, DATABASE_URL (localhost), OPENAI_API_KEY
python manage.py migrate          # add --fake-initial when adopting an existing DB
python manage.py runserver 8080
```

## Key Patterns

- **Queue processing**: Workers claim work with `select_for_update(skip_locked=True)` inside `transaction.atomic()` (see `services/queue.py`). Each table (`pages`, `page_metadata`, `page_summary_embeddings`, `page_content_embeddings`) has a `status` column (pending/processing/done/failed).
- **Schema**: Managed by Django migrations. On an existing populated DB use `migrate --fake-initial` (the container entrypoint does this automatically) so legacy data is adopted without modification.
- **OCR providers**: Registry in `services/ocr/__init__.py`, configured via `OCR_PROVIDER` env var. Currently only OpenAI.
- **Metadata/Embeddings**: Ollama (local LLM) or OpenAI via HTTP. Models via `METADATA_MODEL`, `EMBEDDING_MODEL`/`OPENAI_EMBEDDING_MODEL`. Query and stored embeddings must share a provider+model (routed through `services/embeddings.embed_text`).
- **No automated test suite or linter** configured currently.

## Database

Six tables: `journals`, `pages`, `page_metadata`, `page_metadata_tags`, `page_summary_embeddings`, `page_content_embeddings`, plus Django's contrib tables (`auth_*`, `django_*`). Embedding columns are `vector(3072)` (text-embedding-3-large); exact `<=>` scan is used (pgvector indexes cap at 2000 dims).
