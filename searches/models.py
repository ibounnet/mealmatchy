from django.db import models
from django.contrib.auth.models import User


class SearchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="search_histories")

    # หน้า/พาธที่ค้น เช่น /menus/ หรือ /plan/summary/
    path = models.CharField(max_length=255, blank=True, default="")

    # คำค้นหลัก
    keyword = models.CharField(max_length=255, blank=True, default="")

    # ตัวกรองทั้งหมด เก็บเป็น JSON
    filters_json = models.JSONField(default=dict, blank=True)

    # จำนวนผลลัพธ์ที่เจอ
    result_count = models.PositiveIntegerField(default=0)

    # ถ้าค้นซ้ำแบบเดิมติดกัน ให้ increment ตรงนี้แทนการสร้าง record ใหม่รัวๆ
    count = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.keyword} ({self.path})"
