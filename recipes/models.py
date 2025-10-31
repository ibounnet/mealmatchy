from django.db import models
from django.contrib.auth.models import User
from uuid import uuid4
import os

def recipe_image_path(instance, filename):
    ext = filename.split('.')[-1]
    return os.path.join('recipe_images', f'{uuid4()}.{ext}')

class Recipe(models.Model):
    title = models.CharField(max_length=200)
    restaurant_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    ingredients = models.TextField()     # แยกบรรทัดด้วย \n
    steps = models.TextField()           # แยกบรรทัดด้วย \n
    servings = models.PositiveIntegerField(default=1)
    prep_minutes = models.PositiveIntegerField(default=0)
    cook_minutes = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to=recipe_image_path, blank=True, null=True)

    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='recipes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def total_minutes(self):
        return (self.prep_minutes or 0) + (self.cook_minutes or 0)
