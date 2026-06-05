from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render
from .forms import BookForm
from .models import Book


def test_page(request):
    return render(request, "library/test.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("book_list")
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})
  
  
@login_required
def book_list(request):
    selected_status = request.GET.get("status", "")
    available_statuses = {status for status, label in Book.Status.choices}

    books = Book.objects.filter(user=request.user).prefetch_related("shelves")
    if selected_status in available_statuses:
        books = books.filter(status=selected_status)
    else:
        selected_status = ""

    return render(
        request,
        "library/book_list.html",
        {
            "books": books,
            "status_choices": Book.Status.choices,
            "selected_status": selected_status,
            "displayed_count": books.count(),
        },
    )


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)
    return render(request, "library/book_detail.html", {"book": book})


@login_required
def book_create(request):
    if request.method == "POST":
        form = BookForm(request.POST, user=request.user)
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
        form = BookForm(request.POST, instance=book, user=request.user)
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