# plan/urls.py
from django.urls import path
from . import views

app_name = "plan"

urlpatterns = [
    path("start/", views.plan_start_view, name="start"),
    path("summary/", views.mealplan_summary, name="summary"),
]
