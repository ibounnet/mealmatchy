# recipes/forms.py
from django import forms
from .models import Recipe

BASE = (
    "w-full rounded-xl border border-gray-200 px-3 py-2 "
    "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
)
FILE = (
    "block w-full text-sm text-gray-700 "
    "file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 "
    "file:bg-primary file:text-white hover:file:bg-primary-dark"
)


class RecipeForm(forms.ModelForm):
    # กำหนด field ตัวเลขเองเพื่อควบคุม required / default
    servings = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': BASE, 'min': 1, 'step': 1}),
        label="จำนวนที่เสิร์ฟ",
    )
    prep_minutes = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': BASE, 'min': 0, 'step': 1}),
        label="เวลาตระเตรียม (นาที)",
    )
    cook_minutes = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': BASE, 'min': 0, 'step': 1}),
        label="เวลาในการปรุง (นาที)",
    )

    class Meta:
        model = Recipe
        fields = [
            'title',
            'restaurant_name',
            'description',
            'ingredients',
            'steps',
            'servings',
            'prep_minutes',
            'cook_minutes',
            'image',
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={'class': BASE, 'placeholder': 'ชื่อสูตรอาหาร เช่น ผัดกะเพราหมูกรอบ'}
            ),
            'restaurant_name': forms.TextInput(
                attrs={'class': BASE, 'placeholder': 'ชื่อร้าน/แหล่งที่มา (ไม่บังคับ)'}
            ),
            'description': forms.Textarea(
                attrs={'class': BASE, 'rows': 2, 'placeholder': 'คำอธิบายสั้น ๆ เกี่ยวกับสูตรนี้'}
            ),
            'ingredients': forms.Textarea(
                attrs={
                    'class': BASE,
                    'rows': 6,
                    'placeholder': 'พิมพ์ส่วนผสม บรรทัดละ 1 รายการ',
                }
            ),
            'steps': forms.Textarea(
                attrs={
                    'class': BASE,
                    'rows': 8,
                    'placeholder': 'พิมพ์วิธีทำ บรรทัดละ 1 ขั้นตอน',
                }
            ),
            'image': forms.ClearableFileInput(attrs={'class': FILE}),
        }

    # ถ้าเว้นว่าง ให้ใช้ค่า default / 0 แทน ไม่ให้ฟอร์ม invalid

    def clean_servings(self):
        value = self.cleaned_data.get('servings')
        if value in (None, ''):
            return 1  # default 1 ที่เสิร์ฟ
        return value

    def clean_prep_minutes(self):
        value = self.cleaned_data.get('prep_minutes')
        if value in (None, ''):
            return 0
        return value

    def clean_cook_minutes(self):
        value = self.cleaned_data.get('cook_minutes')
        if value in (None, ''):
            return 0
        return value
