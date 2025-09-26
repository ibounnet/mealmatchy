# restaurants/admin.py
from django.contrib import admin
from .models import Restaurant

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active', 'created_by', 'created_at')
    search_fields = ('name', 'location')
    list_filter = ('is_active',)
