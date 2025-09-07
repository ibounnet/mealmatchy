from django import forms
from .models import DailyBudget

class DailyBudgetForm(forms.ModelForm):
    class Meta:
        model = DailyBudget
        fields = ['date', 'amount']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'rounded-xl border px-3 py-2'}),
            'amount': forms.NumberInput(attrs={'min': 0, 'class': 'rounded-xl border px-3 py-2'}),
        }
        labels = {
            'date': 'วันที่',
            'amount': 'งบ (บาท)',
        }
