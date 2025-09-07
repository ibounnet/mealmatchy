from django.db.models import Q
import re

ALLERGY_KEY_MAP = {
    # คำที่มักอยู่ใน ingredients
    "กุ้ง": ["กุ้ง"],
    "ไข่": ["ไข่"],
    "นม": ["นม", "นมวัว", "นมสด", "ชีส", "เนย"],
    "ถั่ว": ["ถั่ว", "ถั่วลิสง", "อัลมอนด์", "วอลนัท", "เม็ดมะม่วง"],
    "แป้งสาลี": ["แป้งสาลี", "กลูเตน", "ซีอิ๊วขาว"],  # บางแบรนด์มีกลูเตน
    "ทะเล (รวม)": ["กุ้ง", "ปลาหมึก", "หอย", "ปลา"],
}

DISLIKE_KEY_MAP = {
    "หมู": ["หมู"],
    "ไก่": ["ไก่"],
    "เนื้อวัว": ["เนื้อวัว", "วัว", "เนื้อ"],
    "เห็ด": ["เห็ด"],
    "หัวหอม": ["หอม", "หอมหัวใหญ่", "หอมแดง"],
    "เครื่องใน": ["เครื่องใน", "ตับ", "ไส้", "หัวใจ"],
    "ผักชี": ["ผักชี"],
    "กระเทียม": ["กระเทียม"],
}

def build_exclude_q(ingredients_field, keywords):
    """
    สร้าง Q สำหรับ exclude ถ้า ingredients มีคำที่ไม่อนุญาต
    """
    q = Q()
    for kw in keywords:
        q |= Q(**{f"{ingredients_field}__iregex": rf"(^|,|\s){re.escape(kw)}(,|\s|$)"})
    return q

def filter_by_plan(queryset, plan: dict):
    """
    รับ QuerySet ของ Menu และ dict จาก session['plan']
    คืน QuerySet ที่ถูกกรองแล้ว
    """
    if not plan:
        return queryset

    allergies = plan.get('allergies', [])
    dislikes  = plan.get('dislikes', [])
    religions = plan.get('religions', [])
    extra     = plan.get('extra', {}) or {}

    # รวมคีย์เวิร์ดจาก allergies + extra allergy
    allergy_words = []
    for a in allergies:
        allergy_words += ALLERGY_KEY_MAP.get(a, [a])
    if extra.get('allergy'):
        allergy_words += [w.strip() for w in extra['allergy'].split(',') if w.strip()]

    dislike_words = []
    for d in dislikes:
        dislike_words += DISLIKE_KEY_MAP.get(d, [d])
    if extra.get('dislike'):
        dislike_words += [w.strip() for w in extra['dislike'].split(',') if w.strip()]

    # กรองตามศาสนา/วัฒนธรรม
    # - ฮาลาล: ต้องไม่ใช่หมู/แอลกอฮอล์ และควรติ๊ก is_halal ไว้ตอนใส่ข้อมูล
    if "ฮาลาล" in religions:
        queryset = queryset.filter(is_halal=True, no_alcohol=True)
        # กันเคสที่ miss-flag โดยดูคำ “หมู”
        queryset = queryset.exclude(build_exclude_q("ingredients", ["หมู"]))

    # มังสวิรัติ: ไม่มีเนื้อสัตว์แดง/ขาว อนุญาตไข่/นม
    if "มังสวิรัติ" in religions:
        queryset = queryset.filter(is_vegetarian=True, no_alcohol=True)

    # อาหารเจ/วีแกน: ไม่มีผลิตภัณฑ์สัตว์ทุกชนิด
    if "อาหารเจ" in religions:
        queryset = queryset.filter(is_vegan=True, no_alcohol=True)

    # หลีกเลี่ยงแอลกอฮอล์
    if "หลีกเลี่ยงแอลกอฮอล์" in religions:
        queryset = queryset.filter(no_alcohol=True)

    # แพ้/ไม่ชอบ → exclude ถ้ามีคำที่ชน
    if allergy_words:
        queryset = queryset.exclude(build_exclude_q("ingredients", allergy_words))
    if dislike_words:
        queryset = queryset.exclude(build_exclude_q("ingredients", dislike_words))

    return queryset
