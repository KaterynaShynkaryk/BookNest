from django.urls import path
from .views import test_page, register

urlpatterns = [
    path("test/", test_page, name="test_page"),
    path("register/", register, name="register"),
    path("auth/register/", register),
]