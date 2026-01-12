from django.urls import path
from . import views

app_name = "searches"

urlpatterns = [
    path("search/", views.search, name="search"),
    path("history/", views.history_list, name="history_list"),
    path("history/<int:pk>/delete/", views.history_delete, name="history_delete"),
    path("history/clear/", views.history_clear, name="history_clear"),
    path("history/<int:pk>/rerun/", views.history_rerun, name="history_rerun"),
]
