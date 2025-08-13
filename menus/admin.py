from django.contrib import admin
from .models import Menu

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'restaurant_name', 'price', 'created_by', 'created_at')
    list_filter = ('created_by', 'created_at')
    search_fields = ('name', 'restaurant_name', 'created_by__username', 'created_by__first_name', 'created_by__last_name')
