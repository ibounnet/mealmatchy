from django.contrib import admin
from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "keyword", "path", "result_count", "count", "updated_at")
    list_filter = ("path", "updated_at")
    search_fields = ("keyword", "user__username")
    ordering = ("-updated_at",)
