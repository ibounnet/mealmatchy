from django import forms
from .models import Restaurant

class RestaurantForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = ['name', 'description', 'location', 'image']
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full px-4 py-2 rounded-xl bg-gray-50 ring-1 ring-gray-200 focus:outline-none focus:ring-2 focus:ring-primary",
                "placeholder": "เช่น ร้านลุงหนวด",
            }),
            "location": forms.TextInput(attrs={
                "class": "w-full px-4 py-2 rounded-xl bg-gray-50 ring-1 ring-gray-200 focus:outline-none focus:ring-2 focus:ring-primary",
                "placeholder": "เช่น เชียงใหม่ / กรุงเทพฯ",
            }),
            "description": forms.Textarea(attrs={
                "class": "w-full px-4 py-2 rounded-xl bg-gray-50 ring-1 ring-gray-200 focus:outline-none focus:ring-2 focus:ring-primary",
                "rows": 4,
                "placeholder": "เล่ารายละเอียดร้านโดยย่อ",
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "w-full px-4 py-2 rounded-xl bg-white ring-1 ring-gray-200 focus:outline-none focus:ring-2 focus:ring-primary",
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("กรุณากรอกชื่อร้าน")
        return name

    def clean_location(self):
        location = self.cleaned_data.get('location', '').strip()
        if not location:
            raise forms.ValidationError("กรุณากรอกที่ตั้งร้าน")
        return location
