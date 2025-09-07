from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from menus.models import Menu


class DailyBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_budgets')
    date = models.DateField()
    amount = models.PositiveIntegerField(default=0)  # หน่วย: บาท

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.user.username} {self.date} - {self.amount}฿"


class BudgetSpend(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budget_spends')
    date = models.DateField()
    amount = models.PositiveIntegerField()  # บาท
    menu = models.ForeignKey(Menu, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='budget_spends')
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        src = self.menu.name if self.menu else (self.note or "spend")
        return f"{self.user.username} {self.date}: -{self.amount}฿ ({src})"
