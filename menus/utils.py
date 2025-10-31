from django.db.models import Q

# ------------------ คีย์เวิร์ด/ข้อจำกัด ------------------
KW = {
    "หมู": ["หมู", "หมูกรอบ", "หมูสับ", "สามชั้น", "pork", "เบคอน", "bacon"],
    "ไก่": ["ไก่", "chicken"],
    "เนื้อวัว": ["เนื้อวัว", "เนื้อ", "วัว", "beef"],
    "กุ้ง": ["กุ้ง", "shrimp", "prawn"],
    "ทะเล": ["ทะเล", "ซีฟู้ด", "seafood", "หมึก", "ปลาหมึก", "squid", "หอย", "ปู", "crab", "clam", "oyster" , "กุ้ง"],
    "เห็ด": ["เห็ด", "mushroom"],
    "หัวหอม": ["หัวหอม", "หอมใหญ่", "หอมแดง", "onion"],
    "เครื่องใน": ["เครื่องใน", "ตับ", "ไส้", "กึ๋น", "offal", "liver"],
    "ผักชี": ["ผักชี", "coriander", "cilantro"],
    "กระเทียม": ["กระเทียม", "garlic"],
    "นม": ["นม", "ชีส", "เนย", "milk", "cheese", "butter", "cream", "โยเกิร์ต", "yogurt"],
    "ไข่": ["ไข่", "egg"],
    "แป้งสาลี": ["แป้งสาลี", "แป้ง", "wheat", "กลูเตน", "gluten", "บะหมี่", "ขนมปัง", "แป้งทอด"],
    "ถั่ว": ["ถั่ว", "peanut", "อัลมอนด์", "almond", "nut"],
}

RELIGION_BLOCK = {
    "ฮาลาล": ["หมู", "pork", "เบคอน", "alcohol", "ไวน์", "เบียร์"],
    "อาหารเจ": ["หมู","ไก่","เนื้อวัว","กุ้ง","ทะเล","ไข่","นม","meat","egg","milk","butter"],
    "มังสวิรัติ": ["หมู","ไก่","เนื้อวัว","กุ้ง","ทะเล","meat","pork","beef","chicken","seafood"],
    "หลีกเลี่ยงแอลกอฮอล์": ["alcohol","ไวน์","เบียร์","rum","whisky","sake"],
}


# ------------------ main ------------------
def filter_by_plan(qs, plan: dict | None):
    """
    กรองเมนูตามแผน:
      - budget (ราคาไม่เกิน)
      - allergies + dislikes
      - religions
      - extra
    """
    if not plan:
        return qs

    # 1) งบประมาณ
    budget = plan.get("budget")
    if budget and str(budget).isdigit():
        qs = qs.filter(price__lte=int(budget))

    # 2) รวมคีย์เวิร์ดต้องห้าม
    ban: list[str] = []
    for key in (plan.get("allergies") or []) + (plan.get("dislikes") or []):
        ban += KW.get(key, [key])  # ถ้าไม่อยู่ใน KW ก็ใช้ key เดิม

    for r in plan.get("religions") or []:
        ban += RELIGION_BLOCK.get(r, [])

    extra = plan.get("extra") or {}
    for e in (extra.get("allergy") or "").split(","):
        if e.strip():
            ban.append(e.strip())
    for e in (extra.get("dislike") or "").split(","):
        if e.strip():
            ban.append(e.strip())

    # 3) ตัดเมนูที่มีคำต้องห้าม
    if ban:
        q_ex = Q()
        for w in set(ban):
            q_ex |= Q(name__icontains=w) | Q(description__icontains=w)
        qs = qs.exclude(q_ex)

    return qs.distinct()
