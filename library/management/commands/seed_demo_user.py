from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from library.models import Book, Note, Shelf


DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo12345"
DEMO_EMAIL = "demo@booknest.local"


class Command(BaseCommand):
    help = "Create or refresh a demo user with sample BookNest data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=DEMO_USERNAME,
            help=f"Demo username to create or update. Default: {DEMO_USERNAME}",
        )
        parser.add_argument(
            "--password",
            default=DEMO_PASSWORD,
            help=f"Demo password to set. Default: {DEMO_PASSWORD}",
        )
        parser.add_argument(
            "--email",
            default=DEMO_EMAIL,
            help=f"Demo email to set. Default: {DEMO_EMAIL}",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]
        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.set_password(password)
        user.save(update_fields=["email", "password"])

        fantasy_shelf, _ = Shelf.objects.get_or_create(user=user, name="Фентезі")
        planned_shelf, _ = Shelf.objects.get_or_create(user=user, name="На літо")

        dune, _ = Book.objects.update_or_create(
            user=user,
            title="Дюна",
            author="Френк Герберт",
            defaults={
                "genre": "Наукова фантастика",
                "publisher": "КСД",
                "series": "Хроніки Дюни",
                "status": Book.Status.READING,
                "is_favorite": True,
                "description": "Класична історія про Арракіс, політику, пророцтва та силу вибору.",
                "published_year": 1965,
            },
        )
        dune.shelves.set([fantasy_shelf])

        hobbit, _ = Book.objects.update_or_create(
            user=user,
            title="Гобіт",
            author="Дж. Р. Р. Толкін",
            defaults={
                "genre": "Фентезі",
                "publisher": "Астролябія",
                "status": Book.Status.COMPLETED,
                "rating": 5,
                "is_favorite": True,
                "description": "Затишна пригода Більбо Торбина й подорож до Самотньої гори.",
                "published_year": 1937,
            },
        )
        hobbit.shelves.set([fantasy_shelf])

        martian, _ = Book.objects.update_or_create(
            user=user,
            title="Марсіянин",
            author="Енді Вейр",
            defaults={
                "genre": "Наукова фантастика",
                "publisher": "КМ-Букс",
                "status": Book.Status.WISHLIST,
                "description": "Оптимістична survival-історія про астронавта, який залишився на Марсі.",
                "published_year": 2011,
            },
        )
        martian.shelves.set([planned_shelf])

        Note.objects.update_or_create(
            user=user,
            book=dune,
            title="Тема для обговорення",
            defaults={
                "content": "Звернути увагу, як змінюється Пол після знайомства з фріменами.",
                "page_number": 128,
            },
        )
        Note.objects.update_or_create(
            user=user,
            book=None,
            title="Ідея для наступної полиці",
            defaults={
                "content": "Створити полицю для коротких книг, які можна прочитати за вихідні.",
                "page_number": None,
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} demo user '{username}' with password '{password}'."
            )
        )