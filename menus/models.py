from django.db import models
from django.contrib.auth.models import User
import os, uuid

def menu_image_path(instance, filename):
    base, ext = os.path.splitext(filename)
    return os.path.join('menu_images', f"{uuid.uuid4()}{ext}")

class Menu(models.Model):
    restaurant_name = models.CharField(max_length=200, blank=True, default="")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to=menu_image_path, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # NEW: ข้อมูลช่วยกรองตามข้อจำกัด
    ingredients = models.TextField(  # เก็บคีย์เวิร์ดส่วนผสมคั่นด้วยคอมมา
        blank=True,
        help_text="เช่น: กะเพรา, หมู, พริก, กระเทียม, ไข่"
    )
    is_halal = models.BooleanField(default=False)
    is_vegetarian = models.BooleanField(default=False)  # มังสวิรัติ (มีไข่/นมได้)
    is_vegan = models.BooleanField(default=False)       # วีแกน (ไม่เอาไข่/นม)
    no_alcohol = models.BooleanField(default=True)      # ไม่มีแอลกอฮอล์ในวัตถุดิบ/ซอส

    def __str__(self):
        return self.name
