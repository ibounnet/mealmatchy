from django.db import models
from django.contrib.auth.models import User
from menus.models import Menu

class Plan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    days = models.PositiveIntegerField(default=1)
    budget = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Plan {self.id} by {self.user.username}"

class PlanItem(models.Model):
    plan = models.ForeignKey(Plan, related_name="items", on_delete=models.CASCADE)
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE)
    day = models.PositiveIntegerField()

    def __str__(self):
        return f"Day {self.day} - {self.menu.name}"
