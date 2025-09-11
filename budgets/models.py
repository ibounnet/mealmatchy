# budgets/models.py
from django.db import models
from django.contrib.auth.models import User

"""
แนวคิด:
- MealPlan  = 1 แผน/ครั้ง (วันเริ่ม, จำนวนวัน, งบ/วัน, เจ้าของ)
- DailyBudget และ BudgetSpend ผูกกับ plan เสมอ
- unique_together ของ DailyBudget ใช้ (user, date, plan) เพื่อไม่ให้วันเดียวกันชนกันข้ามแผน
"""

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
    amount = models.PositiveIntegerField(default=0)  # บาท
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
    amount = models.PositiveIntegerField()  # บาท
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
