from django.urls import path

from recipes import api
from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.recipe_list, name="list"),
    path("add/", views.add_recipe, name="add"),
    path("<int:pk>/", views.recipe_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_recipe, name="edit"),
    path("<int:pk>/delete/", views.delete_recipe, name="delete"),

    path("cost-settings/", views.cost_settings, name="cost_settings"),

    # API: ingredient price per gram
    path("api/ingredient/<int:pk>/", api.ingredient_detail, name="ingredient_detail"),
    path("api/ingredient/create/", api.ingredient_create, name="ingredient_create"),
]
