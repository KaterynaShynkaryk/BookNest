from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import BookForm
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
        )
        Book.objects.create(
            user=self.user,
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
        self.assertEqual(response.context["status_choices"], Book.Status.choices)
        self.assertContains(response, "Planned Book")
        self.assertContains(response, "Reading Book")
        self.assertContains(response, "Abandoned Book")
        self.assertContains(response, "status-label--planned")
        self.assertContains(response, "status-label--reading")
        self.assertContains(response, "status-label--failed")
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
        response = self.client.get(reverse('book_list'), {'status': Book.Status.READING})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], Book.Status.READING)
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Reading Book")
        self.assertNotContains(response, "Planned Book")


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