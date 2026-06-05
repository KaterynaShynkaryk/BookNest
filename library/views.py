from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import BookForm, BookProgressForm, UkrainianUserCreationForm
from .models import Book


def test_page(request):
    return render(request, "library/test.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def register(request):
    if request.method == "POST":
        form = UkrainianUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("book_list")
    else:
        form = UkrainianUserCreationForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
def book_list(request):
    search_query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "")
    selected_genre = request.GET.get("genre", "")
    selected_publisher = request.GET.get("publisher", "")
    favorite_only = request.GET.get("favorite") == "1"
    available_statuses = {status for status, label in Book.Status.choices}

    user_books = Book.objects.filter(user=request.user)
    genre_choices = list(
        user_books.exclude(genre="")
        .order_by("genre")
        .values_list("genre", flat=True)
        .distinct()
    )
    publisher_choices = list(
        user_books.exclude(publisher="")
        .order_by("publisher")
        .values_list("publisher", flat=True)
        .distinct()
    )

    books = user_books.prefetch_related("shelves")
    if search_query:
        books = books.filter(title__icontains=search_query)

    if selected_status in available_statuses:
        books = books.filter(status=selected_status)
    else:
        selected_status = ""

    if selected_genre in genre_choices:
        books = books.filter(genre=selected_genre)
    else:
        selected_genre = ""

    if selected_publisher in publisher_choices:
        books = books.filter(publisher=selected_publisher)
    else:
        selected_publisher = ""

    if favorite_only:
        books = books.filter(is_favorite=True)

    has_active_filters = any(
        [
            search_query,
            selected_status,
            selected_genre,
            selected_publisher,
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
            "selected_status": selected_status,
            "selected_genre": selected_genre,
            "selected_publisher": selected_publisher,
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
            return redirect("book_detail", pk=book.pk)
    else:
        progress_form = BookProgressForm(instance=book)

    return render(
        request,
        "library/book_detail.html",
        {"book": book, "progress_form": progress_form},
    )


@login_required
def book_create(request):
    if request.method == "POST":
        form = BookForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()
            form.save_m2m()
            return redirect("book_list")
    else:
        form = BookForm(user=request.user)

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
            return redirect("book_detail", pk=book.pk)
    else:
        form = BookForm(instance=book, user=request.user)

    return render(request, "library/book_form.html", {"form": form, "book": book, "mode": "update"})


@login_required
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == "POST":
        book.delete()
        return redirect("book_list")

    return render(request, "library/book_confirm_delete.html", {"book": book})