# menus/admin.py
from django.contrib import admin, messages
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone

from .models import Menu


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    # คอลัมน์ในหน้า changelist
    list_display = (
        "id", "name", "restaurant", "price",
        "status", "creator", "created_at",
        "approved_by", "approved_at",
        "edit_button",
    )
    list_display_links = ("id", "name")
    ordering = ("-created_at",)

    # ตัวกรองด้านขวา
    list_filter = (
        "status", "restaurant", "is_halal", "is_vegetarian", "is_vegan", "no_alcohol",
        "created_at", "created_by",
    )

    # ช่องค้นหา
    search_fields = (
        "name", "restaurant__name", "restaurant_name", "ingredients", "description",
    )

    # ปรับ widget สำหรับ TextField
    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(attrs={"rows": 3, "cols": 60})
        }
    }

    # จัดกลุ่มฟิลด์ในหน้าแก้ไข/เพิ่ม
    fieldsets = (
        ("ข้อมูลเมนู", {
            "fields": (
                "restaurant", "restaurant_name", "name", "description", "price", "image",
            )
        }),
        ("การกรอง/โภชนาการ", {
            "fields": (
                "ingredients", "is_halal", "is_vegetarian", "is_vegan", "no_alcohol",
            )
        }),
        ("สถานะ / การอนุมัติ", {
            "fields": ("status", "approved_by", "approved_at"),
        }),
        ("ระบบ", {
            "fields": ("created_by", "created_at"),
        }),
    )

    # ฟิลด์ที่อ่านอย่างเดียวในหน้าแก้ไข
    readonly_fields = ("created_by", "created_at", "approved_by", "approved_at")

    # กำหนดค่าเริ่มต้น/อัปเดตอัตโนมัติเมื่อบันทึกใน Admin
    def save_model(self, request, obj, form, change):
        # เซ็ตคนสร้างอัตโนมัติเมื่อสร้างใหม่
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user

        # ถ้าเปลี่ยนสถานะเป็น approved แล้วยังไม่เคยระบุผู้อนุมัติ → เซ็ตให้เลย
        if obj.status == Menu.Status.APPROVED and not obj.approved_by:
            obj.approved_by = request.user
            obj.approved_at = timezone.now()

        # ถ้าย้ายจาก approved -> เป็นอย่างอื่น ให้เคลียร์ approved_by/approved_at
        if obj.status != Menu.Status.APPROVED:
            obj.approved_by = None
            obj.approved_at = None

        super().save_model(request, obj, form, change)

    # ซ่อนปุ่ม "Save and add another" และ "Save and continue"
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_save_and_add_another"] = False
        extra_context["show_save_and_continue"] = False
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    # แสดงชื่อผู้ใช้สวยงาม
    def creator(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return "-"
    creator.short_description = "Created by"

    # ปุ่มแก้ไขในคอลัมน์สุดท้าย
    def edit_button(self, obj):
        url = reverse("admin:menus_menu_change", args=[obj.pk])
        return format_html('<a class="button" href="{}">แก้ไข</a>', url)
    edit_button.short_description = "จัดการ"

    # เพิ่ม Admin actions: อนุมัติ / ไม่อนุมัติ
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        updated = 0
        for obj in queryset:
            if obj.status != Menu.Status.APPROVED:
                obj.status = Menu.Status.APPROVED
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
                obj.save(update_fields=["status", "approved_by", "approved_at"])
                updated += 1
        self.message_user(request, f"อนุมัติเมนูจำนวน {updated} รายการแล้ว", level=messages.SUCCESS)
    approve_selected.short_description = "อนุมัติเมนูที่เลือก"

    def reject_selected(self, request, queryset):
        updated = queryset.update(
            status=Menu.Status.REJECTED, approved_by=None, approved_at=None
        )
        self.message_user(request, f"ตั้งสถานะเป็น Rejected จำนวน {updated} รายการแล้ว", level=messages.WARNING)
    reject_selected.short_description = "ตั้งสถานะเมนูที่เลือกเป็น Rejected"


from django.contrib import admin
from .models import Ingredient


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("id", "name")
    ordering = ("id",)
