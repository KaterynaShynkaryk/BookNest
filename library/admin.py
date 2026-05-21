from django.contrib import admin
from .models import Book, Note, Shelf


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'user', 'status', 'is_favorite', 'created_at', 'updated_at')
    list_filter = ('status', 'is_favorite', 'genre', 'publisher')
    search_fields = ('title', 'author', 'publisher')
    filter_horizontal = ('shelves',)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'page_number', 'created_at')
    search_fields = ('book__title', 'content')
    list_filter = ('created_at',)


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    search_fields = ('name',)