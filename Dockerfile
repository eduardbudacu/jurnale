FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=jurnale.settings

WORKDIR /app

# psycopg[binary] and PyMuPDF ship self-contained wheels, so no apt build deps
# are needed on slim. (libpq is bundled with psycopg-binary.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bake compressed static assets into the image (collectstatic needs no DB).
RUN python manage.py collectstatic --noinput

# Run as a non-root user.
RUN chmod +x /app/entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app
USER appuser

EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "jurnale.wsgi:application", \
     "--bind", "0.0.0.0:8080", "--workers", "3", "--timeout", "120"]
