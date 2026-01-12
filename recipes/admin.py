from django.contrib import admin
from django.db import models
from .models import Recipe, RecipeIngredient


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    raw_id_fields = ("ingredient",)
    fields = ("ingredient", "quantity_grams", "price_per_gram_snapshot", "cost_snapshot", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "servings", "created_by", "created_at")
    search_fields = ("title", "description", "ingredients", "steps", "restaurant_name")
    list_filter = ("created_at", "created_by")
    ordering = ("-created_at",)
    inlines = [RecipeIngredientInline]

    formfield_overrides = {
        models.TextField: {"widget": admin.widgets.AdminTextareaWidget(attrs={"rows": 4, "cols": 80})}
    }

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user
        return super().save_model(request, obj, form, change)



@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("id", "recipe", "ingredient", "quantity_grams", "price_per_gram_snapshot", "cost_snapshot", "created_at")
    search_fields = ("recipe__title", "ingredient__name")
    list_filter = ("created_at",)
