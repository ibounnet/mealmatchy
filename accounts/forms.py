# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Profile

BASE = 'w-full rounded-xl border border-gray-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent'

class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': BASE, 'placeholder': 'ชื่อผู้ใช้'})
        self.fields['password'].widget.attrs.update({'class': BASE, 'placeholder': 'รหัสผ่าน'})

class CustomUserCreationForm(UserCreationForm):
    # อนุญาตชื่อผู้ใช้ภาษาไทย โดยไม่ใช้ validators เดิม
    username = forms.CharField(
        label='ชื่อผู้ใช้', max_length=150, help_text='', validators=[],
        widget=forms.TextInput(attrs={'class': BASE, 'placeholder': 'ชื่อผู้ใช้ (พิมพ์ไทยได้)'})
    )
    first_name = forms.CharField(required=True, label='ชื่อ', widget=forms.TextInput(attrs={'class': BASE}))
    last_name  = forms.CharField(required=True, label='นามสกุล', widget=forms.TextInput(attrs={'class': BASE}))
    email      = forms.EmailField(required=True, label='อีเมล', widget=forms.EmailInput(attrs={'class': BASE}))

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError('กรุณากรอกชื่อผู้ใช้')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('ชื่อผู้ใช้นี้ถูกใช้แล้ว')
        return username

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label='อีเมล')
    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].widget.attrs.update({'class': BASE})

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model  = Profile
        fields = ['bio', 'profile_picture']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'bio' in self.fields:
            self.fields['bio'].widget.attrs.update({'class': BASE, 'rows': 3, 'placeholder': 'แนะนำตัวสั้น ๆ'})
        if 'profile_picture' in self.fields:
            self.fields['profile_picture'].widget.attrs.update({'class': 'block w-full text-sm text-gray-700'})
