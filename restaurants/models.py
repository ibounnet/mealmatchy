from django.db import models
from django.contrib.auth.models import User
import os
from uuid import uuid4

def restaurant_image_path(instance, filename):
    ext = filename.split('.')[-1].lower()
    return os.path.join('restaurants', f'{uuid4()}.{ext}')

class Restaurant(models.Model):
    name        = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    location    = models.CharField(max_length=120, blank=True, default="")
    image       = models.ImageField(upload_to=restaurant_image_path, blank=True, null=True)

    # ให้เป็น False โดยค่าเริ่มต้น เพื่อรอ Admin อนุมัติ
    is_active   = models.BooleanField(default=False)

    created_by  = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='requested_restaurants'  # จะใช้ชื่อเดิม created_restaurants ก็ได้
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # อยากเรียงตามชื่อเหมือนเดิม ก็ใช้ ['name'] ได้

    def __str__(self):
        return self.name
