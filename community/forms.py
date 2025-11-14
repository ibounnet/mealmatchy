from django import forms
from .models import Topic, Review, Comment


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ["title", "description", "cover_image"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "placeholder": "ชื่อหัวข้อ",
            }),
            "description": forms.Textarea(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "rows": 4,
                "placeholder": "รายละเอียดหัวข้อ (อธิบายหัวข้อที่จะพูดคุย)",
            }),
            "cover_image": forms.ClearableFileInput(attrs={
                "class": "block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 "
                         "file:rounded-xl file:border-0 file:text-sm file:font-semibold "
                         "file:bg-primary file:text-white hover:file:bg-primary-dark",
            }),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        # ต้องตรงกับ models.Review
        fields = ["title", "price", "rating", "body", "image"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "placeholder": "ชื่อรีวิว (เช่น เมนูนี้อร่อยมาก)",
            }),
            "price": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "min": 0,
            }),
            "rating": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "min": 1,
                "max": 5,
            }),
            "body": forms.Textarea(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "rows": 5,
                "placeholder": "เล่ารายละเอียดรีวิว เช่น รสชาติ บรรยากาศ การบริการ ฯลฯ",
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 "
                         "file:rounded-xl file:border-0 file:text-sm file:font-semibold "
                         "file:bg-primary file:text-white hover:file:bg-primary-dark",
            }),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        # ใช้ field 'message' ให้ตรงกับ models.Comment
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary",
                "rows": 2,
                "placeholder": "แสดงความคิดเห็น...",
            }),
        }
