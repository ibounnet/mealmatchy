# menus/utils.py
from django.db.models import Q

# คีย์เวิร์ดพื้นฐานสำหรับกรองวัตถุดิบ/ข้อจำกัด
KW = {
    # แพ้/ไม่กิน (allergies + dislikes)
    "หมู": ["หมู", "หมูกรอบ", "หมูสับ", "สามชั้น", "pork", "เบคอน", "bacon"],
    "ไก่": ["ไก่", "chicken"],
    "เนื้อวัว": ["เนื้อ", "วัว", "beef"],
    "กุ้ง": ["กุ้ง", "shrimp", "prawn"],
    "ทะเล (รวม)": ["ทะเล", "ปลาหมึก", "หมึก", "หอย", "ปู", "ซีฟู้ด", "seafood", "squid", "crab", "clam"],
    "เห็ด": ["เห็ด", "mushroom"],
    "หัวหอม": ["หัวหอม", "หอมใหญ่", "หอมแดง", "onion"],
    "เครื่องใน": ["เครื่องใน", "ตับ", "ไส้", "กึ๋น", "เครื่องในไก่", "เครื่องในหมู", "offal", "liver"],
    "ผักชี": ["ผักชี", "coriander", "cilantro"],
    "กระเทียม": ["กระเทียม", "garlic"],
    "นม": ["นม", "ชีส", "เนย", "milk", "cheese", "butter", "cream", "โยเกิร์ต", "yogurt"],
    "ไข่": ["ไข่", "egg"],
    "แป้งสาลี": ["แป้งสาลี", "แป้ง", "wheat", "กลูเตน", "gluten", "บะหมี่", "ขนมปัง", "แป้งทอด"],
    "ถั่ว": ["ถั่ว", "peanut", "ถั่วลิสง", "อัลมอนด์", "almond", "nut"],
}

# ศาสนา/วัฒนธรรม (ใช้การอนุมานอย่างง่าย)
RELIGION_BLOCK = {
    "ฮาลาล": ["หมู", "แอลกอฮอล์", "เบคอน", "pork", "alcohol", "ไวน์", "เบียร์"],
    "อาหารเจ": ["หมู","ไก่","เนื้อวัว","กุ้ง","ทะเล (รวม)","ไข่","นม","cheese","butter","egg","milk","meat"],
    "มังสวิรัติ": ["หมู","ไก่","เนื้อวัว","กุ้ง","ทะเล (รวม)","meat","pork","beef","chicken","seafood"],
    "หลีกเลี่ยงแอลกอฮอล์": ["แอลกอฮอล์","alcohol","ไวน์","เบียร์","rum","whisky","sake"],
}

def _build_exclude_q(words):
    """สร้าง Q สำหรับ 'ไม่ให้มี' คีย์เวิร์ดในชื่อ/คำอธิบาย/ชื่อร้าน"""
    q = Q()
    for w in set(words):
        q |= Q(name__icontains=w) | Q(description__icontains=w) | Q(restaurant_name__icontains=w)
    return q

def filter_by_plan(qs, plan: dict | None):
    """
    กรอง QuerySet ของ Menu ตามแผนใน session
    - budget: ราคาไม่เกิน
    - allergies, dislikes: ไม่ให้พบคีย์เวิร์ดที่เกี่ยวข้อง
    - religions: ตัดคีย์เวิร์ดที่ต้องหลีกเลี่ยงตามศาสนา/วัฒนธรรม
    """
    if not plan:
        return qs

    # 1) งบประมาณ
    budget = plan.get("budget")
    if budget and str(budget).isdigit():
        qs = qs.filter(price__lte=int(budget))

    # 2) รวมคีย์เวิร์ดที่ต้องตัดทิ้งจาก allergies + dislikes
    ban = []
    for key in (plan.get("allergies") or []) + (plan.get("dislikes") or []):
        ban += KW.get(key, [key])

    # 3) ศาสนา/วัฒนธรรม
    for r in plan.get("religions") or []:
        ban += RELIGION_BLOCK.get(r, [])

    # 4) extra free text
    extra = plan.get("extra") or {}
    for e in (extra.get("allergy") or "").split(","):
        if e.strip():
            ban.append(e.strip())
    for e in (extra.get("dislike") or "").split(","):
        if e.strip():
            ban.append(e.strip())

    if ban:
        qs = qs.exclude(_build_exclude_q(ban))

    return qs
