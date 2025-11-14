from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    path("", views.topic_list, name="topic_list"),
    path("topic/add/", views.topic_add, name="topic_add"),
    path("topic/<int:pk>/edit/", views.topic_edit, name="topic_edit"),

    path("topic/<int:pk>/", views.topic_detail, name="topic_detail"),

    path("topic/<int:pk>/review/add/", views.review_add, name="review_add"),
    path("review/<int:pk>/edit/", views.review_edit, name="review_edit"),
    path("review/<int:pk>/delete/", views.review_delete, name="review_delete"),
    path("review/<int:pk>/like/", views.review_like_toggle, name="review_like"),

    path("review/<int:pk>/comment/add/", views.comment_add, name="comment_add"),
    path("comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
]
