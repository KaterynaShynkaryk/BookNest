from django.urls import path
from .views import (
    book_list,
    book_detail,
    book_create,
    book_update,
    book_delete,
    #register,
)

urlpatterns = [
    #path("auth/register/", register, name="register"),
    path("", book_list, name="book_list"),
    path("books/", book_list, name="book_list"),
    path("books/add/", book_create, name="book_create"),
    path("books/<int:pk>/", book_detail, name="book_detail"),
    path("books/<int:pk>/edit/", book_update, name="book_update"),
    path("books/<int:pk>/delete/", book_delete, name="book_delete"),
]