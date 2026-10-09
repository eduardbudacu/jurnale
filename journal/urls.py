from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        "login",
        auth_views.LoginView.as_view(
            template_name="journal/login.html",
            redirect_authenticated_user=True,
            extra_context={"title": "Log in"},
        ),
        name="login",
    ),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),
    path("password", views.PasswordChangeView.as_view(), name="password_change"),
    path("", views.index, name="index"),
    path("journal/<int:journal_id>", views.journal_pages, name="journal_pages"),
    path("journal/<int:journal_id>/page/<int:page_number>", views.page_detail, name="page_detail"),
    path("tags", views.tags_view, name="tags"),
    path("wordcloud", views.wordcloud_view, name="wordcloud"),
    path("embeddings", views.embeddings_view, name="embeddings"),
    path("search", views.search_view, name="search"),
    path("ask", views.ask_view, name="ask"),
    path("image/<int:journal_id>/<int:page_number>", views.serve_image, name="serve_image"),
]
