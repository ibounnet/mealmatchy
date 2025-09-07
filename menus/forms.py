from django import forms
from .models import Menu

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = [
            'restaurant_name', 'name', 'description', 'price', 'image',
            'ingredients', 'is_halal', 'is_vegetarian', 'is_vegan', 'no_alcohol'
        ]
        widgets = {
            'ingredients': forms.Textarea(attrs={'rows': 2, 'placeholder': 'เช่น: กะเพรา, หมู, พริก, กระเทียม, ไข่'}),
        }
        labels = {
            'ingredients': 'ส่วนผสม (คีย์เวิร์ด คั่นด้วย , )',
            'is_halal': 'ฮาลาล',
            'is_vegetarian': 'มังสวิรัติ',
            'is_vegan': 'วีแกน',
            'no_alcohol': 'ไม่มีแอลกอฮอล์',
        }
