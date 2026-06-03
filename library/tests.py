from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import BookForm, UkrainianAuthenticationForm, UkrainianUserCreationForm
from .models import Book, Shelf


class BookListViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reader",
            password="test-pass-123",
        )

    def test_book_show_status_badges_and_displayed_count(self):
        Book.objects.create(
            user=self.user,
            title="Planned Book",
            author="Author One",
            status=Book.Status.PLANNED,
        )
        Book.objects.create(
            user=self.user,
            title="Reading Book",
            author="Author Two",
            status=Book.Status.READING,
            is_favorite=True,
        )
        Book.objects.create(
            title="Abandoned Book",
            author="Author Three",
            status=Book.Status.FAILED,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('book_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("status_shelves", response.context)
        self.assertNotIn("status_counts", response.context)
        self.assertEqual(response.context["displayed_count"], 3)
        self.assertEqual(response.context["selected_status"], "")
        self.assertFalse(response.context["favorite_only"])
        self.assertEqual(response.context["status_choices"], Book.Status.choices)
        self.assertContains(response, "Planned Book")
        self.assertContains(response, "Reading Book")
        self.assertContains(response, "Abandoned Book")
        self.assertContains(response, "status-label--planned")
        self.assertContains(response, "status-label--reading")
        self.assertContains(response, "status-label--failed")
        self.assertContains(response, "★")
        self.assertContains(response, "☆")
        self.assertContains(response, "Заплановано")
        self.assertContains(response, "Читаю")
        self.assertContains(response, "Закинуто")

    def test_book_can_be_filtered_by_status(self):
        Book.objects.create(
            user=self.user,
            title="Planned Book",
            author="Author One",
            status=Book.Status.PLANNED,
        )
        Book.objects.create(
            user=self.user,
            title="Reading Book",
            author="Author Two",
            status=Book.Status.READING,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"), {"status": Book.Status.READING})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], Book.Status.READING)
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Reading Book")
        self.assertNotContains(response, "Planned Book")

    def test_books_can_be_filtered_by_favorites(self):
        Book.objects.create(
            user=self.user,
            title="Favorite Book",
            author="Author One",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Regular Book",
            author="Author Two",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"), {"favorite": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["favorite_only"])
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Favorite Book")
        self.assertNotContains(response, "Regular Book")

    def test_favorite_toggle_changes_book_favorite_state(self):
        book = Book.objects.create(
            user=self.user,
            title="Toggle Book",
            author="Author One",
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse("book_toggle_favorite", args=[book.pk]))

        self.assertRedirects(response, reverse("book_list"))
        book.refresh_from_db()
        self.assertTrue(book.is_favorite)

        self.client.post(reverse("book_toggle_favorite", args=[book.pk]))
        self.client.post(reverse("book_toggle_favorite", args=[book.pk]))
        book.refresh_from_db()
        self.assertFalse(book.is_favorite)

    def test_favorite_toggle_is_limited_to_current_user_books(self):
        other_user = get_user_model().objects.create_user(
            username="other-reader",
            password="test-pass-123",
        )
        book = Book.objects.create(
            user=other_user,
            title="Other Book",
            author="Author One",
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse("book_toggle_favorite", args=[book.pk]))

        self.assertEqual(response.status_code, 404)
        book.refresh_from_db()
        self.assertFalse(book.is_favorite)


class BookFormTests(TestCase):
    def test_status_uses_ready_ukrainian_choices(self):
        form = BookForm()

        self.assertEqual(
            [value for value, label in form.fields["status"].choices if value],
            [status for status, label in Book.Status.choices],
        )
        self.assertEqual(
            [label for value, label in Book.Status.choices],
            ["Заплановано", "Читаю", "Прочитано", "Закинуто"],
        )

    def test_book_form_labels_are_ukrainian(self):
        form = BookForm()

        self.assertEqual(form.fields["title"].label, "Назва книги")
        self.assertEqual(form.fields["author"].label, "Автор")
        self.assertEqual(form.fields["publisher"].label, "Видавництво")
        self.assertEqual(form.fields["published_year"].label, "Рік видання")
        self.assertEqual(form.fields["cover_image"].label, "Фото обкладинки")
        self.assertEqual(form.fields["is_favorite"].label, "Додати в обране")


    def test_book_form_accepts_cover_image_upload(self):
        cover = SimpleUploadedFile(
            "cover.png",
            b"fake image content",
            content_type="image/png",
        )
        form = BookForm(
            data={
                "title": "Cover Book",
                "author": "Author One",
                "status": Book.Status.PLANNED,
            },
            files={"cover_image": cover},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["cover_image"].name, "cover.png")

    def test_auth_forms_labels_are_ukrainian(self):
        login_form = UkrainianAuthenticationForm()
        register_form = UkrainianUserCreationForm()

        self.assertEqual(login_form.fields["username"].label, "Ім'я користувача")
        self.assertEqual(login_form.fields["password"].label, "Пароль")
        self.assertEqual(register_form.fields["email"].label, "Email")
        self.assertEqual(register_form.fields["password2"].label, "Підтвердження пароля")

    def test_shelves_are_limited_to_current_user(self):
        User = get_user_model()
        owner = User.objects.create_user(username="owner", password="test-pass-123")
        other = User.objects.create_user(username="other", password="test-pass-123")
        owner_shelf = Shelf.objects.create(user=owner, name="Fantasy")
        other_shelf = Shelf.objects.create(user=other, name="Sci-fi")

        form = BookForm(user=owner)

        self.assertIn(owner_shelf, form.fields["shelves"].queryset)
        self.assertNotIn(other_shelf, form.fields["shelves"].queryset)

    def test_create_page_renders_empty_form_for_get_request(self):
        user = get_user_model().objects.create_user(
            username="creator",
            password="test-pass-123",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("book_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Додати книгу")
        self.assertContains(response, 'enctype="multipart/form-data"')
