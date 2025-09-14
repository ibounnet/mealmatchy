# menus/forms.py
from django import forms
from .models import Menu

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = [
            'restaurant',
            'restaurant_name', 'name', 'description', 'price', 'image',
            'ingredients', 'is_halal', 'is_vegetarian', 'is_vegan', 'no_alcohol',
            # ไม่ต้องใส่ status/approved_* ในฟอร์มฝั่งผู้ใช้ (ให้เป็นค่า default/จัดการใน view)
        ]
        widgets = {
            'ingredients': forms.Textarea(attrs={'rows': 2, 'placeholder': 'เช่น: กะเพรา, หมู, พริก, กระเทียม'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
