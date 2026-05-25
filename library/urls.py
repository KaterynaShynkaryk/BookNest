from django.urls import path
from .views import test_page
from .views import register

urlpatterns = [
    path("test/", test_page, name="test_page"),
    path('auth/register/', register, name='register'),
]