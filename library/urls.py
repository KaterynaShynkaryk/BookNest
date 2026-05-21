from django.urls import path
from .views import test_page

urlpatterns = [
    path("test/", test_page, name="test_page"),
]