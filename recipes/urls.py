from django.urls import path
from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.recipe_list, name="list"),
    path("add/", views.add_recipe, name="add"),
    path("<int:pk>/edit/", views.edit_recipe, name="edit"),
    path("<int:pk>/delete/", views.delete_recipe, name="delete"),
]
