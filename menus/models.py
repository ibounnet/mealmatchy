from django.db import models
from django.contrib.auth.models import User
import os
from uuid import uuid4

def menu_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4()}.{ext}"
    return os.path.join('menu_images', filename)

class Menu(models.Model):
    # ร้านอาหาร: ให้พิมพ์ชื่อเอง
    restaurant_name = models.CharField(max_length=200)

    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price       = models.PositiveIntegerField(default=0)  # จำนวนเต็ม เช่น 50
    image       = models.ImageField(upload_to=menu_image_path, blank=True, null=True)

    # ใครเป็นคนเพิ่ม (อาจเป็น None ถ้ามีข้อมูลเก่าหรือ import)
    created_by  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='menus')
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
