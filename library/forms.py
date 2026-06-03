from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Book, Shelf


class BootstrapFormMixin:
    """Add Bootstrap-friendly classes without overriding Django validation."""

    def apply_bootstrap_styles(self):
        for field in self.fields.values():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class BookForm(BootstrapFormMixin, forms.ModelForm):
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
        self.apply_bootstrap_styles()
        self.fields["description"].widget.attrs.setdefault("rows", 4)

    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "genre",
            "publisher",
            "published_year",
            "cover_image",
            "status",
            "is_favorite",
            "rating",
            "start_date",
            "finish_date",
            "description",
            "shelves",
        ]
        labels = {
            "title": "Назва книги",
            "author": "Автор",
            "genre": "Жанр",
            "publisher": "Видавництво",
            "published_year": "Рік видання",
            "cover_image": "Фото обкладинки",
            "status": "Статус читання",
            "is_favorite": "Додати в обране",
            "rating": "Оцінка",
            "start_date": "Дата початку",
            "finish_date": "Дата завершення",
            "description": "Опис або нотатка",
            "shelves": "Полички",
        }
        help_texts = {
            "published_year": "За бажанням: рік видання або перевидання.",
            "cover_image": "JPG, PNG, WEBP або GIF. Якщо не додати фото, покажемо мінімалістичну обкладинку.",
            "rating": "Вкажи число від 1 до 5, якщо вже маєш оцінку.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Наприклад, Місто"}),
            "author": forms.TextInput(attrs={"placeholder": "Наприклад, Валер'ян Підмогильний"}),
            "genre": forms.TextInput(attrs={"placeholder": "Роман, нон-фікшн, фантастика..."}),
            "publisher": forms.TextInput(attrs={"placeholder": "Назва видавництва"}),
            "published_year": forms.NumberInput(attrs={"min": 0, "placeholder": "Наприклад, 2024"}),
            "cover_image": forms.FileInput(attrs={"accept": "image/*"}),
            "rating": forms.NumberInput(attrs={"min": 1, "max": 5, "placeholder": "1–5"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "finish_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"placeholder": "Коротко про книгу, настрій або очікування"}),
        }


class UkrainianAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(label="Ім'я користувача")
    password = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_styles()
        self.fields["username"].widget.attrs.setdefault("placeholder", "your_name")
        self.fields["password"].widget.attrs.setdefault("placeholder", "••••••••")


class UkrainianUserCreationForm(BootstrapFormMixin, UserCreationForm):
    username = forms.CharField(label="Ім'я користувача")
    email = forms.EmailField(label="Email", required=False)
    password1 = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Підтвердження пароля",
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_styles()
        self.fields["username"].widget.attrs.setdefault("placeholder", "your_name")
        self.fields["email"].widget.attrs.setdefault("placeholder", "you@example.com")
        self.fields["password1"].widget.attrs.setdefault("placeholder", "••••••••")
        self.fields["password2"].widget.attrs.setdefault("placeholder", "••••••••")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user