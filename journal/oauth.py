"""OAuth pieces the MCP server needs on top of django-oauth-toolkit.

Anyone can register a client (Claude Code does so on first connect), so the
registration endpoint only accepts what a local MCP client needs. A registered
client still gets nothing until a logged-in user approves it.
"""
import json
from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_not_required
from django.http import Http404
from django.views.decorators.csrf import csrf_exempt

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
ALLOWED_GRANT_TYPES = {"authorization_code", "refresh_token"}


def _is_loopback_redirect(uri) -> bool:
    if not isinstance(uri, str):
        return False
    try:
        parts = urlsplit(uri)
        return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS
    except ValueError:
        return False


class LocalClientRegistrationPermission:
    """Allow open registration only for loopback, authorization-code clients."""

    def has_permission(self, request) -> bool:
        try:
            data = json.loads(request.body)
        except ValueError:
            return False
        if not isinstance(data, dict):
            return False

        redirect_uris = data.get("redirect_uris")
        if not isinstance(redirect_uris, list) or not redirect_uris:
            return False
        if not all(_is_loopback_redirect(uri) for uri in redirect_uris):
            return False

        grant_types = data.get("grant_types", ["authorization_code"])
        if not isinstance(grant_types, list):
            return False
        return all(g in ALLOWED_GRANT_TYPES for g in grant_types)


@csrf_exempt
@login_not_required
def client_management_disabled(request, client_id):
    """Replace RFC 7592 updates, which would bypass the registration rules."""
    raise Http404
