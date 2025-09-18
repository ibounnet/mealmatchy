from django import forms
from .models import Restaurant

class RestaurantForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        # ฟอร์มฝั่งผู้ใช้: ไม่ให้แก้ is_active
        fields = ['name', 'description', 'location', 'image']

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
