from datetime import timedelta
from django.utils import timezone
from .models import SearchHistory


def normalize_filters(filters: dict) -> dict:
    """
    ปรับ filters ให้เป็นโครงสร้างนิ่งๆ
    - ตัดค่าที่ว่าง
    - แปลง list/tuple ให้เป็น list
    - เรียง list เพื่อให้เทียบ “เหมือนกัน” ได้ง่าย
    """
    cleaned = {}
    for k, v in (filters or {}).items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, (list, tuple)):
            vv = [x for x in v if x not in (None, "", [])]
            if not vv:
                continue
            try:
                vv = sorted(vv)
            except Exception:
                pass
            cleaned[k] = vv
        else:
            cleaned[k] = v
    return cleaned


def log_search(*, user, path: str, keyword: str, filters: dict, result_count: int, dedup_minutes: int = 2):
    """
    บันทึกประวัติการค้น
    - ถ้าภายใน X นาทีล่าสุด user ค้นเหมือนเดิม (keyword+filters+path) -> update record เดิม (count++)
    - ถ้าไม่เหมือน -> create ใหม่
    """
    if not user or not user.is_authenticated:
        return

    keyword = (keyword or "").strip()
    nf = normalize_filters(filters or {})
    now = timezone.now()
    since = now - timedelta(minutes=dedup_minutes)

    last = (
        SearchHistory.objects
        .filter(user=user, updated_at__gte=since)
        .order_by("-updated_at")
        .first()
    )

    if last and last.path == (path or "") and last.keyword == keyword and (last.filters_json or {}) == nf:
        last.result_count = int(result_count or 0)
        last.count = (last.count or 1) + 1
        last.save(update_fields=["result_count", "count", "updated_at"])
        return

    SearchHistory.objects.create(
        user=user,
        path=path or "",
        keyword=keyword,
        filters_json=nf,
        result_count=int(result_count or 0),
        count=1,
    )
