from django.contrib import admin
from django.db import models
from .models import Recipe

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'servings', 'created_by', 'created_at')
    search_fields = ('title', 'description', 'ingredients', 'steps', 'restaurant_name')
    list_filter = ('created_at', 'created_by')
    ordering = ('-created_at',)

    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 4, 'cols': 80})}
    }

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user
        return super().save_model(request, obj, form, change)
