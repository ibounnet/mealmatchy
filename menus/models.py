# menus/models.py
from django.db import models
from django.contrib.auth.models import User
from restaurants.models import Restaurant
import os, uuid

def menu_image_path(instance, filename):
    base, ext = os.path.splitext(filename)
    return os.path.join('menu_images', f"{uuid.uuid4()}{ext}")

class Menu(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='menus',
        null=True, blank=True
    )

    restaurant_name = models.CharField(max_length=200, blank=True, default="")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    image = models.ImageField(upload_to=menu_image_path, blank=True, null=True)

    ingredients = models.TextField(blank=True, default="")
    is_halal = models.BooleanField(default=False)
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    no_alcohol = models.BooleanField(default=True)

    class Status(models.TextChoices):
        PENDING = "P", "Pending"
        APPROVED = "A", "Approved"
        REJECTED = "R", "Rejected"

    status = models.CharField(
        max_length=1, choices=Status.choices, default=Status.PENDING
    )

    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_menus'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
