from django.db import models
from django.contrib.auth.models import User
from uuid import uuid4
import os
from restaurants.models import Restaurant

def menu_image_path(instance, filename):
    ext = filename.split('.')[-1]
    return os.path.join('menu_images', f'{uuid4()}.{ext}')

class Menu(models.Model):
    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'รออนุมัติ'
        APPROVED = 'APPROVED', 'อนุมัติแล้ว'
        REJECTED = 'REJECTED', 'ถูกปฏิเสธ'

    restaurant  = models.ForeignKey(
        Restaurant, null=True, blank=True,
        on_delete=models.CASCADE, related_name='menus'
    )

    # เก็บชื่อร้านเผื่อข้อมูลเก่า
    restaurant_name = models.CharField(max_length=100, blank=True)

    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price       = models.PositiveIntegerField(default=0)
    image       = models.ImageField(upload_to=menu_image_path, blank=True, null=True)

    created_by  = models.ForeignKey(User, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='created_menus')
    created_at  = models.DateTimeField(auto_now_add=True)

    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(User, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='approved_menus')
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
