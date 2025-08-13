from django import forms
from .models import Menu

BASE = 'w-full rounded-xl border border-gray-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent'
FILE = 'block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary file:text-white hover:file:bg-primary-dark'

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ['restaurant_name', 'name', 'description', 'price', 'image']
        widgets = {
            'restaurant_name': forms.TextInput(attrs={'class': BASE, 'placeholder': 'ชื่อร้านอาหาร'}),
            'name':            forms.TextInput(attrs={'class': BASE, 'placeholder': 'ชื่อเมนู'}),
            'description':     forms.Textarea(attrs={'class': BASE, 'rows': 3, 'placeholder': 'รายละเอียด (ไม่บังคับ)'}),
            'price':           forms.NumberInput(attrs={'class': BASE + ' appearance-none', 'step': '1', 'inputmode': 'numeric', 'pattern': r'\d*', 'placeholder': 'เช่น 50'}),
            'image':           forms.ClearableFileInput(attrs={'class': FILE}),
        }
