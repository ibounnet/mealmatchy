# menus/admin.py
from django.contrib import admin, messages
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from .models import Menu

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant_name", "name", "price", "creator", "created_at", "edit_button")
    list_display_links = ("id", "restaurant_name", "name")
    ordering = ("-created_at",)
    list_filter = ("created_at", "created_by")
    search_fields = ("restaurant_name", "name", "description")

    formfield_overrides = {
        models.TextField: {
            'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 4, 'cols': 60})
        }
    }

    # ✅ เซ็ตคนสร้างอัตโนมัติ
    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # ✅ ซ่อนปุ่ม "บันทึกและเพิ่ม" + "บันทึกและแก้ไขต่อ"
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save_and_add_another'] = False
        extra_context['show_save_and_continue'] = False
        # (ปุ่ม Save ปกติและ Delete ยังอยู่)
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    # ✅ แสดงชื่อผู้ใช้ (ชื่อจริงถ้ามี) แทน object user
    def creator(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return '-'
    creator.short_description = "Created by"

    # (ออปชัน) ปุ่มแก้ไขในคอลัมน์สุดท้าย
    def edit_button(self, obj):
        url = reverse('admin:menus_menu_change', args=[obj.pk])
        return format_html('<a class="button" href="{}">แก้ไข</a>', url)
    edit_button.short_description = "จัดการ"
