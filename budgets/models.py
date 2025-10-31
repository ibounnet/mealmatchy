from django.db import models
from django.contrib.auth.models import User


class MealPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mealplans')
    start_date = models.DateField()
    days = models.PositiveIntegerField(default=1)
    budget_per_day = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Plan#{self.pk} {self.user.username} {self.start_date} ({self.days}d)'


class DailyBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_budgets')
    date = models.DateField()
    amount = models.PositiveIntegerField(default=0)
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name='daily_budgets',
                             null=True, blank=True)

    class Meta:
        unique_together = ('user', 'date', 'plan')
        ordering = ['date']

    def __str__(self):
        pid = self.plan_id or '-'
        return f"{self.user.username} {self.date} - {self.amount}฿ (plan {pid})"


class BudgetSpend(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budget_spends')
    date = models.DateField()
    amount = models.PositiveIntegerField()
    menu = models.ForeignKey('menus.Menu', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='budget_spends')
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name='spends',
                             null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        src = self.menu.name if self.menu else (self.note or "spend")
        pid = self.plan_id or '-'
        return f"{self.user.username} {self.date}: -{self.amount}฿ ({src}) [plan {pid}]"


class MealItem(models.Model):
    MEAL_CHOICES = [
        ('breakfast', 'มื้อเช้า'),
        ('lunch', 'มื้อเที่ยง'),
        ('dinner', 'มื้อเย็น'),
    ]
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name='items')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meal_items')
    date = models.DateField()
    menu = models.ForeignKey('menus.Menu', on_delete=models.CASCADE, related_name='meal_items')
    meal_type = models.CharField(max_length=20, choices=MEAL_CHOICES, default='lunch')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'meal_type']

    def __str__(self):
        return f"{self.user.username} {self.date} {self.meal_type}: {self.menu.name}"
