from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Book, Note, Shelf


def format_star_rating(value):
    if value in (None, ""):
        return "☆☆☆☆☆"

    rating = int(value)
    return "★" * rating + "☆" * (5 - rating)


RATING_CHOICES = [(value, "★") for value in range(5, 0, -1)]
GENRE_SEPARATOR = ", "


def split_genres(value):
    return [genre.strip() for genre in value.replace(";", ",").split(",") if genre.strip()]


def normalize_genre_list(value):
    genres = []
    seen = set()

    for genre in split_genres(value):
        genre_key = genre.casefold()
        if genre_key not in seen:
            genres.append(genre)
            seen.add(genre_key)

    return GENRE_SEPARATOR.join(genres)


class BootstrapFormMixin:
    """Add Bootstrap-friendly classes without overriding Django validation."""

    def apply_bootstrap_styles(self):
        for field in self.fields.values():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs.setdefault("class", "checkbox-list")
            elif isinstance(widget, forms.RadioSelect):
                widget.attrs.setdefault("class", "rating-radio-list")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


def validate_reading_fields(form, cleaned_data):
    status = cleaned_data.get("status")
    rating = cleaned_data.get("rating")
    start_date = cleaned_data.get("start_date")
    finish_date = cleaned_data.get("finish_date")

    if status == Book.Status.WISHLIST and start_date:
        form.add_error("start_date", "Дату початку не можна вказувати для бажанки.")

    if status != Book.Status.COMPLETED:
        if rating is not None:
            form.add_error("rating", "Оцінку можна ставити тільки для прочитаних книг.")
        if finish_date:
            form.add_error("finish_date", "Дату завершення можна вказати тільки для прочитаних книг.")
    elif start_date and finish_date and finish_date < start_date:
        form.add_error("finish_date", "Дата завершення не може бути раніше дати початку.")

    return cleaned_data


class BookProgressForm(BootstrapFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Оцінка",
        choices=RATING_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Book
        fields = ["status", "is_favorite", "start_date", "finish_date", "rating"]
        labels = {
            "status": "Статус читання",
            "is_favorite": "Улюблена книга",
            "start_date": "Дата початку",
            "finish_date": "Дата завершення",
            "rating": "Оцінка",
        }
        help_texts = {
            "start_date": "Недоступно, коли статус книги — «Бажанка».",
            "finish_date": "Доступно, коли статус книги — «Прочитано».",
            "rating": "Оцінку можна ставити тільки для прочитаних книг.",
        }
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "finish_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].help_text = "Зміни статус прямо на сторінці книги."
        self.apply_bootstrap_styles()

    def clean(self):
        cleaned_data = super().clean()
        return validate_reading_fields(self, cleaned_data)


class BookForm(BootstrapFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Оцінка",
        choices=RATING_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["status"].help_text = "Обери один із статусів читання."
        shelves_field = self.fields["shelves"]
        shelves_field.widget = forms.CheckboxSelectMultiple()
        user_books = Book.objects.none()

        if user is not None:
            shelves_field.queryset = Shelf.objects.filter(user=user)
            user_books = Book.objects.filter(user=user)
        else:
            shelves_field.queryset = Shelf.objects.none()

        genre_options = []
        seen_genres = set()
        genre_values = (
            user_books.exclude(genre="")
            .order_by("genre")
            .values_list("genre", flat=True)
            .distinct()
        )
        for genre_value in genre_values:
            for genre in split_genres(genre_value):
                genre_key = genre.casefold()
                if genre_key not in seen_genres:
                    genre_options.append(genre)
                    seen_genres.add(genre_key)
        self.genre_options = genre_options
        self.publisher_options = list(
            user_books.exclude(publisher="")
            .order_by("publisher")
            .values_list("publisher", flat=True)
            .distinct()
        )
        self.series_options = list(
            user_books.exclude(series="")
            .order_by("series")
            .values_list("series", flat=True)
            .distinct()
        )

        self.shelf_options = list(shelves_field.queryset)
        if self.is_bound:
            shelf_field_name = self.add_prefix("shelves")
            if hasattr(self.data, "getlist"):
                selected_shelves = self.data.getlist(shelf_field_name)
            else:
                selected_shelves = self.data.get(shelf_field_name, [])
                if isinstance(selected_shelves, str):
                    selected_shelves = [selected_shelves]
            self.selected_shelf_ids = set(selected_shelves)
        elif self.instance.pk:
            self.selected_shelf_ids = set(
                str(pk) for pk in self.instance.shelves.values_list("pk", flat=True)
            )
        else:
            self.selected_shelf_ids = set()

        shelves_field.required = False
        shelves_field.help_text = "Позначте потрібні полички. Щоб прибрати книгу з поличок, зніміть усі позначки."
        self.apply_bootstrap_styles()
        self.fields["description"].widget.attrs.setdefault("rows", 4)

    def clean_genre(self):
        return normalize_genre_list(self.cleaned_data.get("genre", ""))

    def clean_shelves(self):
        shelves = self.cleaned_data.get("shelves")
        if not shelves:
            return shelves

        if self.user is None or shelves.exclude(user=self.user).exists():
            raise forms.ValidationError("Можна обирати тільки власні полички.")

        return shelves

    def clean(self):
        cleaned_data = super().clean()
        return validate_reading_fields(self, cleaned_data)


    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "genre",
            "publisher",
            "series",
            "published_year",
            "cover_image",
            "cover_url",
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
            "series": "Серія",
            "published_year": "Рік видання",
            "cover_image": "Обкладинка",
            "cover_url": "Посилання",
            "status": "Статус читання",
            "is_favorite": "Додати в обране",
            "rating": "Оцінка",
            "start_date": "Дата початку",
            "finish_date": "Дата завершення",
            "description": "Опис або нотатка",
            "shelves": "Полички",
        }
        help_texts = {
            "genre": "Можна додати кілька жанрів через кому, наприклад: фентезі, роман.",
            "published_year": "За бажанням: рік видання або перевидання.",
            "cover_image": "Додай обкладинку файлом або посиланням. Якщо заповнити обидва варіанти, буде показано файл.",
            "cover_url": "Встав пряме посилання на зображення.",
            "finish_date": "Доступно, коли статус книги — «Прочитано».",
            "rating": "Оцінку можна ставити тільки для прочитаних книг.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Наприклад, Місто"}),
            "author": forms.TextInput(attrs={"placeholder": "Наприклад, Валер'ян Підмогильний"}),
            "genre": forms.TextInput(attrs={"placeholder": "Фентезі, роман, нон-фікшн..."}),
            "publisher": forms.TextInput(attrs={"placeholder": "Назва видавництва"}),
            "series": forms.TextInput(attrs={"placeholder": "Назва серії книг"}),
            "published_year": forms.NumberInput(attrs={"min": 0, "placeholder": "Наприклад, 2024"}),
            "cover_image": forms.FileInput(attrs={"accept": "image/*"}),
            "cover_url": forms.URLInput(attrs={"placeholder": "https://example.com/cover.jpg"}),
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "finish_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"placeholder": "Коротко про книгу, настрій або очікування"}),
        }

class ShelfForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Shelf
        fields = ["name"]
        labels = {"name": "Назва полички"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Наприклад, Фентезі або Купити"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.apply_bootstrap_styles()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Введіть назву полички.")

        if self.user is not None:
            duplicate_shelves = Shelf.objects.filter(user=self.user)
            if self.instance.pk:
                duplicate_shelves = duplicate_shelves.exclude(pk=self.instance.pk)
            if any(shelf.name.casefold() == name.casefold() for shelf in duplicate_shelves):
                raise forms.ValidationError("Поличка з такою назвою вже існує.")

        return name

    
class NoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Note
        fields = ["book", "title", "content", "page_number"]
        labels = {
            "book": "Книга",
            "title": "Заголовок",
            "content": "Нотатка",
            "page_number": "Сторінка",
        }
        help_texts = {
            "book": "Необов’язково: залиш порожнім, якщо нотатка не стосується конкретної книги.",
            "page_number": "Необов’язково, якщо нотатка не прив’язана до сторінки.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Необов’язково"}),
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Запишіть думку, цитату або враження...",
                },
            ),
        }
    def __init__(self, *args, user=None, include_book=True, **kwargs):
        super().__init__(*args, **kwargs)

        if include_book:
            self.fields["book"].required = False
            self.fields["book"].queryset = (
                Book.objects.filter(user=user) if user is not None else Book.objects.none()
            )
            self.fields["book"].empty_label = "Без книги"
        else:
            self.fields.pop("book")

        self.apply_bootstrap_styles()


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