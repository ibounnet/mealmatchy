# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Profile

BASE = (
    "w-full rounded-xl border border-gray-200 px-3 py-2 "
    "focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
)

FILE_BASE = "block w-full text-sm text-gray-700 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100"


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update(
            {"class": BASE, "placeholder": "ชื่อผู้ใช้"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": BASE, "placeholder": "รหัสผ่าน"}
        )


class CustomUserCreationForm(UserCreationForm):
    # อนุญาตชื่อผู้ใช้ภาษาไทย โดยไม่ใช้ validators เดิม
    username = forms.CharField(
        label="ชื่อผู้ใช้",
        max_length=150,
        help_text="",
        validators=[],
        widget=forms.TextInput(
            attrs={"class": BASE, "placeholder": "ชื่อผู้ใช้ (พิมพ์ไทยได้)"}
        ),
    )
    first_name = forms.CharField(
        required=True, label="ชื่อ", widget=forms.TextInput(attrs={"class": BASE})
    )
    last_name = forms.CharField(
        required=True, label="นามสกุล", widget=forms.TextInput(attrs={"class": BASE})
    )
    email = forms.EmailField(
        required=True, label="อีเมล", widget=forms.EmailInput(attrs={"class": BASE})
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username", "password1", "password2"]

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("กรุณากรอกชื่อผู้ใช้")

        # กันชื่อซ้ำแบบ case-insensitive
        qs = User.objects.filter(username__iexact=username)

        # ถ้าเป็นการแก้ไข user เดิม (เผื่อ reuse form) ให้ไม่ชนตัวเอง
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("ชื่อผู้ใช้นี้ถูกใช้แล้ว")
        return username

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ใส่ class ให้ password fields ด้วย
        if "password1" in self.fields:
            self.fields["password1"].widget.attrs.update(
                {"class": BASE, "placeholder": "รหัสผ่าน"}
            )
        if "password2" in self.fields:
            self.fields["password2"].widget.attrs.update(
                {"class": BASE, "placeholder": "ยืนยันรหัสผ่าน"}
            )


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="อีเมล")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name in self.fields:
            widget = self.fields[name].widget
            widget.attrs.update({"class": BASE})
            # ใส่ placeholder แบบเบา ๆ
            if name == "first_name":
                widget.attrs.setdefault("placeholder", "ชื่อ")
            if name == "last_name":
                widget.attrs.setdefault("placeholder", "นามสกุล")
            if name == "email":
                widget.attrs.setdefault("placeholder", "อีเมล")


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["bio", "profile_picture"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "bio" in self.fields:
            self.fields["bio"].widget.attrs.update(
                {"class": BASE, "placeholder": "แนะนำตัวสั้น ๆ"}
            )

        if "profile_picture" in self.fields:
            self.fields["profile_picture"].required = False
            self.fields["profile_picture"].widget.attrs.update({"class": FILE_BASE})
