# restaurants/models.py
from django.db import models
from django.contrib.auth.models import User
import os
from uuid import uuid4


def restaurant_image_path(instance, filename):
    """กำหนด path สำหรับเก็บรูปภาพร้าน"""
    ext = filename.split('.')[-1].lower()
    return os.path.join('restaurants', f'{uuid4()}.{ext}')


class Restaurant(models.Model):
    name = models.CharField(max_length=120, unique=True)  # ชื่อร้าน (ใช้ join lookup ได้)
    description = models.TextField(blank=True)  # รายละเอียดร้าน
    location = models.CharField(max_length=120, blank=True, default="")  # ที่อยู่ / สถานที่
    image = models.ImageField(upload_to=restaurant_image_path, blank=True, null=True)  # รูปภาพ

    # False = ยังไม่อนุมัติ (รอแอดมิน), True = อนุมัติแล้ว
    is_active = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='requested_restaurants'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # ถ้าอยากเรียงตามชื่อก็เปลี่ยนเป็น ['name']

    def __str__(self):
        return self.name
