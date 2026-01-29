# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


def user_profile_path(instance, filename):
    return f"profile_pics/user_{instance.user.id}/{filename}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to=user_profile_path, blank=True, null=True
    )

    def __str__(self):
        return self.user.username if self.user_id else "Profile"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    ทำให้แน่ใจว่า User ทุกคนมี Profile เสมอ
    - created=True: สร้าง Profile ใหม่
    - created=False: ถ้าไม่มี Profile ให้สร้าง (กันข้อมูลเก่าหรือ import user)
    """
    if created:
        Profile.objects.create(user=instance)
        return

    # สำหรับ user ที่มีอยู่แล้ว แต่ไม่มี profile (กันพัง)
    Profile.objects.get_or_create(user=instance)
