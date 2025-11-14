from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


def topic_image_path(instance, filename):
    return f"community/topics/{instance.id}/{filename}"


def review_image_path(instance, filename):
    return f"community/reviews/{instance.id}/{filename}"


class Topic(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to=topic_image_path, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Review(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    topic = models.ForeignKey(Topic, related_name="reviews", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    body = models.TextField()
    price = models.PositiveIntegerField(default=0)
    rating = models.PositiveIntegerField(default=5)
    image = models.ImageField(upload_to=review_image_path, blank=True, null=True)

    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title



class Comment(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="comments"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_comments"
    )
    message = models.TextField()          # ← ใช้ชื่อ message (ไม่ใช่ text)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user} on {self.review}"
    

class Like(models.Model):
    review = models.ForeignKey(Review, related_name="likes", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("review", "user")
