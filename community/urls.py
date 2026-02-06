# community/urls.py
from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    path("", views.topic_list, name="topic_list"),

    # topic CRUD
    path("topic/add/", views.topic_add, name="topic_add"),
    path("topic/<int:pk>/", views.topic_detail, name="topic_detail"),
    path("topic/<int:pk>/edit/", views.topic_edit, name="topic_edit"),
    path("topic/<int:pk>/delete/", views.topic_delete, name="topic_delete"),

    # review
    path("topic/<int:pk>/review/add/", views.review_add, name="review_add"),
    path("review/<int:pk>/edit/", views.review_edit, name="review_edit"),
    path("review/<int:pk>/delete/", views.review_delete, name="review_delete"),
    path("review/<int:pk>/like/", views.review_like_toggle, name="review_like"),

    # comment
    path("review/<int:pk>/comment/add/", views.comment_add, name="comment_add"),
    path("comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),

    # moderation (staff) — จัดการโดย “ลบ”
    path("moderation/topics/", views.topic_moderation_list, name="topic_moderation_list"),
    path("moderation/topic/<int:pk>/delete/", views.topic_moderation_delete, name="topic_moderation_delete"),

    path("moderation/reviews/", views.review_moderation_list, name="review_moderation_list"),
    path("moderation/review/<int:pk>/delete/", views.review_moderation_delete, name="review_moderation_delete"),
]
