from django.urls import path
from .views import register, book_list, book_create

urlpatterns = [
    path("auth/register/", register, name="register"),
    path("", book_list, name="book_list"),
    path("books/", book_list, name="book_list"),
    path("books/add/", book_create, name="book_create"),
]