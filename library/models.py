from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Book(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        READING = 'reading', 'Reading'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        API = 'api', 'API'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name = 'books',
    )

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    genre = models.CharField(max_length=100, blank=True)
    publisher = models.CharField(max_length=150, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    is_favorite = models.BooleanField(default=False)

    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    start_date = models.DateField(null=True, blank=True)
    finish_date = models.DateField(null=True, blank=True)

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    external_id = models.CharField(max_length=120, blank=True)
    cover_url = models.URLField(blank=True)
    publisher_year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    shelves = models.ManyToManyField(
        'Shelf',
        blank=True,
        related_name='books',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.title} - {self.author}'


class Shelf(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name = 'shelves',
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name = 'notes',
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name = 'notes',
    )

    content = models.TextField()
    page_number = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Note for {self.book.title}'