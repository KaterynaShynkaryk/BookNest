from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    book_create,
    book_delete,
    book_detail,
    book_list,
    book_update,
    register,
    test_page,
)

urlpatterns = [
    path("", book_list, name="book_list"),
    path("books/", book_list, name="book_list"),
    path("books/add/", book_create, name="book_create"),
    path("books/<int:pk>/", book_detail, name="book_detail"),
    path("books/<int:pk>/edit/", book_update, name="book_update"),
    path("books/<int:pk>/delete/", book_delete, name="book_delete"),
    path("test/", test_page, name="test_page"),
    path("register/", register, name="register"),
    path("auth/register/", register, name="auth_register"),
    path("auth/login/", auth_views.LoginView.as_view(), name="login"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="logout"),
]