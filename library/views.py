from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import BookForm
from .models import Book

# Create your views here.
def test_page(request):
    return render(request, "library/test.html")


@login_required
def book_list(request):
    books = Book.objects.filter(user=request.user)
    return render(request, "library/book_list.html", {"books": books})


@login_required
def book_create(request):
    if request.method == "POST":
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()
            form.save_m2m()
            return redirect("book_list")
    else:
        form = BookForm()

    return render(request, "library/book_form.html", {"form": form})