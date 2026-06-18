from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .forms import BookForm, BookProgressForm, NoteForm, ShelfForm, UkrainianAuthenticationForm, UkrainianUserCreationForm
from .book_lookup import extract_book_metadata
from .models import Book, Note, Shelf


class BookListViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reader",
            password="test-pass-123",
        )

    def test_book_list_loads_without_publisher_filter_param(self):
        Book.objects.create(
            user=self.user,
            title="Publisher Regression",
            author="Author One",
            publisher="КСД",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_publishers"], [])
        self.assertContains(response, "Publisher Regression")

    def test_book_show_status_badges_and_displayed_count(self):
        Book.objects.create(
            user=self.user,
            title="Wishlist Book",
            author="Author Zero",
            status=Book.Status.WISHLIST,
        )
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
        self.assertEqual(response.context["displayed_count"], 4)
        self.assertEqual(response.context["selected_statuses"], [])
        self.assertFalse(response.context["favorite_only"])
        self.assertEqual(response.context["status_choices"], Book.Status.choices)
        self.assertContains(response, 'class="filter-section" open')
        self.assertContains(response, 'class="filter-section__summary"')
        self.assertContains(response, 'class="filter-section__chevron"')
        self.assertContains(response, 'class="filter-checkbox-group"')
        self.assertContains(response, '<legend class="visually-hidden">Статус читання</legend>')
        self.assertContains(response, 'name="status"')
        with open("backend/static/images/booknest-logo.svg", encoding="utf-8") as logo:
            svg = logo.read()
        self.assertIn("BookNest logo", svg)
        self.assertIn("Minimal blue app icon with a white book and bookmark", svg)
        self.assertIn('id="background"', svg)
        self.assertIn('fill="#ffffff"', svg)
        self.assertIn('fill="#f1c66d"', svg)
        self.assertContains(response, '<legend class="visually-hidden">Статус читання</legend>')
        self.assertNotContains(response, 'id="status-filter"')
        self.assertNotContains(response, 'id="genre-filter"')
        self.assertContains(response, "Wishlist Book")
        self.assertContains(response, "Planned Book")
        self.assertContains(response, "Reading Book")
        self.assertContains(response, "Abandoned Book")
        self.assertContains(response, "status-label--wishlist")
        self.assertContains(response, "status-label--planned")
        self.assertContains(response, "status-label--reading")
        self.assertContains(response, "status-label--failed")
        self.assertContains(response, "♥")
        self.assertContains(response, "♡")
        self.assertContains(response, "Бажанка")
        self.assertContains(response, "Заплановано")
        self.assertContains(response, "Читаю")
        self.assertContains(response, "Закинуто")

    def test_base_template_renders_flash_messages_region(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("book_create_manual"),
            {
                "title": "Flash Book",
                "author": "Author One",
                "status": Book.Status.PLANNED,
                "source": Book.Source.MANUAL,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="flash-messages"')
        self.assertContains(response, 'class="flash-message flash-message--success"')
        self.assertContains(response, 'data-flash-dismiss')
        self.assertContains(response, 'rel="icon" type="image/svg+xml"')
        self.assertContains(response, 'images/booknest-logo.svg')
        self.assertContains(response, 'aria-label="Закрити повідомлення"')
        self.assertContains(response, "Книгу «Flash Book» додано до бібліотеки.")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".flash-message", css)
        self.assertIn(".flash-message--success", css)
        self.assertIn(".flash-message__dismiss", css)

    def test_book_create_with_series_creates_auto_series_shelf(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("book_create_manual"),
            {
                "title": "Дюна",
                "author": "Френк Герберт",
                "series": "Хроніки Дюни",
                "status": Book.Status.PLANNED,
                "source": Book.Source.MANUAL,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        book = Book.objects.get(user=self.user, title="Дюна")
        shelf = Shelf.objects.get(user=self.user, name='Серія: "Хроніки Дюни"')
        self.assertTrue(shelf.is_auto_series)
        self.assertEqual(shelf.series, "Хроніки Дюни")
        self.assertEqual(shelf.status, Shelf.Status.NOT_STARTED)
        self.assertIn(shelf, book.shelves.all())

        form = BookForm(user=self.user)
        self.assertNotIn(shelf, form.shelf_options)

    def test_book_create_entry_redirects_to_search_first(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("book_create"))

        self.assertRedirects(response, reverse("book_create_search"))

    def test_book_search_page_queries_google_books_and_links_to_manual_form(self):
        self.client.force_login(self.user)
        results = [
            {
                "title": "Дюна",
                "author": "Френк Герберт",
                "published_year": 1965,
                "publisher": "КСД",
                "genre": "Science fiction, Classics",
                "cover_url": "https://books.google.com/books/content?id=abc&printsec=frontcover&img=1",
                "external_url": "https://books.google.com/books?id=abc",
                "source": "Google Books",
            }
        ]

        with patch("library.views.search_books", return_value=results) as search:
            response = self.client.get(reverse("book_create_search"), {"q": "Дюна"})

        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("Дюна")
        self.assertContains(response, "Результати пошуку")
        self.assertContains(response, "Дюна")
        self.assertContains(response, "Френк Герберт")
        self.assertContains(response, "Google Books")
        self.assertContains(response, reverse("book_create_manual"))
        self.assertContains(response, "Пошук за назвою")
        self.assertContains(response, "Додати вручну")
        self.assertNotContains(response, 'name="isbn"')

    def test_book_search_page_shows_title_and_url_import_without_isbn_field(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("book_create_search"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="book_url"')
        self.assertContains(response, "Yakaboo")
        self.assertContains(response, "Можна ввести назву або посилання")
        self.assertNotContains(response, 'name="isbn"')
        self.assertNotContains(response, "ISBN зазвичай")

    def test_book_search_page_can_import_from_book_url(self):
        self.client.force_login(self.user)
        results = [
            {
                "title": "Мова тіла",
                "author": "А. К. Тернер",
                "published_year": "2024",
                "publisher": "Лабораторія",
                "genre": "",
                "cover_url": "https://example.com/body-language.jpg",
                "description": "Книжка про невербальну комунікацію.",
                "external_url": "https://www.yakaboo.ua/book.html",
                "source": "Сторінка книги",
            }
        ]

        with patch("library.views.import_book_from_url", return_value=results) as import_from_url:
            response = self.client.get(
                reverse("book_create_search"),
                {"book_url": "https://www.yakaboo.ua/book.html"},
            )

        self.assertEqual(response.status_code, 200)
        import_from_url.assert_called_once_with("https://www.yakaboo.ua/book.html")
        self.assertContains(response, "Мова тіла")
        self.assertContains(response, "А. К. Тернер")
        self.assertContains(response, "Сторінка книги")
        self.assertContains(response, "import_id=")
        self.assertNotContains(response, "description=")

    def test_book_url_import_uses_short_session_link_for_long_metadata(self):
        self.client.force_login(self.user)
        long_description = "Опис " * 1500
        results = [
            {
                "title": "Великий опис",
                "author": "Автор",
                "published_year": "2024",
                "publisher": "Видавництво",
                "genre": "Роман",
                "cover_url": "https://example.com/cover.jpg",
                "description": long_description,
                "external_url": "https://example.com/book",
                "source": "Сторінка книги",
            }
        ]

        with patch("library.views.import_book_from_url", return_value=results):
            response = self.client.get(
                reverse("book_create_search"),
                {"book_url": "https://example.com/book"},
            )

        self.assertContains(response, "import_id=")
        self.assertNotContains(response, long_description)
        import_id = next(iter(self.client.session["book_import_initials"]))

        response = self.client.get(reverse("book_create_manual"), {"import_id": import_id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Великий опис"')
        self.assertContains(response, long_description[:120])

    def test_book_url_metadata_can_be_extracted_from_json_ld(self):
        metadata = extract_book_metadata(
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Мова тіла",'
            '"image":"https://example.com/cover.jpg","description":"Опис книги",'
            '"additionalProperty":['
            '{"name":"Автор","value":"А. К. Тернер"},'
            '{"name":"Видавництво","value":"Лабораторія"},'
            '{"name":"Рік видання","value":"2024"}'
            ']}'
            "</script>"
        )

        self.assertEqual(metadata["title"], "Мова тіла")
        self.assertEqual(metadata["author"], "А. К. Тернер")
        self.assertEqual(metadata["publisher"], "Лабораторія")
        self.assertEqual(metadata["published_year"], "2024")
        self.assertEqual(metadata["cover_url"], "https://example.com/cover.jpg")

    def test_book_url_metadata_falls_back_to_visible_book_details(self):
        metadata = extract_book_metadata(
            '<html><head>'
            '<meta property="og:title" content="Дівчина, яка впала під море | Yakaboo">'
            '<meta property="og:description" content="Фентезійна історія.">'
            '<meta property="og:image" content="https://example.com/sea.jpg">'
            '</head><body>'
            '<dl><dt>Автор</dt><dd>Аксі О</dd>'
            '<dt>Видавництво</dt><dd>Рідна мова</dd>'
            '<dt>Рік видання</dt><dd>2024</dd></dl>'
            '</body></html>'
        )

        self.assertEqual(metadata["title"], "Дівчина, яка впала під море")
        self.assertEqual(metadata["author"], "Аксі О")
        self.assertEqual(metadata["publisher"], "Рідна мова")
        self.assertEqual(metadata["published_year"], "2024")
        self.assertEqual(metadata["cover_url"], "https://example.com/sea.jpg")

    def test_book_url_metadata_extracts_yakaboo_frontend_attribute_labels(self):
        metadata = extract_book_metadata(
            '<html><body>'
            '<script type="application/json">'
            '{"product":{"title":"Книга з атрибутами",'
            '"brand":"Yakaboo",'
            '"attributes":['
            '{"frontend_label":"Видавництво","value":"Видавництво Старого Лева"},'
            '{"frontend_label":"Рік видання","value":"2025"},'
            '{"frontend_label":"Автор","value":"Катерина Єгорушкіна"}'
            ']}}'
            '</script>'
            '</body></html>'
        )

        self.assertEqual(metadata["title"], "Книга з атрибутами")
        self.assertEqual(metadata["author"], "Катерина Єгорушкіна")
        self.assertEqual(metadata["publisher"], "Видавництво Старого Лева")
        self.assertEqual(metadata["published_year"], "2025")
        self.assertNotEqual(metadata["publisher"], "Yakaboo")

    def test_book_url_metadata_extracts_yakaboo_values_from_inline_script_state(self):
        metadata = extract_book_metadata(
            '<html><head>'
            '<meta property="og:title" content="Книга з JS state | Yakaboo">'
            '</head><body>'
            '<script>'
            'window.__PRODUCT__ = {'
            '"characteristics":['
            '{"label":"Видавництво","value":"Наш Формат"},'
            '{"label":"Рік видання","value":"2022"}'
            ']};'
            '</script>'
            '</body></html>'
        )

        self.assertEqual(metadata["title"], "Книга з JS state")
        self.assertEqual(metadata["publisher"], "Наш Формат")
        self.assertEqual(metadata["published_year"], "2022")

    def test_book_url_metadata_ignores_yakaboo_publisher_label_placeholder(self):
        metadata = extract_book_metadata(
            '<html><head>'
            '<meta property="og:title" content="Книга з placeholder | Yakaboo">'
            '</head><body>'
            '<script>'
            'window.__PRODUCT__ = {'
            '"publisher":"book_publisher_label",'
            '"characteristics":['
            '{"label":"Видавництво","value":"Видавництво Старого Лева"},'
            '{"label":"Рік видання","value":"2024"}'
            ']};'
            '</script>'
            '</body></html>'
        )

        self.assertEqual(metadata["title"], "Книга з placeholder")
        self.assertEqual(metadata["publisher"], "Видавництво Старого Лева")
        self.assertEqual(metadata["published_year"], "2024")
        self.assertNotEqual(metadata["publisher"], "book_publisher_label")

    def test_book_url_metadata_does_not_guess_publisher_from_unlabelled_text(self):
        metadata = extract_book_metadata(
            '<html><head>'
            '<meta property="og:title" content="Книга без видавництва">'
            '<meta property="og:description" content="Опис книги.">'
            '<meta property="og:image" content="https://example.com/cover.jpg">'
            '</head><body>'
            '<script>window.analytics = {publisher: "Некоректне видавництво"};</script>'
            '<p>Купити книгу на сайті видавництва або в каталозі книгарні.</p>'
            '</body></html>'
        )

        self.assertEqual(metadata["title"], "Книга без видавництва")
        self.assertEqual(metadata["publisher"], "")

    def test_book_search_page_handles_unavailable_catalogs_without_error_flash(self):
        self.client.force_login(self.user)

        with patch("library.views.search_books", return_value=[]):
            response = self.client.get(reverse("book_create_search"), {"q": "Рідкісна книга"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Нічого не знайдено")
        self.assertContains(response, "ручне додавання працює без інтернету")
        self.assertNotContains(response, "Не вдалося отримати дані")

    def test_manual_book_form_can_be_prefilled_from_search_result(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("book_create_manual"),
            {
                "title": "Дюна",
                "author": "Френк Герберт",
                "publisher": "КСД",
                "published_year": "1965",
                "genre": "Science fiction",
                "cover_url": "https://books.google.com/books/content?id=abc&printsec=frontcover&img=1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Дюна"')
        self.assertContains(response, 'value="Френк Герберт"')
        self.assertContains(response, 'value="КСД"')
        self.assertContains(response, 'value="1965"')
        self.assertContains(response, 'value="Science fiction"')

    def test_login_and_logout_show_flash_messages(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": "test-pass-123",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ви успішно увійшли.")

        response = self.client.get(reverse("logout"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ви вийшли з акаунту.")
        self.assertContains(response, "window.setTimeout")
        self.assertContains(response, "flash-message--error")
        self.assertContains(response, "flash-message--danger")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn("flex-direction: column", css)
        self.assertIn(".auth-page .flash-messages", css)

    def test_login_page_does_not_show_demo_account_hint(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BookNest")
        self.assertContains(response, "Моя цифрова бібліотека")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn("min-height: 100svh", css)
        self.assertIn("padding: 1rem 1rem 2rem", css)
        self.assertNotContains(response, "Моя бібліотека")
        self.assertNotContains(response, "Демо акаунт")
        self.assertNotContains(response, "demo12345")
        self.assertNotContains(response, "python manage.py seed_demo_user")

    def test_seed_demo_user_command_creates_sample_account(self):
        stdout = StringIO()

        call_command("seed_demo_user", stdout=stdout)

        User = get_user_model()
        user = User.objects.get(username="demo")
        self.assertTrue(user.check_password("demo12345"))
        self.assertEqual(Book.objects.filter(user=user).count(), 3)
        self.assertTrue(Book.objects.filter(user=user, status=Book.Status.WISHLIST).exists())
        self.assertEqual(Shelf.objects.filter(user=user).count(), 3)
        self.assertEqual(Note.objects.filter(user=user).count(), 2)
        self.assertIn("demo", stdout.getvalue())

        call_command("seed_demo_user", stdout=StringIO())

        self.assertEqual(User.objects.filter(username="demo").count(), 1)
        self.assertEqual(Book.objects.filter(user=user).count(), 3)
        self.assertEqual(Shelf.objects.filter(user=user).count(), 3)
        self.assertEqual(Note.objects.filter(user=user).count(), 2)

    def test_book_card_shows_shelves_next_to_status(self):
        shelf = Shelf.objects.create(user=self.user, name="Фентезі")
        book = Book.objects.create(
            user=self.user,
            title="Shelf Book",
            author="Author One",
            status=Book.Status.READING,
        )
        book.shelves.add(shelf)

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="book-meta-row"')
        self.assertContains(response, 'aria-label="Полички книги"')
        self.assertContains(response, "Читаю")
        self.assertContains(response, "Фентезі")
        content = response.content.decode()
        self.assertLess(content.index("Читаю"), content.index("Фентезі"))

    def test_library_empty_state_is_compact_and_actionable(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="empty-state library-empty-state"')
        self.assertContains(response, 'class="empty-state__icon"')
        self.assertContains(response, "Бібліотека порожня")
        self.assertContains(response, "Додайте першу книгу, щоб почати збирати свою цифрову бібліотеку.")
        self.assertContains(response, "Додати книгу")
        self.assertNotContains(response, "Ваша бібліотека поки порожня")
        self.assertNotContains(response, "empty-book")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".empty-state__icon", css)
        self.assertIn("font-size: 2.75rem", css)

    def test_filtered_library_empty_state_is_compact_and_clear(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"), {"q": "missing"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="empty-state library-empty-state"')
        self.assertContains(response, "Книг не знайдено")
        self.assertContains(response, "Змініть пошук або скиньте фільтри")
        self.assertContains(response, "Скинути фільтри")
        self.assertNotContains(response, "Немає книг за цим запитом")

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
        self.assertEqual(response.context["selected_statuses"], [Book.Status.READING])
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
            series="Chronicles",
        )
        Book.objects.create(
            user=self.user,
            title="Sci Fi Press Book",
            author="Author Two",
            genre="Sci-Fi",
            publisher="Book Press",
            series="Chronicles",
        )
        Book.objects.create(
            user=self.user,
            title="Fantasy House Book",
            author="Author Three",
            genre="Fantasy, Romance",
            publisher="Story House",
            series="Standalone",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("book_list"),
            {"genre": "Fantasy", "publisher": "Book Press"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_genres"], ["Fantasy"])
        self.assertEqual(response.context["selected_publishers"], ["Book Press"])
        self.assertEqual(response.context["genre_choices"], ["Fantasy", "Romance", "Sci-Fi"])
        self.assertEqual(response.context["publisher_choices"], ["Book Press", "Story House"])
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Fantasy Press Book")
        self.assertNotContains(response, "Sci Fi Press Book")
        self.assertNotContains(response, "Fantasy House Book")

    def test_books_can_be_searched_by_ukrainian_title_case_insensitively(self):
        Book.objects.create(
            user=self.user,
            title="Мова тіла",
            author="А. К. Тернер",
        )
        Book.objects.create(
            user=self.user,
            title="Дівчина, яка впала під море",
            author="Аксі О",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"), {"q": "мова"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "мова")
        self.assertTrue(response.context["has_active_filters"])
        self.assertEqual(response.context["displayed_count"], 1)
        self.assertContains(response, "Мова тіла")
        self.assertNotContains(response, "Дівчина, яка впала під море")

    def test_books_can_be_filtered_by_multiple_checkbox_values(self):
        Book.objects.create(
            user=self.user,
            title="Completed Fantasy",
            author="Author One",
            status=Book.Status.COMPLETED,
            genre="Fantasy",
            publisher="Book Press",
            series="Chronicles",
        )
        Book.objects.create(
            user=self.user,
            title="Reading Sci-Fi",
            author="Author Two",
            status=Book.Status.READING,
            genre="Sci-Fi",
            publisher="Story House",
            series="Saga",
        )
        Book.objects.create(
            user=self.user,
            title="Planned Mystery",
            author="Author Three",
            status=Book.Status.PLANNED,
            genre="Mystery",
            publisher="Hidden Press",
            series="Standalone",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("book_list"),
            {
                "status": [Book.Status.COMPLETED, Book.Status.READING],
                "genre": ["Fantasy", "Sci-Fi"],
                "publisher": ["Book Press", "Story House"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_statuses"], [Book.Status.COMPLETED, Book.Status.READING])
        self.assertEqual(response.context["selected_genres"], ["Fantasy", "Sci-Fi"])
        self.assertEqual(response.context["selected_publishers"], ["Book Press", "Story House"])
        self.assertEqual(response.context["displayed_count"], 2)
        self.assertContains(response, "Completed Fantasy")
        self.assertContains(response, "Reading Sci-Fi")
        self.assertNotContains(response, "Planned Mystery")

    def test_search_and_filters_are_combined_in_one_query(self):
        Book.objects.create(
            user=self.user,
            title="Dune",
            author="Frank Herbert",
            status=Book.Status.COMPLETED,
            genre="Sci-Fi",
            publisher="Ace",
            series="Dune",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Dune Messiah",
            author="Frank Herbert",
            status=Book.Status.READING,
            genre="Sci-Fi",
            publisher="Ace",
            series="Dune",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Children of Dune",
            author="Frank Herbert",
            status=Book.Status.COMPLETED,
            genre="Sci-Fi",
            publisher="Penguin",
            series="Dune",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Dune Encyclopedia",
            author="Willis McNelly",
            status=Book.Status.COMPLETED,
            genre="Reference",
            publisher="Ace",
            series="Reference Shelf",
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
        self.assertEqual(response.context["selected_statuses"], [Book.Status.COMPLETED])
        self.assertEqual(response.context["selected_genres"], ["Sci-Fi"])
        self.assertEqual(response.context["selected_publishers"], ["Ace"])
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
        self.assertContains(response, 'class="book-cover book-cover--sm"')
        self.assertNotContains(response, 'class="book-cover-frame book-cover--sm"')
        self.assertContains(response, 'src="https://example.com/cover.jpg"')

    def test_book_cover_has_no_decorative_left_stripe(self):
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()

        self.assertIn(".book-cover img", css)
        self.assertNotIn(".book-cover-frame", css)
        self.assertNotIn("left: 18%", css)
        self.assertNotIn("linear-gradient(135deg", css)
        self.assertNotIn("left: -10px", css)

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

    def test_favorite_ordering_moves_book_forward_and_back(self):
        book1 = Book.objects.create(user=self.user, title="Book One", author="Author")
        book2 = Book.objects.create(user=self.user, title="Book Two", author="Author")
        book3 = Book.objects.create(user=self.user, title="Book Three", author="Author")

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))
        self.assertEqual(list(response.context["books"]), [book3, book2, book1])

        book2.is_favorite = True
        book2.save()
        response = self.client.get(reverse("book_list"))
        self.assertEqual(list(response.context["books"]), [book2, book3, book1])

        book2.is_favorite = False
        book2.save()
        response = self.client.get(reverse("book_list"))
        self.assertEqual(list(response.context["books"]), [book3, book2, book1])

    def test_book_card_shows_reading_date_for_completed_books(self):
        import datetime
        book = Book.objects.create(
            user=self.user,
            title="Completed Book",
            author="Author One",
            status=Book.Status.COMPLETED,
            finish_date=datetime.date(2026, 6, 17),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("book_list"))
        self.assertContains(response, "прочитано 17.06.2026")

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
        self.assertIn("align-items: stretch", css)
        self.assertIn("min-height: 100%", css)
        self.assertIn("margin-top: auto", css)
        self.assertIn("bottom: 0", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn("flex-direction: row", css)
        self.assertIn("max-width: 100%", css)
        self.assertIn("width: auto", css)
        self.assertIn("padding-left: 1rem", css)
        self.assertIn("padding-left: 0.5rem", css)
        self.assertIn(".filter-controls--compact", css)
        self.assertIn("min-height: 4.6rem", css)
        self.assertIn("min-height: 2rem", css)
        self.assertIn(".status-strip", css)
        self.assertIn("display: none", css)
        self.assertIn("a:not(.book-card__link)", css)
        self.assertIn(".book-card:has(.book-actions-menu[open])", css)
        self.assertIn(".book-actions-menu[open]", css)
        self.assertIn("z-index: 70", css)
        self.assertContains(response, "closeMenus")
        self.assertContains(response, "filterMenus")
        self.assertContains(response, 'event.target.closest(".book-actions-menu, .filter-menu")')
        self.assertContains(response, 'event.target.closest(".book-card__link")')


class ShelfListViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shelf-reader",
            password="test-pass-123",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-shelf-reader",
            password="test-pass-123",
        )

    def test_shelf_list_shows_only_current_users_shelves_and_books(self):
        fantasy = Shelf.objects.create(user=self.user, name="Фентезі")
        classics = Shelf.objects.create(user=self.user, name="Класика")
        hidden_shelf = Shelf.objects.create(user=self.other_user, name="Чужа поличка")
        first_book = Book.objects.create(user=self.user, title="Абетка магії", author="Автор Один")
        second_book = Book.objects.create(user=self.user, title="Замок", author="Автор Два")
        hidden_book = Book.objects.create(user=self.other_user, title="Чужа книга", author="Автор Три")
        fantasy.books.add(second_book, first_book)
        classics.books.add(first_book)
        hidden_shelf.books.add(hidden_book)

        self.client.force_login(self.user)
        response = self.client.get(reverse("shelf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "library/shelf_list.html")
        self.assertEqual(response.context["shelf_count"], 2)
        self.assertContains(response, "Фентезі")
        self.assertContains(response, "Класика")
        self.assertContains(response, "Книг: 2")
        self.assertContains(response, 'class="primary-link-button add-book-link" href="/shelves/add/"')
        self.assertContains(response, "Книг: 1")
        self.assertContains(response, 'class="shelf-cover-grid"')
        self.assertContains(response, 'class="shelf-cover-tile"')
        self.assertContains(response, "Абетка магії")
        self.assertContains(response, "Замок")
        self.assertNotContains(response, 'class="shelf-book-list"')
        self.assertContains(response, 'class="is-active" href="/shelves/"')
        self.assertContains(response, 'class="book-actions-menu shelf-actions-menu"')
        self.assertContains(response, "⋯")
        self.assertContains(response, "📚︎ Керувати книгами")
        self.assertContains(response, '<span class="mirrored-icon" aria-hidden="true">✎</span> Редагувати')
        self.assertContains(response, "🗙 Видалити")
        self.assertNotContains(response, "Відкрити поличку →")
        self.assertContains(response, 'event.target.closest(".shelf-actions-menu")')
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".shelf-card:has(.book-actions-menu[open])", css)
        self.assertNotContains(response, 'class="shelf-card__icon"')
        self.assertNotContains(response, "Чужа поличка")
        self.assertNotContains(response, "Чужа книга")

    def test_shelf_detail_shows_shelf_actions_menu_without_open_link(self):
        shelf = Shelf.objects.create(user=self.user, name="Фентезі")
        book = Book.objects.create(user=self.user, title="Абетка магії", author="Автор Один")
        shelf.books.add(book)

        self.client.force_login(self.user)
        response = self.client.get(reverse("shelf_detail", args=[shelf.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "library/shelf_detail.html")
        self.assertContains(response, "Фентезі")
        self.assertContains(response, "Абетка магії")
        self.assertContains(response, 'class="book-actions-menu shelf-actions-menu"')
        self.assertContains(response, "📚︎ Керувати книгами")
        self.assertContains(response, '<span class="mirrored-icon" aria-hidden="true">✎</span> Редагувати')
        self.assertContains(response, "🗙 Видалити")
        self.assertNotContains(response, "Відкрити поличку")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".page-heading:has(.book-actions-menu[open])", css)
        self.assertIn(".page-heading__actions .book-actions-menu", css)


    def test_shelf_list_has_empty_state(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("shelf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["shelf_count"], 0)
        self.assertContains(response, "Поличок ще немає")
        self.assertContains(response, "Створіть першу поличку, щоб групувати книги за настроєм, жанром або планами.")
        self.assertContains(response, 'class="empty-state shelf-empty-state"')
        self.assertContains(response, 'class="shelf-empty-icon"')
        self.assertContains(response, "До бібліотеки")
        self.assertNotContains(response, "empty-book")
        self.assertNotContains(response, "Створення поличок додамо наступним кроком")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".shelf-empty-state", css)
        self.assertIn(".shelf-empty-icon", css)
        self.assertIn("font-size: 2.75rem", css)

    def test_shelf_list_shows_empty_state_for_shelf_without_books(self):
        Shelf.objects.create(user=self.user, name="Порожня")

        self.client.force_login(self.user)
        response = self.client.get(reverse("shelf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Порожня")
        self.assertContains(response, "Книг: 0")
        self.assertContains(response, 'class="shelf-card-empty-state"')
        self.assertContains(response, 'class="shelf-card-empty-state__icon"')
        self.assertContains(response, "Поличка порожня")
        self.assertContains(response, "Оберіть “Керувати книгами” в меню ⋯, щоб додати книги на поличку.")
        self.assertContains(response, f'href="/shelves/{Shelf.objects.get(name="Порожня").pk}/books/"')
        self.assertNotContains(response, 'class="note-empty"')
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".shelf-card-empty-state", css)
        self.assertNotIn(".shelf-card-empty-state__action", css)

    def test_empty_shelf_add_book_link_opens_existing_book_picker(self):
        shelf = Shelf.objects.create(user=self.user, name="Порожня")
        Book.objects.create(user=self.user, title="Доступна книга", author="Автор Один")

        self.client.force_login(self.user)
        response = self.client.get(reverse("shelf_books", args=[shelf.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "library/shelf_books.html")
        self.assertContains(response, "Книги на поличці “Порожня”")
        self.assertContains(response, 'class="shelf-book-picker"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'name="books"')
        self.assertContains(response, "Доступна книга")
        self.assertContains(response, "Зберегти поличку")
        self.assertContains(response, 'class="is-active" href="/shelves/"')

    def test_shelf_book_picker_updates_existing_books_and_ignores_other_users_books(self):
        shelf = Shelf.objects.create(user=self.user, name="Підібране")
        first_book = Book.objects.create(user=self.user, title="Моя перша", author="Автор Один")
        second_book = Book.objects.create(user=self.user, title="Моя друга", author="Автор Два")
        other_book = Book.objects.create(user=self.other_user, title="Чужа", author="Автор Три")
        shelf.books.add(first_book)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("shelf_books", args=[shelf.pk]),
            {"books": [str(second_book.pk), str(other_book.pk)]},
        )

        self.assertRedirects(response, reverse("shelf_list"))
        self.assertEqual(list(shelf.books.order_by("title")), [second_book])

    def test_shelf_cards_show_latest_eight_book_covers_instead_of_title_list(self):
        shelf = Shelf.objects.create(user=self.user, name="Обкладинки")
        books = [
            Book.objects.create(
                user=self.user,
                title=f"Книга {index}",
                author="Автор",
                cover_url=f"https://example.com/cover-{index}.jpg",
            )
            for index in range(1, 10)
        ]
        shelf.books.add(*books)

        self.client.force_login(self.user)
        response = self.client.get(reverse("shelf_list"))

        self.assertContains(response, 'class="shelf-cover-grid"')
        self.assertContains(response, 'class="shelf-cover-tile"', count=8)
        for index in range(2, 10):
            self.assertContains(response, f"https://example.com/cover-{index}.jpg")
        self.assertNotContains(response, "https://example.com/cover-1.jpg")
        self.assertContains(response, "+ ще 1")
        self.assertContains(response, "📚︎ Керувати книгами")
        self.assertNotContains(response, 'class="shelf-card__manage-link"')
        self.assertNotContains(response, 'class="shelf-book-list"')

    def test_user_can_create_shelf(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("shelf_create"), {"name": "  Манґа  "})

        self.assertRedirects(response, reverse("shelf_list"))
        shelf = Shelf.objects.get(user=self.user)
        self.assertEqual(shelf.name, "Манґа")

    def test_create_shelf_shows_validation_errors(self):
        Shelf.objects.create(user=self.user, name="Фентезі")

        self.client.force_login(self.user)
        response = self.client.post(reverse("shelf_create"), {"name": "фентезі"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "library/shelf_form.html")
        self.assertContains(response, "Поличка з такою назвою вже існує.")
        self.assertEqual(Shelf.objects.filter(user=self.user).count(), 1)

    def test_user_can_update_own_shelf(self):
        shelf = Shelf.objects.create(user=self.user, name="Старе")

        self.client.force_login(self.user)
        response = self.client.post(reverse("shelf_update", args=[shelf.pk]), {"name": "Нове"})

        self.assertRedirects(response, reverse("shelf_list"))
        shelf.refresh_from_db()
        self.assertEqual(shelf.name, "Нове")

    def test_user_cannot_update_other_users_shelf(self):
        shelf = Shelf.objects.create(user=self.other_user, name="Чужа")

        self.client.force_login(self.user)
        response = self.client.post(reverse("shelf_update", args=[shelf.pk]), {"name": "Нова"})

        self.assertEqual(response.status_code, 404)
        shelf.refresh_from_db()
        self.assertEqual(shelf.name, "Чужа")

    def test_user_can_delete_own_shelf_without_deleting_books(self):
        shelf = Shelf.objects.create(user=self.user, name="Видалити")
        book = Book.objects.create(user=self.user, title="Book", author="Author")
        book.shelves.add(shelf)

        self.client.force_login(self.user)
        get_response = self.client.get(reverse("shelf_delete", args=[shelf.pk]))
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "Книги не будуть видалені")

        response = self.client.post(reverse("shelf_delete", args=[shelf.pk]))

        self.assertRedirects(response, reverse("shelf_list"))
        self.assertFalse(Shelf.objects.filter(pk=shelf.pk).exists())
        self.assertTrue(Book.objects.filter(pk=book.pk).exists())

    def test_user_cannot_delete_other_users_shelf(self):
        shelf = Shelf.objects.create(user=self.other_user, name="Чужа")

        self.client.force_login(self.user)
        response = self.client.post(reverse("shelf_delete", args=[shelf.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Shelf.objects.filter(pk=shelf.pk).exists())

    def test_user_can_update_series_shelf_status(self):
        shelf = Shelf.objects.create(
            user=self.user,
            name='Серія: "Хроніки Дюни"',
            series="Хроніки Дюни",
            is_auto_series=True,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("shelf_update", args=[shelf.pk]),
            {"name": shelf.name, "status": Shelf.Status.STARTED},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        shelf.refresh_from_db()
        self.assertEqual(shelf.status, Shelf.Status.STARTED)
        self.assertContains(response, "Автополичка серії")
        self.assertContains(response, "Почато")
        self.assertContains(response, "shelf-status--started")

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

    def test_detail_page_avoids_duplicate_author_and_rating_in_main_content(self):
        self.book.status = Book.Status.COMPLETED
        self.book.rating = 4
        self.book.genre = "Fantasy"
        self.book.publisher = "Book Press"
        self.book.series = "Series One"
        self.book.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("book_detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Author One")
        self.assertNotContains(response, 'class="detail-rating"')
        self.assertNotContains(response, "<small>Автор</small>")
        self.assertContains(response, "Fantasy")
        self.assertContains(response, "Book Press")
        self.assertContains(response, "Серія")
        self.assertContains(response, "Series One")

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

    def test_finish_date_cannot_be_before_start_date_on_detail_page(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("book_detail", args=[self.book.pk]),
            {
                "status": Book.Status.COMPLETED,
                "start_date": "2026-02-10",
                "finish_date": "2026-02-01",
                "rating": "4",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Дата завершення не може бути раніше дати початку.")
        self.book.refresh_from_db()
        self.assertIsNone(self.book.finish_date)

    def test_wishlist_status_disables_start_date_on_detail_page(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("book_detail", args=[self.book.pk]),
            {
                "status": Book.Status.WISHLIST,
                "start_date": "2026-01-01",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Дату початку не можна вказувати для бажанки.")
        self.book.refresh_from_db()
        self.assertEqual(self.book.status, Book.Status.READING)
        self.assertIsNone(self.book.start_date)

        response = self.client.get(reverse("book_detail", args=[self.book.pk]))

        self.assertContains(response, "data-not-wishlist")
        self.assertContains(response, 'const wishlistValue = "wishlist";')

    def test_progress_form_rejects_rating_outside_star_range(self):
        for invalid_rating in ("0", "6", "abc"):
            with self.subTest(invalid_rating=invalid_rating):
                form = BookProgressForm(
                    data={
                        "status": Book.Status.COMPLETED,
                        "start_date": "2026-01-01",
                        "finish_date": "2026-01-10",
                        "rating": invalid_rating,
                    },
                    instance=self.book,
                )

                self.assertFalse(form.is_valid())
                self.assertIn("rating", form.errors)

    def test_progress_form_allows_empty_rating_for_completed_book(self):
        form = BookProgressForm(
            data={
                "status": Book.Status.COMPLETED,
                "start_date": "2026-01-01",
                "finish_date": "2026-01-10",
                "rating": "",
            },
            instance=self.book,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["rating"])



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
        self.assertContains(response, 'class="note-form-toggle"')
        self.assertContains(response, '+ Додати нотатку')
        self.assertContains(response, "Chapter insight")
        content = response.content.decode()
        self.assertLess(content.index("Заголовок"), content.index("Сторінка"))
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
        self.assertContains(response, "☷︎ Полички")
        self.assertContains(response, 'href="/shelves/"')
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
        self.assertLess(content.index("Заголовок"), content.index("Сторінка"))
        self.assertContains(response, "General title")
        self.assertContains(response, "General note")
        self.assertContains(response, "Book note")
        self.assertContains(response, 'class="note-form-toggle note-page-form-toggle"')
        self.assertContains(response, '+ Додати нотатку')
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
        self.assertLess(content.index("Заголовок"), content.index("Сторінка"))

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

    def test_detail_and_notes_pages_show_helpful_empty_states(self):
        self.client.force_login(self.user)

        detail_response = self.client.get(reverse("book_detail", args=[self.book.pk]))
        self.assertContains(
            detail_response,
            "Натисніть “Додати нотатку”, щоб зберегти першу думку про книгу.",
        )
        self.assertContains(detail_response, 'class="note-empty__icon"')
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".note-form-toggle", css)
        self.assertIn(".note-form-toggle__button", css)
        self.assertIn(".notes-page-layout:has(.note-page-form-toggle:not([open]))", css)
        self.assertIn(".notes-page-layout:has(.note-page-form-toggle[open])", css)

        notes_response = self.client.get(reverse("note_list"))
        self.assertContains(
            notes_response,
            "Загальних нотаток ще немає. Натисніть “Додати нотатку”, щоб створити першу.",
        )
        self.assertContains(
            notes_response,
            "Нотаток до книг ще немає. Натисніть “Додати нотатку” або додайте нотатку зі сторінки книги.",
        )

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


    class ShelfFormTests(TestCase):
        def test_shelf_form_rejects_duplicate_name_for_same_user(self):
            user = get_user_model().objects.create_user(username="shelf-form-reader")
            other = get_user_model().objects.create_user(username="other-shelf-form-reader")
            Shelf.objects.create(user=user, name="Фентезі")
            Shelf.objects.create(user=other, name="Фентезі")

            form = ShelfForm(data={"name": " фентезі "}, user=user)

            self.assertFalse(form.is_valid())
            self.assertIn("Поличка з такою назвою вже існує.", form.errors["name"])

        def test_shelf_form_allows_same_name_for_different_user(self):
            owner = get_user_model().objects.create_user(username="owner-shelf-form-reader")
            other = get_user_model().objects.create_user(username="allowed-shelf-form-reader")
            Shelf.objects.create(user=owner, name="Фентезі")

            form = ShelfForm(data={"name": "Фентезі"}, user=other)

            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["name"], "Фентезі")


class BookFormTests(TestCase):
    def test_status_uses_ready_ukrainian_choices(self):
        form = BookForm()

        self.assertEqual(
            [value for value, label in form.fields["status"].choices if value],
            [status for status, label in Book.Status.choices],
        )
        self.assertEqual(
            [label for value, label in Book.Status.choices],
            ["Бажанка", "Заплановано", "Читаю", "Прочитано", "Закинуто"],
        )

    def test_book_form_labels_are_ukrainian(self):
        form = BookForm()

        self.assertEqual(form.fields["title"].label, "Назва книги")
        self.assertEqual(form.fields["author"].label, "Автор")
        self.assertEqual(form.fields["publisher"].label, "Видавництво")
        self.assertEqual(form.fields["series"].label, "Серія")
        self.assertEqual(form.fields["published_year"].label, "Рік видання")
        self.assertEqual(form.fields["cover_image"].label, "Обкладинка")
        self.assertEqual(form.fields["cover_url"].label, "Посилання")
        self.assertEqual(form.fields["is_favorite"].label, "Додати в обране")

    def test_book_form_published_year_uses_text_input_without_spinner(self):
        form = BookForm()
        widget = form.fields["published_year"].widget

        self.assertEqual(widget.input_type, "text")
        self.assertEqual(widget.attrs["inputmode"], "numeric")
        self.assertEqual(widget.attrs["pattern"], "[0-9]*")


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

    def test_book_form_rejects_start_date_for_wishlist_status(self):
        form = BookForm(
            data={
                "title": "Wishlist Book",
                "author": "Author One",
                "status": Book.Status.WISHLIST,
                "start_date": "2026-01-01",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("start_date", form.errors)
        self.assertIn("Дату початку не можна вказувати для бажанки.", form.errors["start_date"])

    def test_book_form_marks_start_date_as_not_wishlist_field(self):
        user = get_user_model().objects.create_user(username="wishlist-form-reader")

        self.client.force_login(user)
        response = self.client.get(reverse("book_create_manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="wishlist"')
        self.assertContains(response, "Бажанка")
        self.assertContains(response, "data-not-wishlist")
        self.assertContains(response, 'const wishlistValue = "wishlist";')

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

    def test_book_form_rejects_finish_date_before_start_date(self):
        form = BookForm(
            data={
                "title": "Invalid Dates",
                "author": "Author One",
                "status": Book.Status.COMPLETED,
                "start_date": "2026-02-10",
                "finish_date": "2026-02-01",
                "rating": "4",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("finish_date", form.errors)
        self.assertIn("Дата завершення не може бути раніше дати початку.", form.errors["finish_date"])

    def test_book_form_rejects_rating_outside_star_range(self):
        for invalid_rating in ("0", "6", "abc"):
            with self.subTest(invalid_rating=invalid_rating):
                form = BookForm(
                    data={
                        "title": "Invalid Rating",
                        "author": "Author One",
                        "status": Book.Status.COMPLETED,
                        "rating": invalid_rating,
                    },
                )

                self.assertFalse(form.is_valid())
                self.assertIn("rating", form.errors)

    def test_book_form_allows_empty_rating_for_completed_book(self):
        form = BookForm(
            data={
                "title": "No Rating",
                "author": "Author One",
                "status": Book.Status.COMPLETED,
                "rating": "",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["rating"])

    def test_book_form_normalizes_multiple_genres(self):
        form = BookForm(
            data={
                "title": "Multi Genre",
                "author": "Author One",
                "genre": " Fantasy; fantasy, Romance , ",
                "status": Book.Status.PLANNED,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["genre"], "Fantasy, Romance")
        self.assertIn("кілька жанрів", form.fields["genre"].help_text)

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
        self.assertEqual(form.fields["shelves"].widget.__class__.__name__, "CheckboxSelectMultiple")
        self.assertEqual(form.shelf_options, [owner_shelf])
        self.assertEqual(form.selected_shelf_ids, set())
        self.assertIn("зніміть усі позначки", form.fields["shelves"].help_text)

    def test_book_update_page_renders_shelf_checkboxes_without_clear_button(self):
        user = get_user_model().objects.create_user(username="shelf-checkboxes", password="test-pass-123")
        shelf = Shelf.objects.create(user=user, name="Fantasy")
        book = Book.objects.create(
            user=user,
            title="Shelf Checkbox Book",
            author="Author One",
            status=Book.Status.PLANNED,
        )
        book.shelves.add(shelf)

        self.client.force_login(user)
        response = self.client.get(reverse("book_update", args=[book.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="checkbox-fieldset"')
        self.assertContains(response, 'class="shelf-book-picker shelf-picker"')
        self.assertContains(response, 'class="shelf-book-option shelf-option"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'name="shelves"')
        self.assertContains(response, 'checked')
        self.assertContains(response, "Fantasy")
        self.assertContains(response, "Поличка")
        self.assertNotContains(response, "Прибрати всі полички")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".shelf-book-option", css)
        self.assertIn(".shelf-picker", css)
        self.assertIn(".shelf-option", css)

    def test_book_create_page_renders_shelf_picker_like_shelf_books_page(self):
        user = get_user_model().objects.create_user(username="book-create-shelf-picker", password="test-pass-123")
        Shelf.objects.create(user=user, name="Fantasy")

        self.client.force_login(user)
        response = self.client.get(reverse("book_create_manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="shelf-book-picker shelf-picker"')
        self.assertContains(response, 'class="shelf-book-option shelf-option"')
        self.assertContains(response, 'name="shelves"')
        self.assertContains(response, "Fantasy")
        self.assertContains(response, "Поличка")

    def test_book_update_can_clear_all_shelves(self):
        user = get_user_model().objects.create_user(username="clear-shelves", password="test-pass-123")
        shelf = Shelf.objects.create(user=user, name="Fantasy")
        book = Book.objects.create(
            user=user,
            title="Shelf Book",
            author="Author One",
            status=Book.Status.PLANNED,
        )
        book.shelves.add(shelf)

        self.client.force_login(user)
        response = self.client.post(
            reverse("book_update", args=[book.pk]),
            {
                "title": book.title,
                "author": book.author,
                "genre": "",
                "publisher": "",
                "published_year": "",
                "cover_url": "",
                "status": Book.Status.PLANNED,
                "start_date": "",
                "finish_date": "",
                "rating": "",
                "description": "",
            },
        )

        self.assertRedirects(response, reverse("book_detail", args=[book.pk]))
        self.assertEqual(book.shelves.count(), 0)

    def test_book_create_rejects_shelves_from_another_user(self):
        User = get_user_model()
        owner = User.objects.create_user(username="create-shelf-owner", password="test-pass-123")
        other = User.objects.create_user(username="create-shelf-other", password="test-pass-123")
        owner_shelf = Shelf.objects.create(user=owner, name="Owner shelf")
        other_shelf = Shelf.objects.create(user=other, name="Other shelf")

        self.client.force_login(owner)
        response = self.client.post(
            reverse("book_create_manual"),
            {
                "title": "Unsafe Shelf Book",
                "author": "Author One",
                "genre": "",
                "publisher": "",
                "series": "",
                "published_year": "",
                "cover_url": "",
                "status": Book.Status.PLANNED,
                "start_date": "",
                "finish_date": "",
                "rating": "",
                "description": "",
                "shelves": [str(owner_shelf.pk), str(other_shelf.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("немає серед варіантів вибору", response.context["form"].errors["shelves"][0])
        self.assertFalse(Book.objects.filter(title="Unsafe Shelf Book").exists())

    def test_book_update_rejects_shelves_from_another_user(self):
        User = get_user_model()
        owner = User.objects.create_user(username="update-shelf-owner", password="test-pass-123")
        other = User.objects.create_user(username="update-shelf-other", password="test-pass-123")
        owner_shelf = Shelf.objects.create(user=owner, name="Owner shelf")
        other_shelf = Shelf.objects.create(user=other, name="Other shelf")
        book = Book.objects.create(
            user=owner,
            title="Protected Shelf Book",
            author="Author One",
            status=Book.Status.PLANNED,
        )
        book.shelves.add(owner_shelf)

        self.client.force_login(owner)
        response = self.client.post(
            reverse("book_update", args=[book.pk]),
            {
                "title": book.title,
                "author": book.author,
                "genre": "",
                "publisher": "",
                "series": "",
                "published_year": "",
                "cover_url": "",
                "status": Book.Status.PLANNED,
                "start_date": "",
                "finish_date": "",
                "rating": "",
                "description": "",
                "shelves": [str(other_shelf.pk)],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("немає серед варіантів вибору", response.context["form"].errors["shelves"][0])
        self.assertEqual(list(book.shelves.all()), [owner_shelf])

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
            series="Chronicles",
        )
        Book.objects.create(
            user=owner,
            title="Owner Sci-Fi",
            author="Author Two",
            genre="Sci-Fi, Fantasy",
            publisher="Story House",
            series="Saga",
        )
        Book.objects.create(
            user=other,
            title="Other Horror",
            author="Author Three",
            genre="Horror",
            publisher="Other Press",
            series="Hidden Series",
        )

        form = BookForm(user=owner)

        self.assertEqual(form.genre_options, ["Fantasy", "Sci-Fi"])
        self.assertEqual(form.publisher_options, ["Book Press", "Story House"])
        self.assertEqual(form.series_options, ["Chronicles", "Saga"])
        self.assertNotIn("list", form.fields["genre"].widget.attrs)
        self.assertNotIn("list", form.fields["publisher"].widget.attrs)
        self.assertNotIn("list", form.fields["series"].widget.attrs)

    def test_update_page_renders_existing_series_picker(self):
        user = get_user_model().objects.create_user(username="series-picker", password="test-pass-123")
        existing_book = Book.objects.create(
            user=user,
            title="Existing Series Book",
            author="Author One",
            series="The Expanse",
        )
        Book.objects.create(
            user=user,
            title="Editable Book",
            author="Author Two",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("book_update", args=[existing_book.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="series"')
        self.assertContains(response, 'id="series-existing-picker"')
        self.assertContains(response, 'aria-label="Обрати існуючу серію"')
        self.assertContains(response, "The Expanse")

    def test_create_page_renders_empty_form_for_get_request(self):
        user = get_user_model().objects.create_user(
            username="creator",
            password="test-pass-123",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("book_create_manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Додати книгу")
        self.assertContains(response, "Обкладинка")
        self.assertContains(response, "Файл")
        self.assertContains(response, "Посилання")
        self.assertContains(response, 'name="cover_image"')
        self.assertContains(response, 'name="cover_url"')
        self.assertNotContains(response, 'list="genre-options"')
        self.assertNotContains(response, 'list="publisher-options"')
        self.assertNotContains(response, 'list="series-options"')
        self.assertContains(response, 'name="series"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "Поличок ще немає")
        self.assertNotContains(response, "Прибрати всі полички")


    def test_create_page_renders_existing_genre_publisher_and_series_suggestions(self):
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
            series="The Expanse",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("book_create_manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="combined-value-field"')
        self.assertContains(response, 'id="genre-existing-picker"')
        self.assertContains(response, '<option value="Fantasy">Fantasy</option>')
        self.assertContains(response, 'data-fill-field="id_genre"')
        self.assertContains(response, 'data-append-value="true"')
        self.assertContains(response, 'id="publisher-existing-picker"')
        self.assertContains(response, '<option value="Book Press">Book Press</option>')
        self.assertContains(response, 'data-fill-field="id_publisher"')
        self.assertContains(response, 'id="series-existing-picker"')
        self.assertContains(response, '<option value="The Expanse">The Expanse</option>')
        self.assertContains(response, 'data-fill-field="id_series"')
        self.assertContains(response, 'aria-label="Обрати існуючу серію"')
        self.assertContains(response, "Жанр: введіть свій або оберіть існуючий")
        self.assertContains(response, "Видавництво: введіть своє або оберіть існуюче")
        self.assertContains(response, "Серія: введіть свою або оберіть існуючу")
        self.assertContains(response, "Існуючі")
        self.assertNotContains(response, "Обрати існуючий жанр</label>")
        self.assertNotContains(response, "Обрати існуюче видавництво</label>")
        self.assertNotContains(response, "Обрати існуючу серію</label>")
        with open("static/css/styles.css", encoding="utf-8") as styles:
            css = styles.read()
        self.assertIn(".combined-value-field", css)
        self.assertIn(".existing-value-select", css)


class StatisticsViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="stats-reader",
            password="test-pass-123",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-stats-reader",
            password="test-pass-123",
        )

    def test_statistics_page_shows_totals_and_completed_books_by_year(self):
        Book.objects.create(
            user=self.user,
            title="Книга 2025",
            author="Автор Один",
            status=Book.Status.COMPLETED,
            finish_date="2025-05-10",
        )
        Book.objects.create(
            user=self.user,
            title="Книга 2024",
            author="Автор Два",
            status=Book.Status.COMPLETED,
            finish_date="2024-03-01",
            is_favorite=True,
        )
        Book.objects.create(
            user=self.user,
            title="Читаю зараз",
            author="Автор Три",
            status=Book.Status.READING,
        )
        Book.objects.create(
            user=self.other_user,
            title="Чужа книга",
            author="Автор Чотири",
            status=Book.Status.COMPLETED,
            finish_date="2025-01-01",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("statistics"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "library/statistics.html")
        self.assertEqual(response.context["total_books"], 3)
        self.assertEqual(response.context["completed_count"], 2)
        self.assertEqual(response.context["reading_count"], 1)
        self.assertEqual(response.context["favorite_count"], 1)
        self.assertContains(response, "Статистика")
        self.assertContains(response, "Усього книг")
        self.assertContains(response, "Прочитано у 2025")
        self.assertContains(response, "Книга 2025")
        self.assertContains(response, "Прочитано у 2024")
        self.assertContains(response, "Книга 2024")
        self.assertContains(response, 'class="is-active" href="/statistics/"')
        self.assertNotContains(response, "Чужа книга")