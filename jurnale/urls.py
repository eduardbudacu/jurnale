from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from oauth2_provider import views as oauth_views

from journal.oauth import client_management_disabled

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("journal.urls")),
]

# Only the OAuth endpoints the MCP server needs, not the toolkit's full URLconf.
if settings.MCP_PUBLIC_URL:
    oauth_urlpatterns = [
        path(
            ".well-known/oauth-authorization-server",
            oauth_views.OAuthServerMetadataView.as_view(),
            name="oauth-server-metadata",
        ),
        path("oauth/authorize/", oauth_views.AuthorizationView.as_view(), name="authorize"),
        path("oauth/token/", oauth_views.TokenView.as_view(), name="token"),
        path("oauth/revoke/", oauth_views.RevokeTokenView.as_view(), name="revoke-token"),
        path(
            "oauth/register/",
            oauth_views.DynamicClientRegistrationView.as_view(),
            name="dcr-register",
        ),
        path(
            "oauth/register/<str:client_id>/",
            client_management_disabled,
            name="dcr-register-management",
        ),
    ]
    urlpatterns.append(path("", include((oauth_urlpatterns, "oauth2_provider"))))
