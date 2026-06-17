# Migration: Flask + psycopg → Django 6

This document is the plan that was executed and the reference for what changed.

## Goal

Replace the Flask dashboard and the hand-rolled `psycopg` data layer with a
Django 6 project, **without changing the PostgreSQL + pgvector schema**, so an
existing populated database is adopted as-is.

## Outcome

| Concern | Before | After |
|---|---|---|
| Web framework | Flask (`src/pipeline/dashboard.py`) | Django 6 (`jurnale/`, `journal/views.py`) |
| Data access | raw SQL in `src/pipeline/db.py` | Django ORM (`journal/models.py`, `journal/services/queue.py`) |
| Vector search | raw SQL | raw SQL via `django.db.connection` (pgvector `<=>`) — unchanged semantics |
| Schema management | `ensure_schema()` DDL string | Django migrations (`journal/migrations/0001_initial.py`) |
| CLI | `python -m pipeline <cmd>` | `python manage.py <cmd>` |
| Work queue | `SELECT … FOR UPDATE SKIP LOCKED` | ORM `select_for_update(skip_locked=True)` (same lock semantics) |
| Templates | Jinja2 | Django Template Language |
| Config | ad-hoc `os.environ` | `jurnale/settings.py` + env (`dj-database-url`) |
| Static / serving | `app.run()` | gunicorn + WhiteNoise |

The legacy `src/pipeline/` tree was removed.

## Schema compatibility (how existing data is preserved)

Models pin the legacy table and column names and use plain `AutoField` PKs
(`DEFAULT_AUTO_FIELD = "django.db.models.AutoField"`) to match the original
`SERIAL` columns. Foreign keys land on the same `journal_id` / `page_id` /
`page_metadata_id` columns Django would pick anyway.

For a **new** database, `migrate` creates everything (the `vector` extension is
enabled first via `pgvector.django.VectorExtension`).

For an **existing** database, run `migrate --fake-initial`: Django sees the six
`journal` tables already exist and marks `0001_initial` as applied **without
touching the data**, then creates only the Django contrib tables
(`auth_*`, `django_*`). The container entrypoint always uses `--fake-initial`,
so the same image is safe on both fresh and populated databases.

## Command mapping

| Old | New |
|---|---|
| `python -m pipeline index` | `python manage.py index` |
| `python -m pipeline enqueue` | `python manage.py enqueue` |
| `python -m pipeline worker` | `python manage.py ocr_worker` |
| `python -m pipeline status` | `python manage.py status` |
| `python -m pipeline dashboard` | `gunicorn jurnale.wsgi` (prod) / `python manage.py runserver` (dev) |
| `python -m pipeline metadata-enqueue` | `python manage.py metadata_enqueue` |
| `python -m pipeline metadata-worker -n N` | `python manage.py metadata_worker -n N` |
| `python -m pipeline embeddings-enqueue` | `python manage.py embeddings_enqueue` |
| `python -m pipeline embeddings-worker -n N` | `python manage.py embeddings_worker -n N` |
| `python -m pipeline embeddings-reset` | `python manage.py embeddings_reset` |
| `python -m pipeline content-embeddings-enqueue` | `python manage.py content_embeddings_enqueue` |
| `python -m pipeline content-embeddings-worker -n N` | `python manage.py content_embeddings_worker -n N` |
| `python -m pipeline export -o FILE` | `python manage.py export_json -o FILE` |

> Management-command names use underscores (Python module names can't contain
> hyphens). All dashboard URLs are unchanged.

## What's new

- **Django admin** at `/admin/` for browsing journals, pages, metadata, tags,
  and embeddings. Create a user with `python manage.py createsuperuser`.

## Validation performed

- `manage.py check` clean; `makemigrations --check` reports no drift.
- Against a real `pgvector/pgvector:pg15` container: fresh `migrate`; ORM CRUD;
  `select_for_update(skip_locked=True)` claim path; 3072-dim vectors written via
  `VectorField`; every dashboard route returns 200; `collectstatic` + WhiteNoise
  compression.
- **`migrate --fake-initial` against a database pre-loaded with the original
  schema + data**: `journal.0001_initial` was FAKED and the pre-existing rows
  were served unchanged through the new ORM and views.

## ⚠️ Security follow-up

The committed `.env` contains a live `OPENAI_API_KEY`. **Rotate it** and keep it
out of version control — `.env` is now in `.gitignore` and `.dockerignore`.
Also set a real `DJANGO_SECRET_KEY` (don't ship the default).
