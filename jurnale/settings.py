"""Django settings for the Jurnale project.

Configuration is driven by environment variables (see .env.example) so the same
image runs locally and in Docker. PostgreSQL + pgvector is the backing store.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


# --- Core -------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", "0")
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "*") or ["*"]
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "journal",  # before oauth2_provider so its consent template wins
    "oauth2_provider",
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every view requires a logged-in user unless marked @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "jurnale.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "jurnale.wsgi.application"
ASGI_APPLICATION = "jurnale.asgi.application"

# --- Database ---------------------------------------------------------------
# Parsed from DATABASE_URL; psycopg (v3) is used automatically when installed.
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get(
            "DATABASE_URL", "postgresql://jurnale:jurnale@localhost:5432/jurnale"
        ),
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "600")),
    )
}

# Existing schema uses SERIAL (int4) primary keys; match it so Django ORM and
# the legacy tables line up exactly (enables migrate --fake-initial).
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# --- Authentication ---------------------------------------------------------
# The whole dashboard is private. Users are managed via /admin/ or
# `manage.py createsuperuser`; there is no self-service sign-up.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "index"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = int(os.environ.get("DJANGO_SESSION_AGE", str(60 * 60 * 24 * 14)))

# Lock a username + client IP pair after repeated failed logins. Behind a proxy
# REMOTE_ADDR is the proxy, so this effectively locks the username.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = int(os.environ.get("AXES_FAILURE_LIMIT", "10"))
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True

# --- MCP server + OAuth -------------------------------------------------------
# Public URL of the MCP endpoint, e.g. https://jurnale.example.com/mcp. The OAuth
# routes are only mounted when this is set (see jurnale/urls.py).
MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/")
_mcp_url = urlsplit(MCP_PUBLIC_URL)
MCP_ORIGIN = f"{_mcp_url.scheme}://{_mcp_url.netloc}" if MCP_PUBLIC_URL else ""
MCP_HOST = _mcp_url.netloc
MCP_SCOPE = "journal:read"

OAUTH2_PROVIDER = {
    "OIDC_ISS_ENDPOINT": MCP_ORIGIN,
    "SCOPES": {MCP_SCOPE: "Search and read all journal pages"},
    "DEFAULT_SCOPES": [MCP_SCOPE],
    "OAUTH2_RESPONSE_TYPES_SUPPORTED": ["code"],
    "OAUTH2_GRANT_TYPES_SUPPORTED": ["authorization_code", "refresh_token"],
    # "none" is how public clients like Claude Code authenticate (PKCE, no secret).
    "OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED": ["none", "client_secret_post", "client_secret_basic"],
    "ACCESS_TOKEN_EXPIRE_SECONDS": 60 * 60,
    "REFRESH_TOKEN_EXPIRE_SECONDS": 60 * 60 * 24 * 30,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "REFRESH_TOKEN_GRACE_PERIOD_SECONDS": 30,
    "PKCE_REQUIRED": True,
    # Claude Code registers a localhost callback on a random port.
    "ALLOW_LOCALHOST_LOOPBACK": True,
    "DCR_ENABLED": True,
    "DCR_REGISTRATION_PERMISSION_CLASSES": ("journal.oauth.LocalClientRegistrationPermission",),
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
}

# --- Password validation ----------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / time ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True  # matches TIMESTAMPTZ columns

# --- Static files -----------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --- Security (production) ---------------------------------------------------
# Behind a TLS-terminating proxy, set DJANGO_SECURE_PROXY=1.
if _env_bool("DJANGO_SECURE_PROXY", "0"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SESSION_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", "0")
    CSRF_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", "0")

# --- Logging ----------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
