# menus/forms.py
from django import forms
from .models import Menu


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        # ไม่เอา calories แล้ว และไม่ให้เลือก restaurant จากฟอร์ม
        fields = ["name", "description", "price", "image"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full px-3 py-2 rounded-xl ring-1 ring-gray-200",
                "placeholder": "เช่น กระเพราหมูกรอบ ไข่ดาว"
            }),
            "description": forms.Textarea(attrs={
                "class": "w-full px-3 py-2 rounded-xl ring-1 ring-gray-200",
                "rows": 3,
                "placeholder": "รายละเอียดเพิ่มเติม (ไม่บังคับ)"
            }),
            "price": forms.NumberInput(attrs={
                "class": "w-full px-3 py-2 rounded-xl ring-1 ring-gray-200",
                "min": 0,
                "step": "1",
                "placeholder": "ราคาต่อจาน (บาท)"
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "w-full text-sm"
            }),
        }
