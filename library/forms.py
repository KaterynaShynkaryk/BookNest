from django import forms

from .models import Book, Shelf


class BookForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].help_text = "Обери один із готових статусів читання."
        shelves_field = self.fields["shelves"]

        if user is not None:
            shelves_field.queryset = Shelf.objects.filter(user=user)
        else:
            shelves_field.queryset = Shelf.objects.none()

        shelves_field.required = False
        shelves_field.help_text = "Полички — окрема категоризація книг, незалежна від статусу читання."
        
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