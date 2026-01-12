# recipes/forms.py
from django import forms
from .models import Recipe, UserCookingCostSetting

BASE = (
    "w-full rounded-xl border border-gray-200 px-3 py-2 "
    "focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
)
SELECT = (
    "w-full rounded-xl border border-gray-200 px-3 py-2 bg-white "
    "focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
)
FILE = (
    "block w-full text-sm text-gray-700 "
    "file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 "
    "file:bg-orange-500 file:text-white hover:file:bg-orange-600"
)

STOVE_CHOICES = [
    ("", "ใช้ค่าเริ่มต้นจากบัญชี"),
    ("electric", "เตาไฟฟ้า"),
    ("induction", "เตาแม่เหล็กไฟฟ้า (Induction)"),
    ("gas", "เตาแก๊ส"),
]

class RecipeForm(forms.ModelForm):
    STOVE_CHOICES = [
        ("", "ไม่เลือก (ใช้ค่าจากบัญชี)"),
        ("electric", "เตาไฟฟ้า"),
        ("induction", "เตาแม่เหล็กไฟฟ้า (Induction)"),
        ("gas", "เตาแก๊ส"),
    ]

    stove_type = forms.ChoiceField(
        required=False,
        choices=STOVE_CHOICES,
        widget=forms.Select(attrs={"class": BASE}),
        label="เตาที่ใช้กับสูตรนี้",
    )

    ingredients = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": BASE,
                "rows": 6,
                "placeholder": "ถ้าคุณใช้ตารางวัตถุดิบด้านบน ช่องนี้ไม่จำเป็นต้องกรอก (เว้นว่างได้)",
            }
        ),
        label="ส่วนผสม (ข้อความเดิม)",
    )

    servings = forms.IntegerField(
        required=False, min_value=1,
        widget=forms.NumberInput(attrs={"class": BASE, "min": 1, "step": 1}),
        label="จำนวนที่เสิร์ฟ",
    )
    prep_minutes = forms.IntegerField(
        required=False, min_value=0,
        widget=forms.NumberInput(attrs={"class": BASE, "min": 0, "step": 1}),
        label="เวลาตระเตรียม (นาที)",
    )
    cook_minutes = forms.IntegerField(
        required=False, min_value=0,
        widget=forms.NumberInput(attrs={"class": BASE, "min": 0, "step": 1}),
        label="เวลาในการปรุง (นาที)",
    )

    class Meta:
        model = Recipe
        fields = [
            "title",
            "restaurant_name",
            "description",
            "servings",
            "prep_minutes",
            "cook_minutes",
            "stove_type",   # ✅ สำคัญ
            "image",
            "ingredients",
            "steps",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": BASE, "placeholder": "ชื่อสูตรอาหาร เช่น ผัดกะเพราหมูกรอบ"}),
            "restaurant_name": forms.TextInput(attrs={"class": BASE, "placeholder": "ชื่อร้าน/แหล่งที่มา (ไม่บังคับ)"}),
            "description": forms.Textarea(attrs={"class": BASE, "rows": 2, "placeholder": "คำอธิบายสั้น ๆ เกี่ยวกับสูตรนี้"}),
            "steps": forms.Textarea(attrs={"class": BASE, "rows": 8, "placeholder": "พิมพ์วิธีทำ บรรทัดละ 1 ขั้นตอน"}),
            "image": forms.ClearableFileInput(attrs={"class": FILE}),
        }

    def clean_servings(self):
        v = self.cleaned_data.get("servings")
        return 1 if v in (None, "") else v

    def clean_prep_minutes(self):
        v = self.cleaned_data.get("prep_minutes")
        return 0 if v in (None, "") else v

    def clean_cook_minutes(self):
        v = self.cleaned_data.get("cook_minutes")
        return 0 if v in (None, "") else v


class UserCookingCostSettingForm(forms.ModelForm):
    class Meta:
        model = UserCookingCostSetting
        fields = [
            "mode",
            "seasoning_cost_per_serving",
            "overhead_cost_per_serving",
            "default_stove_type",
            "default_cook_minutes",
            "electricity_rate_per_kwh",
            "electric_power_watt",
            "induction_power_watt",
            "gas_cost_per_hour",
        ]
        widgets = {
            "mode": forms.Select(attrs={"class": SELECT}),
            "seasoning_cost_per_serving": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "0.01"}),
            "overhead_cost_per_serving": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "0.01"}),
            "default_stove_type": forms.Select(attrs={"class": SELECT}),
            "default_cook_minutes": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "1"}),
            "electricity_rate_per_kwh": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "0.01"}),
            "electric_power_watt": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "1"}),
            "induction_power_watt": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "1"}),
            "gas_cost_per_hour": forms.NumberInput(attrs={"class": BASE, "min": 0, "step": "0.01"}),
        }
