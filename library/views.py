import secrets

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Prefetch, Q
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import (
    BookForm,
    BookProgressForm,
    NoteForm,
    ShelfForm,
    UkrainianAuthenticationForm,
    UkrainianUserCreationForm,
    split_genres,
)
from .book_lookup import BookLookupError, import_book_from_url, search_books
from .models import Book, Note, Shelf
from .series_shelves import cleanup_empty_series_shelves, sync_book_series_shelf


def test_page(request):
    return render(request, "library/test.html")


def logout_view(request):
    logout(request)
    messages.success(request, "Ви вийшли з акаунту.")
    return redirect("login")


class UkrainianLoginView(LoginView):
    authentication_form = UkrainianAuthenticationForm

    def form_valid(self, form):
        messages.success(self.request, "Ви успішно увійшли.")
        return super().form_valid(form)


def register(request):
    if request.method == "POST":
        form = UkrainianUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Акаунт створено. Ласкаво просимо до BookNest!")
            return redirect("book_list")
    else:
        form = UkrainianUserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def get_safe_redirect_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
    ):
        return next_url

    return None


@login_required
def book_list(request):
    search_query = request.GET.get("q", "").strip()
    selected_statuses = request.GET.getlist("status")
    selected_genres = request.GET.getlist("genre")
    selected_publishers = list(request.GET.getlist("publisher"))
    favorite_only = request.GET.get("favorite") == "1"
    available_statuses = {status for status, label in Book.Status.choices}

    user_books = Book.objects.filter(user=request.user)
    genre_choices = []
    seen_genres = set()
    for genre_value in (
        user_books.exclude(genre="")
        .order_by("genre")
        .values_list("genre", flat=True)
        .distinct()
    ):
        for genre in split_genres(genre_value):
            genre_key = genre.casefold()
            if genre_key not in seen_genres:
                genre_choices.append(genre)
                seen_genres.add(genre_key)
    publisher_choices = list(
        user_books.exclude(publisher="")
        .order_by("publisher")
        .values_list("publisher", flat=True)
        .distinct()
    )
    books = user_books.prefetch_related("shelves")

    selected_statuses = [status for status in selected_statuses if status in available_statuses]
    if selected_statuses:
        books = books.filter(status__in=selected_statuses)

    selected_genres = [genre for genre in selected_genres if genre in genre_choices]
    if selected_genres:
        genre_query = Q()
        for genre in selected_genres:
            genre_query |= Q(genre__icontains=genre)
        books = books.filter(genre_query)

    selected_publishers = [publisher for publisher in selected_publishers if publisher in publisher_choices]
    if selected_publishers:
        books = books.filter(publisher__in=selected_publishers)

    if favorite_only:
        books = books.filter(is_favorite=True)

    if search_query:
        normalized_query = search_query.casefold()
        matching_book_ids = [
            book_id
            for book_id, title in books.values_list("pk", "title")
            if normalized_query in title.casefold()
        ]
        books = books.filter(pk__in=matching_book_ids)

    has_active_filters = any(
        [
            search_query,
            selected_statuses,
            selected_genres,
            selected_publishers,
            favorite_only,
        ]
    )

    return render(
        request,
        "library/book_list.html",
        {
            "books": books,
            "status_choices": Book.Status.choices,
            "genre_choices": genre_choices,
            "publisher_choices": publisher_choices,
            "search_query": search_query,
            "selected_statuses": selected_statuses,
            "selected_genres": selected_genres,
            "selected_publishers": selected_publishers,
            "favorite_only": favorite_only,
            "has_active_filters": has_active_filters,
            "displayed_count": books.count(),
        },
    )


@login_required
def book_toggle_favorite(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == "POST":
        book.is_favorite = not book.is_favorite
        book.save(update_fields=["is_favorite", "updated_at"])

    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
    ):
        return redirect(next_url)

    return redirect("book_list")


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == "POST":
        progress_form = BookProgressForm(request.POST, instance=book)
        if progress_form.is_valid():
            progress_form.save()
            messages.success(request, "Прогрес читання оновлено.")
            return redirect("book_detail", pk=book.pk)
    else:
        progress_form = BookProgressForm(instance=book)

    notes = book.notes.filter(user=request.user)
    note_form = NoteForm(user=request.user, include_book=False)

    return render(
        request,
        "library/book_detail.html",
        {
            "book": book,
            "progress_form": progress_form,
            "notes": notes,
            "note_form": note_form,
        },
    )


@login_required
@require_POST
def book_note_create(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)
    form = NoteForm(request.POST, user=request.user, include_book=False)

    if form.is_valid():
        note = form.save(commit=False)
        note.user = request.user
        note.book = book
        note.save()
        messages.success(request, "Нотатку додано до книги.")
        return redirect("book_detail", pk=book.pk)

    return render(
        request,
        "library/book_detail.html",
        {
            "book": book,
            "progress_form": BookProgressForm(instance=book),
            "notes": book.notes.filter(user=request.user),
            "note_form": form,
        },
    )


@login_required
def shelf_list(request):
    shelves = (
        Shelf.objects.filter(user=request.user)
        .prefetch_related(
            Prefetch(
                "books",
                queryset=Book.objects.filter(user=request.user).order_by("-created_at"),
            )
        )
    )

    return render(
        request,
        "library/shelf_list.html",
        {
            "shelves": shelves,
            "shelf_count": shelves.count(),
        },
    )


@login_required
def shelf_detail(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk, user=request.user)
    books = shelf.books.filter(user=request.user).prefetch_related("shelves")

    return render(
        request,
        "library/shelf_detail.html",
        {
            "shelf": shelf,
            "books": books,
            "displayed_count": books.count(),
        },
    )


@login_required
def shelf_create(request):
    if request.method == "POST":
        form = ShelfForm(request.POST, user=request.user)
        if form.is_valid():
            shelf = form.save(commit=False)
            shelf.user = request.user
            shelf.save()
            messages.success(request, f"Поличку «{shelf.name}» створено.")
            return redirect("shelf_list")
    else:
        form = ShelfForm(user=request.user)

    return render(
        request,
        "library/shelf_form.html",
        {"form": form, "mode": "create"},
    )


@login_required
def shelf_update(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk, user=request.user)

    if request.method == "POST":
        form = ShelfForm(request.POST, instance=shelf, user=request.user)
        if form.is_valid():
            shelf = form.save()
            messages.success(request, f"Поличку «{shelf.name}» оновлено.")
            return redirect("shelf_list")
    else:
        form = ShelfForm(instance=shelf, user=request.user)

    return render(
        request,
        "library/shelf_form.html",
        {"form": form, "shelf": shelf, "mode": "update"},
    )


@login_required
def shelf_books(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk, user=request.user)
    books = Book.objects.filter(user=request.user).order_by("title")

    if request.method == "POST":
        selected_books = books.filter(pk__in=request.POST.getlist("books"))
        shelf.books.set(selected_books)
        messages.success(request, f"Книги на поличці «{shelf.name}» оновлено.")
        return redirect("shelf_list")

    selected_book_ids = set(shelf.books.values_list("pk", flat=True))

    return render(
        request,
        "library/shelf_books.html",
        {
            "shelf": shelf,
            "books": books,
            "selected_book_ids": selected_book_ids,
        },
    )


@login_required
def shelf_delete(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk, user=request.user)

    if request.method == "POST":
        shelf_name = shelf.name
        shelf.delete()
        messages.success(request, f"Поличку «{shelf_name}» видалено.")
        return redirect("shelf_list")

    return render(request, "library/shelf_confirm_delete.html", {"shelf": shelf})


@login_required
def note_list(request):
    if request.method == "POST":
        form = NoteForm(request.POST, user=request.user)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, "Нотатку додано.")
            return redirect("note_list")
    else:
        form = NoteForm(user=request.user)

    notes = Note.objects.filter(user=request.user).select_related("book")
    return render(
        request,
        "library/note_list.html",
        {
            "form": form,
            "general_notes": notes.filter(book__isnull=True),
            "book_notes": notes.filter(book__isnull=False),
        },
    )


@login_required
def note_update(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    redirect_url = get_safe_redirect_url(request)

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Нотатку оновлено.")
            if redirect_url:
                return redirect(redirect_url)
            if note.book_id:
                return redirect("book_detail", pk=note.book_id)
            return redirect("note_list")
    else:
        form = NoteForm(instance=note, user=request.user)

    return render(
        request,
        "library/note_form.html",
        {"form": form, "note": note, "next_url": redirect_url},
    )


@login_required
@require_POST
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    redirect_url = get_safe_redirect_url(request)
    fallback_book_pk = note.book_id
    note.delete()
    messages.success(request, "Нотатку видалено.")

    if redirect_url:
        return redirect(redirect_url)

    if fallback_book_pk:
        return redirect("book_detail", pk=fallback_book_pk)

    return redirect("note_list")


@login_required
def book_create(request):
    return redirect("book_create_search")


BOOK_IMPORT_SESSION_KEY = "book_import_initials"
BOOK_IMPORT_ALLOWED_FIELDS = [
    "title",
    "author",
    "genre",
    "publisher",
    "published_year",
    "cover_url",
    "description",
]


def get_book_initial_from_mapping(data):
    initial = {}
    for field in BOOK_IMPORT_ALLOWED_FIELDS:
        value = str(data.get(field, "")).strip()
        if value:
            initial[field] = value

    if initial:
        initial.setdefault("status", Book.Status.PLANNED)

    return initial


def remember_book_import_options(request, search_results):
    stored_options = request.session.get(BOOK_IMPORT_SESSION_KEY, {})

    for result in search_results:
        initial = get_book_initial_from_mapping(result)
        if not initial:
            continue

        import_id = secrets.token_urlsafe(8)
        result["import_id"] = import_id
        stored_options[import_id] = initial

    if len(stored_options) > 20:
        stored_options = dict(list(stored_options.items())[-20:])

    request.session[BOOK_IMPORT_SESSION_KEY] = stored_options


def get_book_initial_from_query(request):
    import_id = request.GET.get("import_id", "").strip()
    stored_options = request.session.get(BOOK_IMPORT_SESSION_KEY, {})
    if import_id and import_id in stored_options:
        return dict(stored_options[import_id])

    return get_book_initial_from_mapping(request.GET)

@login_required
def book_create_search(request):
    search_query = request.GET.get("q", "").strip()
    book_url = request.GET.get("book_url", "").strip()
    search_results = []
    has_searched = bool(search_query or book_url)

    if book_url:
        try:
            search_results = import_book_from_url(book_url)
        except BookLookupError:
            search_results = []
    elif search_query:
        search_results = search_books(search_query)

    remember_book_import_options(request, search_results)

    return render(
        request,
        "library/book_search.html",
        {
            "search_query": search_query,
            "book_url": book_url,
            "search_results": search_results,
            "has_searched": has_searched,
        },
    )


@login_required
def book_create_manual(request):
    if request.method == "POST":
        form = BookForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()
            form.save_m2m()
            sync_book_series_shelf(book)
            messages.success(request, f"Книгу «{book.title}» додано до бібліотеки.")
            return redirect("book_list")
    else:
        form = BookForm(user=request.user, initial=get_book_initial_from_query(request))

    return render(request, "library/book_form.html", {"form": form, "mode": "create"})


@login_required
def book_update(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == "POST":
        form = BookForm(request.POST, request.FILES, instance=book, user=request.user)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()
            form.save_m2m()
            sync_book_series_shelf(book)
            messages.success(request, f"Книгу «{book.title}» оновлено.")
            return redirect("book_detail", pk=book.pk)
    else:
        form = BookForm(instance=book, user=request.user)

    return render(request, "library/book_form.html", {"form": form, "book": book, "mode": "update"})


@login_required
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == "POST":
        book_title = book.title
        user = request.user
        book.delete()
        cleanup_empty_series_shelves(user)
        messages.success(request, f"Книгу «{book_title}» видалено.")
        return redirect("book_list")

    return render(request, "library/book_confirm_delete.html", {"book": book})