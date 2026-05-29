from django import forms
from .models import Book


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "genre",
            "publisher",
            "status",
            "is_favorite",
            "rating",
            "start_date",
            "finish_date",
            "description",
            "shelves",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "finish_date": forms.DateInput(attrs={"type": "date"}),
        }