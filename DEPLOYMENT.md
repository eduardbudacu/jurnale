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

The dashboard requires login. Create the first account (a superuser can also
manage further users at `/admin/`):

```bash
docker compose run --rm web python manage.py createsuperuser
```

Alternatively set `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` in
`.env` and the `web` container creates it on startup if it does not exist.
Additional users: `/admin/` → Users → Add (no self-service sign-up). Users change
their own password via the **Password** link in the header.

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

## 5. Expose the MCP server (optional)

The `mcp` service lets Claude Code search the journals through
`https://<your-domain>/mcp`, using a browser login against the dashboard's users.
It needs HTTPS on a domain that the machine running Claude Code can reach.

### Secure the host first

The MCP login makes this stack reachable from outside. Before exposing it:

- Set a real `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS` to your domain.
- Set `DJANGO_DEBUG=0`, `DJANGO_SECURE_PROXY=1`, `DJANGO_SECURE_COOKIES=1`, and
  `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-domain>`.
- Change `POSTGRES_PASSWORD` and don't expose port 5432 to the internet. Compose
  publishes it by default; firewall it, or set `POSTGRES_PORT=127.0.0.1:5432`.
- Keep the `tools` profile (`dbhub`) off, and don't expose port 8099.
- Use strong passwords. Every dashboard user who approves a client can search
  all journals, because pages have no owner.

### Configure and start

In `.env`:

```bash
MCP_PUBLIC_URL=https://<your-domain>/mcp
```

```bash
docker compose up -d --build db web
docker compose --profile mcp up -d --build mcp
```

### Route the paths

On one domain, send `/mcp` and the protected-resource metadata to `mcp` (port
8091 on the host) and everything else to `web` (port 8081). The proxy must
forward the original `Host` header, or `mcp` answers `421`.

Caddy:

```
<your-domain> {
    @mcp path /mcp /.well-known/oauth-protected-resource /.well-known/oauth-protected-resource/*
    reverse_proxy @mcp localhost:8091
    reverse_proxy localhost:8081
}
```

nginx (inside the TLS `server` block):

```nginx
location ~ ^/(mcp$|\.well-known/oauth-protected-resource) {
    proxy_pass http://localhost:8091;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location / {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Connect Claude Code

```bash
claude mcp add --transport http jurnale https://<your-domain>/mcp
```

Then open `/mcp` in a `claude` terminal and authenticate, or run
`claude mcp login jurnale`. A browser opens on the dashboard login, then on an
approval page. Afterwards Claude Code has one tool, `search_pages`.

To use it from claude.ai or the desktop app instead, add a custom connector with
the same URL and leave the OAuth client fields empty. Client registration only
accepts localhost redirects and Claude's hosted callback.

Each search sends the query to the embedding provider, and the results enter your
Claude session.

### Operate

- Revoke access: delete the application or its tokens at `/admin/` under
  Django OAuth Toolkit. Access tokens last 1 hour, refresh tokens 30 days.
- Clear old tokens periodically:
  `docker compose run --rm web python manage.py cleartokens`
- Failed logins lock a username + IP pair for an hour after 10 attempts
  (`AXES_FAILURE_LIMIT`). Behind a proxy that amounts to locking the username.
  Unlock with `docker compose run --rm web python manage.py axes_reset`.
- Leave `MCP_PUBLIC_URL` empty to turn the OAuth routes off.

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
