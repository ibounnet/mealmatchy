from django.db import models
from django.db.models import Q


# ------------------ คีย์เวิร์ด/ข้อจำกัด ------------------
KW = {
    "หมู": ["หมู", "หมูกรอบ", "หมูสับ", "สามชั้น", "pork", "เบคอน", "bacon"],
    "ไก่": ["ไก่", "chicken"],
    "เนื้อวัว": ["เนื้อวัว", "เนื้อ", "วัว", "beef"],
    "กุ้ง": [
        "กุ้ง", "shrimp", "prawn",
        # เพิ่มพิเศษ: ตัดด้วยคำที่เกี่ยวกับอาหารทะเลด้วย
        "ทะเล", "ซีฟู้ด", "seafood", "หมึก", "ปลาหมึก", "squid", "หอย", "ปู", "crab", "clam", "oyster"
    ],
    "ทะเล": ["ทะเล", "ซีฟู้ด", "seafood", "หมึก", "ปลาหมึก", "squid", "หอย", "ปู", "crab", "clam", "oyster"],
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


# ------------------ helpers: หา lookup ปลอดภัยตามชนิดฟิลด์ ------------------
def _ingredient_lookup(menu_model: models.Model) -> str | None:
    """
    คืน lookup สำหรับ ingredients:
      - ถ้าเป็น TextField/CharField -> 'ingredients__icontains'
      - ถ้าเป็น ManyToMany(Ingredient.name) -> 'ingredients__name__icontains'
      - อย่างอื่น -> None
    """
    try:
        f = menu_model._meta.get_field("ingredients")
    except Exception:
        return None

    if isinstance(f, (models.CharField, models.TextField)):
        return "ingredients__icontains"

    if isinstance(f, models.ManyToManyField):
        try:
            rel_model = f.remote_field.model
            # หาชื่อฟิลด์ตัวอักษรในโมเดลวัตถุดิบ เช่น name/title
            for name_field in ("name", "title", "label"):
                rf = rel_model._meta.get_field(name_field)
                if isinstance(rf, (models.CharField, models.TextField)):
                    return f"ingredients__{name_field}__icontains"
        except Exception:
            return None

    return None


def _restaurant_lookup(menu_model: models.Model) -> str | None:
    """
    คืน lookup สำหรับชื่อร้าน:
      - ถ้า Menu มี FK 'restaurant' และ Restaurant มีฟิลด์ตัวอักษร เช่น name/title/restaurant_name
        -> 'restaurant__<that_field>__icontains'
      - ถ้าไม่มี -> None (จะไม่ join ร้าน)
    """
    try:
        rf = menu_model._meta.get_field("restaurant")
        if not isinstance(rf, models.ForeignKey):
            return None
        rest_model = rf.remote_field.model
    except Exception:
        return None

    for fname in ("name", "restaurant_name", "title", "display_name"):
        try:
            f = rest_model._meta.get_field(fname)
            if isinstance(f, (models.CharField, models.TextField)):
                return f"restaurant__{fname}__icontains"
        except Exception:
            continue

    return None


def _build_exclude_q(words, menu_model: models.Model):
    """
    ประกอบ Q สำหรับ exclude โดยตรวจชนิดฟิลด์ก่อนทุกครั้ง
    - ชื่อเมนู/คำอธิบาย -> icontains ได้แน่นอน
    - ingredients -> เลือก lookup ตามชนิด (TextField vs M2M)
    - restaurant -> ใช้เฉพาะเมื่อมี lookup ปลอดภัยเท่านั้น
    """
    ing_lookup = _ingredient_lookup(menu_model)   # eg. 'ingredients__icontains' หรือ 'ingredients__name__icontains' หรือ None
    rest_lookup = _restaurant_lookup(menu_model)  # eg. 'restaurant__name__icontains' หรือ None

    q = Q()
    for w in set(words):
        q_word = Q(name__icontains=w) | Q(description__icontains=w)

        if ing_lookup:
            q_word |= Q(**{ing_lookup: w})

        if rest_lookup:
            q_word |= Q(**{rest_lookup: w})

        q |= q_word

    return q


# ------------------ main ------------------
def filter_by_plan(qs, plan: dict | None):
    """
    กรองเมนูอย่างปลอดภัยตาม plan ใน session:
      - budget (ราคาไม่เกิน)
      - allergies + dislikes (รวม mapping ใน KW)
      - religions (mapping เพิ่มคำต้องห้าม)
      - extra (คอมมาแยกคำ)
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
        ban += KW.get(key, [key])  # ถ้า key ไม่อยู่ในแมพ ก็ใช้ key เดิม

    for r in plan.get("religions") or []:
        ban += RELIGION_BLOCK.get(r, [])

    extra = plan.get("extra") or {}
    for e in (extra.get("allergy") or "").split(","):
        e = e.strip()
        if e:
            ban.append(e)
    for e in (extra.get("dislike") or "").split(","):
        e = e.strip()
        if e:
            ban.append(e)

    # 3) ตัดเมนูตามคีย์เวิร์ดต้องห้าม (ประกอบ Q แบบปลอดภัย)
    if ban:
        q_ex = _build_exclude_q(ban, qs.model)
        qs = qs.exclude(q_ex)

    return qs.distinct()
