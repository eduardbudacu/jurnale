# Deployment (Docker)

The stack is one image (`web` = Django + gunicorn + WhiteNoise) plus a
PostgreSQL/pgvector database. Pipeline workers run the same image with a
different command.

## 1. Configure

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `DJANGO_SECRET_KEY` — a long random string
  (`python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- `DJANGO_ALLOWED_HOSTS` — your domain(s), e.g. `jurnale.example.com`
- `OPENAI_API_KEY` — for OCR, embeddings, and the `/ask` answer synthesis
- `POSTGRES_PASSWORD` / `DATABASE_URL` — change the password for anything
  beyond local use

Behind HTTPS, also set `DJANGO_DEBUG=0`, `DJANGO_SECURE_PROXY=1`,
`DJANGO_SECURE_COOKIES=1`, and `DJANGO_CSRF_TRUSTED_ORIGINS=https://your.domain`.

## 2. Build & start the dashboard

```bash
docker compose up -d --build db web
```

- `db` comes up first (compose waits for its healthcheck).
- `web` runs `migrate --fake-initial` on startup (safe on a fresh **or** an
  already-populated database — see MIGRATION.md), then serves gunicorn.
- Dashboard: **http://localhost:8081**

Create an admin user (optional, enables `/admin/`):

```bash
docker compose run --rm web python manage.py createsuperuser
```

## 3. Run the pipeline

Drop journal PDFs into `./data_pdf/` (bind-mounted into the container), then run
the stages. Each stage drains its queue and exits.

```bash
# 1. Extract pages from PDFs and populate the DB
docker compose run --rm web python manage.py index

# 2. OCR pending pages (OpenAI)
docker compose run --rm web python manage.py ocr_worker

# 3. Metadata (date / summary / tags) — needs Ollama reachable via OLLAMA_URL
docker compose run --rm web python manage.py metadata_enqueue
docker compose run --rm web python manage.py metadata_worker -n 2

# 4. Embeddings (for /search, /embeddings, /ask)
docker compose run --rm web python manage.py embeddings_enqueue
docker compose run --rm web python manage.py embeddings_worker -n 2
docker compose run --rm web python manage.py content_embeddings_enqueue
docker compose run --rm web python manage.py content_embeddings_worker -n 2

# Progress at any time
docker compose run --rm web python manage.py status
```

Alternatively, bring workers up as services (they exit when their queue drains):

```bash
docker compose --profile pipeline up ocr-worker metadata-worker \
  embeddings-worker content-embeddings-worker
```

> Note: `metadata_worker` and Ollama-based embeddings call `OLLAMA_URL`. From a
> container, a host Ollama is reachable at `http://host.docker.internal:11434`.

## 4. Operate

```bash
docker compose logs -f web              # tail logs
docker compose up -d --build web        # redeploy after code changes
docker compose down                     # stop (keeps the pgdata volume)
docker compose run --rm web python manage.py export_json -o /app/data_img/export.json
```

### Optional DB GUI

```bash
docker compose --profile tools up -d dbhub   # http://localhost:8099
```

## Backups

All durable state is the Postgres volume `pgdata` plus `./data_img` (page PNGs).

```bash
# Database dump
docker compose exec db pg_dump -U jurnale jurnale > backup_$(date +%F).sql
# Restore
cat backup.sql | docker compose exec -T db psql -U jurnale -d jurnale
```

## Production notes

- Static files are compressed and baked into the image at build
  (`collectstatic`) and served by WhiteNoise — no separate nginx/static volume
  needed. Front it with a TLS-terminating reverse proxy (Caddy/nginx/Traefik).
- Scale gunicorn with `--workers` (Dockerfile `CMD`); rule of thumb
  `2 × CPU + 1`.
- `web` runs as a non-root user inside the image.
- pgvector indexes (hnsw/ivfflat) are capped at 2000 dims; the 3072-dim columns
  use exact scan (`<=>`), which is fine for this dataset size.

## Local development (no Docker)

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env                                # set DATABASE_URL to localhost
python manage.py migrate           # add --fake-initial if adopting an existing DB
python manage.py runserver 8080    # http://localhost:8080
```
