from django import forms
from .models import Recipe

BASE = 'w-full rounded-xl border border-gray-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent'
FILE = 'block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary file:text-white hover:file:bg-primary-dark'

class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = [
            'title', 'restaurant_name', 'description',
            'ingredients', 'steps',
            'servings', 'prep_minutes', 'cook_minutes',
            'image'
        ]
        widgets = {
            'title':           forms.TextInput(attrs={'class': BASE, 'placeholder': 'ชื่อสูตร'}),
            'restaurant_name': forms.TextInput(attrs={'class': BASE, 'placeholder': 'ชื่อร้าน/แหล่งที่มา (ไม่บังคับ)'}),
            'description':     forms.Textarea(attrs={'class': BASE, 'rows': 2, 'placeholder': 'คำอธิบายสั้น ๆ'}),
            'ingredients':     forms.Textarea(attrs={'class': BASE, 'rows': 6, 'placeholder': 'พิมพ์ส่วนผสม บรรทัดละ 1 รายการ'}),
            'steps':           forms.Textarea(attrs={'class': BASE, 'rows': 8, 'placeholder': 'พิมพ์วิธีทำ บรรทัดละ 1 ขั้นตอน'}),
            'servings':        forms.NumberInput(attrs={'class': BASE, 'min': 1, 'step': 1}),
            'prep_minutes':    forms.NumberInput(attrs={'class': BASE, 'min': 0, 'step': 1}),
            'cook_minutes':    forms.NumberInput(attrs={'class': BASE, 'min': 0, 'step': 1}),
            'image':           forms.ClearableFileInput(attrs={'class': FILE}),
        }
