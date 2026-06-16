from django.db.models import Count

from .models import Shelf

SERIES_SHELF_PREFIX = 'Серія: '


def format_series_shelf_name(series):
    return f'{SERIES_SHELF_PREFIX}"{series.strip()}"'


def cleanup_empty_series_shelves(user):
    Shelf.objects.filter(user=user, is_auto_series=True).annotate(
        book_count=Count("books"),
    ).filter(book_count=0).delete()


def sync_book_series_shelf(book):
    series = book.series.strip()
    if not series:
        cleanup_empty_series_shelves(book.user)
        return None

    shelf, _ = Shelf.objects.get_or_create(
        user=book.user,
        name=format_series_shelf_name(series),
        defaults={
            "series": series,
            "is_auto_series": True,
        },
    )

    changed_fields = []
    if shelf.series != series:
        shelf.series = series
        changed_fields.append("series")
    if not shelf.is_auto_series:
        shelf.is_auto_series = True
        changed_fields.append("is_auto_series")
    if changed_fields:
        shelf.save(update_fields=changed_fields)

    book.shelves.add(shelf)
    cleanup_empty_series_shelves(book.user)
    return shelf