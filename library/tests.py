from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import BookForm, NoteForm, UkrainianAuthenticationForm, UkrainianUserCreationForm
from .models import Book, Note, Shelf


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
        self.assertFalse(response.context["favorite_only"])
        self.assertEqual(response.context["status_choices"], Book.Status.choices)
        self.assertContains(response, "Planned Book")
        self.assertContains(response, "Reading Book")
        self.assertContains(response, "Abandoned Book")
        self.assertContains(response, "status-label--planned")
        self.assertContains(response, "status-label--reading")
        self.assertContains(response, "status-label--failed")
        self.assertContains(response, "♥")
        self.assertContains(response, "♡")
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

    def test_books_can_be_searched_by_title(self):
        Book.objects.create(
            user=self.user,
            title="Dune Messiah",
            author="Frank Herbert",
        )
        Book.objects.create(
            user=self.user,
            title="Foundation",
            author="Isaac Asimov",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"), {"q": "dune"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "dune")
        self.assertTrue(response.context["has_active_filters"])
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Dune Messiah")
        self.assertNotContains(response, "Foundation")

    def test_books_can_be_filtered_by_genre_and_publisher(self):
        Book.objects.create(
            user=self.user,
            title="Fantasy Press Book",
            author="Author One",
            genre="Fantasy",
            publisher="Book Press",
        )
        Book.objects.create(
            user=self.user,
            title="Sci Fi Press Book",
            author="Author Two",
            genre="Sci-Fi",
            publisher="Book Press",
        )
        Book.objects.create(
            user=self.user,
            title="Fantasy House Book",
            author="Author Three",
            genre="Fantasy",
            publisher="Story House",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("book_list"),
            {"genre": "Fantasy", "publisher": "Book Press"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_genre"], "Fantasy")
        self.assertEqual(response.context["selected_publisher"], "Book Press")
        self.assertEqual(response.context["genre_choices"], ["Fantasy", "Sci-Fi"])
        self.assertEqual(response.context["publisher_choices"], ["Book Press", "Story House"])
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Fantasy Press Book")
        self.assertNotContains(response, "Sci Fi Press Book")
        self.assertNotContains(response, "Fantasy House Book")

    def test_search_and_filters_are_combined_in_one_query(self):
        Book.objects.create(
            user=self.user,
            title="Dune",
            author="Frank Herbert",
            status=Book.Status.COMPLETED,
            genre="Sci-Fi",
            publisher="Ace",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Dune Messiah",
            author="Frank Herbert",
            status=Book.Status.READING,
            genre="Sci-Fi",
            publisher="Ace",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Children of Dune",
            author="Frank Herbert",
            status=Book.Status.COMPLETED,
            genre="Sci-Fi",
            publisher="Penguin",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Dune Encyclopedia",
            author="Willis McNelly",
            status=Book.Status.COMPLETED,
            genre="Reference",
            publisher="Ace",
            is_favorite=False,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("book_list"),
            {
                "q": "dune",
                "status": Book.Status.COMPLETED,
                "genre": "Sci-Fi",
                "publisher": "Ace",
                "favorite": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "dune")
        self.assertEqual(response.context["selected_status"], Book.Status.COMPLETED)
        self.assertEqual(response.context["selected_genre"], "Sci-Fi")
        self.assertEqual(response.context["selected_publisher"], "Ace")
        self.assertTrue(response.context["favorite_only"])
        self.assertTrue(response.context["has_active_filters"])
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Dune")
        self.assertNotContains(response, "Dune Messiah")
        self.assertNotContains(response, "Children of Dune")
        self.assertNotContains(response, "Dune Encyclopedia")

    def test_book_cover_url_is_rendered_when_no_uploaded_cover_exists(self):
        Book.objects.create(
            user=self.user,
            title="Linked Cover Book",
            author="Author One",
            cover_url="https://example.com/cover.jpg",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'src="https://example.com/cover.jpg"')

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

    def test_book_card_links_to_detail_and_actions_are_in_menu(self):
        book = Book.objects.create(
            user=self.user,
            title="Clickable Book",
            author="Author One",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("book_detail", args=[book.pk])}"')
        self.assertContains(response, "book-card__link")
        self.assertContains(response, "book-card--planned")
        self.assertContains(response, "book-actions-menu")
        self.assertContains(response, "⋯")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn("display: block", css)
        self.assertIn("padding-top: 5px", css)
        self.assertIn(".book-card--completed", css)
        self.assertIn(".status-strip", css)
        self.assertIn("display: none", css)
        self.assertIn("a:not(.book-card__link)", css)
        self.assertContains(response, "closeMenus")
        self.assertContains(response, "filterMenus")
        self.assertContains(response, 'event.target.closest(".book-actions-menu, .filter-menu")')
        self.assertContains(response, 'event.target.closest(".book-card__link")')



class BookDetailProgressTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="detail-reader",
            password="test-pass-123",
        )
        self.book = Book.objects.create(
            user=self.user,
            title="Detail Book",
            author="Author One",
            status=Book.Status.READING,
        )

    def test_detail_page_updates_status_favorite_and_dates(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("book_detail", args=[self.book.pk]),
            {
                "status": Book.Status.COMPLETED,
                "is_favorite": "on",
                "start_date": "2026-01-01",
                "finish_date": "2026-01-10",
                "rating": "3",
            },
        )

        self.assertRedirects(response, reverse("book_detail", args=[self.book.pk]))
        self.book.refresh_from_db()
        self.assertEqual(self.book.status, Book.Status.COMPLETED)
        self.assertTrue(self.book.is_favorite)
        self.assertEqual(str(self.book.start_date), "2026-01-01")
        self.assertEqual(str(self.book.finish_date), "2026-01-10")
        self.assertEqual(self.book.rating, 3)
        self.assertEqual(self.book.rating_stars(), "★★★☆☆")

    def test_rating_is_allowed_only_for_completed_books(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("book_detail", args=[self.book.pk]),
            {
                "status": Book.Status.READING,
                "start_date": "2026-01-01",
                "rating": "3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Оцінку можна ставити тільки для прочитаних книг.")
        self.book.refresh_from_db()
        self.assertIsNone(self.book.rating)



class NoteFeatureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="note-reader",
            password="test-pass-123",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-note-reader",
            password="test-pass-123",
        )
        self.book = Book.objects.create(
            user=self.user,
            title="Note Book",
            author="Author One",
            start_date="2026-01-01",
            finish_date="2026-01-10",
        )

    def test_note_form_can_create_general_note_or_user_book_note(self):
        other_book = Book.objects.create(
            user=self.other_user,
            title="Other Book",
            author="Author Two",
        )

        form = NoteForm(user=self.user)

        self.assertFalse(form.fields["book"].required)
        self.assertIn(self.book, form.fields["book"].queryset)
        self.assertNotIn(other_book, form.fields["book"].queryset)

    def test_detail_page_shows_book_notes_and_not_duplicate_reading_dates(self):
        Note.objects.create(
            user=self.user,
            book=self.book,
            title="Chapter insight",
            content="Important quote",
            page_number=42,
        )
        Note.objects.create(user=self.user, content="General thought")
        Note.objects.create(
            user=self.other_user,
            book=self.book,
            content="Hidden note",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Нотатки до книги")
        self.assertContains(response, "Chapter insight")
        self.assertContains(response, "Important quote")
        self.assertContains(response, "стор. 42")
        self.assertContains(response, "Редагувати")
        self.assertNotContains(response, "General thought")
        self.assertNotContains(response, "Hidden note")
        self.assertNotContains(response, "Почато читати</small>")
        self.assertNotContains(response, "Закінчено читати</small>")
        self.assertContains(response, 'name="start_date"')
        self.assertContains(response, 'value="2026-01-01"')
        self.assertContains(response, 'name="finish_date"')
        self.assertContains(response, 'value="2026-01-10"')

    def test_user_can_add_and_delete_book_note(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("book_note_create", args=[self.book.pk]),
            {"title": "My title", "content": "New book note", "page_number": "7"},
        )

        self.assertRedirects(response, reverse("book_detail", args=[self.book.pk]))
        note = Note.objects.get(content="New book note")
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.book, self.book)
        self.assertEqual(note.title, "My title")
        self.assertEqual(note.page_number, 7)

        response = self.client.post(reverse("note_delete", args=[note.pk]))

        self.assertRedirects(response, reverse("book_detail", args=[self.book.pk]))
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())

    def test_user_cannot_add_note_to_other_users_book_or_delete_other_users_note(self):
        other_book = Book.objects.create(
            user=self.other_user,
            title="Other Book",
            author="Author Two",
        )
        other_note = Note.objects.create(
            user=self.other_user,
            book=other_book,
            content="Private note",
        )

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("book_note_create", args=[other_book.pk]),
            {"content": "Should not save"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Note.objects.filter(content="Should not save").exists())

        response = self.client.post(reverse("note_delete", args=[other_note.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Note.objects.filter(pk=other_note.pk).exists())

    def test_general_notes_page_creates_and_lists_general_and_book_notes(self):
        Note.objects.create(user=self.user, book=self.book, content="Book note")
        Note.objects.create(user=self.other_user, content="Other hidden note")

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("note_list"),
            {"book": "", "title": "General title", "content": "General note", "page_number": ""},
        )

        self.assertRedirects(response, reverse("note_list"))
        note = Note.objects.get(content="General note")
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.title, "General title")
        self.assertIsNone(note.book)

        response = self.client.get(reverse("note_list"))
        self.assertContains(response, "Без книги")
        self.assertContains(response, "До книг")
        self.assertContains(response, "BookNest")
        self.assertContains(response, 'class="app-sidebar"')
        self.assertContains(response, "📚︎ Бібліотека")
        self.assertContains(response, "📝︎ Нотатки")
        self.assertContains(response, "▦ Полички")
        self.assertContains(response, 'class="is-active" href="/notes/"')
        self.assertNotContains(response, "sidebar-brand")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn("justify-content: center", css)
        self.assertIn(".sidebar-nav a.is-active", css)
        self.assertIn("color: var(--primary)", css)
        self.assertIn("justify-content: space-between", css)
        self.assertIn("max-width: 940px", css)
        self.assertNotIn(".has-sidebar .nav-actions", css)
        content = response.content.decode()
        self.assertLess(content.index("Сторінка"), content.index("Заголовок"))
        self.assertContains(response, "General title")
        self.assertContains(response, "General note")
        self.assertContains(response, "Book note")
        self.assertNotContains(response, "Other hidden note")

    def test_user_can_edit_note_title_content_and_book_link(self):
        note = Note.objects.create(
            user=self.user,
            book=self.book,
            title="Old title",
            content="Old content",
            page_number=5,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("note_update", args=[note.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Редагувати нотатку")
        self.assertContains(response, 'value="Old title"')
        self.assertContains(response, "Old content")
        content = response.content.decode()
        self.assertLess(content.index("Сторінка"), content.index("Заголовок"))

        response = self.client.post(
            reverse("note_update", args=[note.pk]),
            {
                "book": "",
                "title": "Updated title",
                "content": "Updated content",
                "page_number": "9",
            },
        )

        self.assertRedirects(response, reverse("note_list"))
        note.refresh_from_db()
        self.assertIsNone(note.book)
        self.assertEqual(note.title, "Updated title")
        self.assertEqual(note.content, "Updated content")
        self.assertEqual(note.page_number, 9)

    def test_user_cannot_edit_other_users_note(self):
        other_note = Note.objects.create(
            user=self.other_user,
            title="Other title",
            content="Private note",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("note_update", args=[other_note.pk]))

        self.assertEqual(response.status_code, 404)

    def test_book_notes_are_deleted_with_book_but_general_notes_remain(self):
        book_note = Note.objects.create(
            user=self.user,
            book=self.book,
            content="Book note",
        )
        general_note = Note.objects.create(user=self.user, content="General note")

        self.book.delete()

        self.assertFalse(Note.objects.filter(pk=book_note.pk).exists())
        self.assertTrue(Note.objects.filter(pk=general_note.pk).exists())


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
        self.assertEqual(form.fields["cover_image"].label, "Обкладинка")
        self.assertEqual(form.fields["cover_url"].label, "Посилання")
        self.assertEqual(form.fields["is_favorite"].label, "Додати в обране")


    def test_book_form_keeps_cover_url_and_status_as_separate_fields(self):
        form = BookForm()

        self.assertIn("cover_url", form.fields)
        self.assertIn("status", form.fields)
        self.assertNotIn("cover_urlstatus", form.fields)
        self.assertEqual(
            list(form.fields).index("cover_url") + 1,
            list(form.fields).index("status"),
        )


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

    def test_book_form_accepts_cover_url(self):
        form = BookForm(
            data={
                "title": "Cover Link Book",
                "author": "Author One",
                "cover_url": "https://example.com/cover.jpg",
                "status": Book.Status.PLANNED,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["cover_url"], "https://example.com/cover.jpg")

    def test_book_form_groups_cover_file_and_url_in_one_cover_section(self):
        form = BookForm()

        self.assertIn("cover_image", form.fields)
        self.assertIn("cover_url", form.fields)
        self.assertEqual(
            form.fields["cover_image"].help_text,
            "Додай обкладинку файлом або посиланням. Якщо заповнити обидва варіанти, буде показано файл.",
        )

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

    def test_genre_and_publisher_inputs_suggest_current_user_values(self):
        User = get_user_model()
        owner = User.objects.create_user(username="suggest-owner", password="test-pass-123")
        other = User.objects.create_user(username="suggest-other", password="test-pass-123")
        Book.objects.create(
            user=owner,
            title="Owner Fantasy",
            author="Author One",
            genre="Fantasy",
            publisher="Book Press",
        )
        Book.objects.create(
            user=owner,
            title="Owner Sci-Fi",
            author="Author Two",
            genre="Sci-Fi",
            publisher="Story House",
        )
        Book.objects.create(
            user=other,
            title="Other Horror",
            author="Author Three",
            genre="Horror",
            publisher="Other Press",
        )

        form = BookForm(user=owner)

        self.assertEqual(form.genre_options, ["Fantasy", "Sci-Fi"])
        self.assertEqual(form.publisher_options, ["Book Press", "Story House"])
        self.assertNotIn("list", form.fields["genre"].widget.attrs)
        self.assertNotIn("list", form.fields["publisher"].widget.attrs)

    def test_create_page_renders_empty_form_for_get_request(self):
        user = get_user_model().objects.create_user(
            username="creator",
            password="test-pass-123",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("book_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Додати книгу")
        self.assertContains(response, "Обкладинка")
        self.assertContains(response, "Файл")
        self.assertContains(response, "Посилання")
        self.assertContains(response, 'name="cover_image"')
        self.assertContains(response, 'name="cover_url"')
        self.assertNotContains(response, 'list="genre-options"')
        self.assertNotContains(response, 'list="publisher-options"')
        self.assertContains(response, 'enctype="multipart/form-data"')


    def test_create_page_renders_existing_genre_and_publisher_suggestions(self):
        user = get_user_model().objects.create_user(
            username="suggestions",
            password="test-pass-123",
        )
        Book.objects.create(
            user=user,
            title="Suggested Book",
            author="Author One",
            genre="Fantasy",
            publisher="Book Press",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("book_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="combined-value-field"')
        self.assertContains(response, 'id="genre-existing-picker"')
        self.assertContains(response, '<option value="Fantasy">Fantasy</option>')
        self.assertContains(response, 'data-fill-field="id_genre"')
        self.assertContains(response, 'id="publisher-existing-picker"')
        self.assertContains(response, '<option value="Book Press">Book Press</option>')
        self.assertContains(response, 'data-fill-field="id_publisher"')
        self.assertContains(response, "Жанр: введіть свій або оберіть існуючий")
        self.assertContains(response, "Видавництво: введіть своє або оберіть існуюче")
        self.assertContains(response, "Існуючі")
        self.assertNotContains(response, "Обрати існуючий жанр</label>")
        self.assertNotContains(response, "Обрати існуюче видавництво</label>")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".combined-value-field", css)
        self.assertIn(".existing-value-select", css)