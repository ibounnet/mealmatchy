# searches/views.py
import json
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.utils import timezone

from menus.models import Menu, Restaurant
from recipes.models import Recipe
from community.models import Topic
from .models import SearchHistory


def _to_display_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        cleaned = [str(x).strip() for x in v if x is not None and str(x).strip() != ""]
        return ", ".join(cleaned)
    if isinstance(v, dict):
        return ", ".join([f"{k}:{val}" for k, val in v.items()])
    return str(v).strip()


@login_required
def search(request):
    """
    /search/?q=...&scope=all|menus|restaurants|recipes|community
    """
    q = (request.GET.get("q") or "").strip()
    scope = (request.GET.get("scope") or "all").strip()

    # --- base result sets ---
    menus = Menu.objects.none()
    restaurants = Restaurant.objects.none()
    recipes = Recipe.objects.none()
    topics = Topic.objects.none()

    if q:
        if scope in ("all", "menus"):
            # ปรับ field ให้ตรงกับ Menu ของคุณ (เดิมคุณใช้ name/restaurant_name/price)
            menus = Menu.objects.filter(
                Q(name__icontains=q) |
                Q(restaurant_name__icontains=q)
            ).order_by("-id")[:40]

        if scope in ("all", "restaurants"):
            # ปรับ field ให้ตรงกับ Restaurant ของคุณ (สมมติ name)
            restaurants = Restaurant.objects.filter(
                Q(name__icontains=q)
            ).order_by("-id")[:40]

        if scope in ("all", "recipes"):
            recipes = Recipe.objects.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(ingredients__icontains=q) |
                Q(steps__icontains=q)
            ).order_by("-created_at")[:40]

        if scope in ("all", "community"):
            # ✅ FIX HERE: Topic ไม่มี content -> ใช้ title/description แทน
            # และคุมสิทธิ์: คนทั่วไปเห็นเฉพาะ approved (ถ้าโปรเจกต์ใช้ status แบบนี้)
            base_topics = Topic.objects.all()
            if not request.user.is_staff:
                # ถ้าโปรเจกต์คุณใช้ชื่อสถานะอื่น ให้เปลี่ยน 'approved' ให้ตรง
                base_topics = base_topics.filter(status="approved")

            topics = base_topics.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q)
            ).order_by("-created_at")[:40]

    # --- save history (กันพังด้วยการใช้ fields ที่ "มีจริง" ตามที่คุณใช้ก่อนหน้า) ---
    # ถ้าโมเดลคุณใช้ keyword/filters_json/path/result_count ให้แก้ด้านล่างให้ตรง
    filters_json = {"scope": scope}
    result_count = int(menus.count() + restaurants.count() + recipes.count() + topics.count())

    # รองรับได้ 2 แบบ: SearchHistory มี field query หรือ keyword
    create_kwargs = {
        "user": request.user,
        "path": request.path,
        "filters_json": filters_json,
        "result_count": result_count,
    }

    # ใส่คำค้นให้ถูก field
    if hasattr(SearchHistory, "query"):
        create_kwargs["query"] = q
    elif hasattr(SearchHistory, "keyword"):
        create_kwargs["keyword"] = q

    # อัปเดตถ้ามี record เดิม “คำค้น+scope เดิม” เพื่อให้ updated_at ขยับ (UX ดี)
    try:
        # พยายาม match ตาม field ที่มีจริง
        lookup = {"user": request.user, "path": request.path}
        if "query" in create_kwargs:
            lookup["query"] = q
        if "keyword" in create_kwargs:
            lookup["keyword"] = q
        lookup["filters_json"] = filters_json

        obj = SearchHistory.objects.filter(**lookup).first()
        if obj:
            obj.result_count = result_count
            obj.filters_json = filters_json
            obj.path = request.path
            obj.updated_at = timezone.now()
            obj.save(update_fields=["result_count", "filters_json", "path", "updated_at"])
        else:
            SearchHistory.objects.create(**create_kwargs)
    except Exception:
        # history พังไม่ควรทำให้ search พัง
        pass

    return render(request, "searches/search_results.html", {
        "q": q,
        "scope": scope,
        "menus": menus,
        "restaurants": restaurants,
        "recipes": recipes,
        "topics": topics,
        "total": result_count,
    })


@login_required
def history_list(request):
    qs = SearchHistory.objects.filter(user=request.user).order_by("-updated_at", "-created_at")[:200]

    items = []
    for it in qs:
        raw = it.filters_json or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}

        filters_pairs = []
        if isinstance(raw, dict):
            for k, v in raw.items():
                val_str = _to_display_value(v)
                if val_str:
                    filters_pairs.append((k, val_str))

        # รองรับ field query/keyword
        query_val = ""
        if hasattr(it, "query"):
            query_val = it.query or ""
        elif hasattr(it, "keyword"):
            query_val = it.keyword or ""

        items.append({
            "id": it.id,
            "query": query_val,
            "created_at": it.created_at,
            "updated_at": it.updated_at,
            "result_count": getattr(it, "result_count", None),
            "filters_pairs": filters_pairs,
        })

    return render(request, "searches/history_list.html", {
        "items": items,
        "today": timezone.localdate(),
    })


@login_required
def history_delete(request, pk):
    item = get_object_or_404(SearchHistory, pk=pk)
    if item.user_id != request.user.id:
        return HttpResponseForbidden("Forbidden")
    if request.method == "POST":
        item.delete()
    return redirect("searches:history_list")


@login_required
def history_clear(request):
    if request.method == "POST":
        SearchHistory.objects.filter(user=request.user).delete()
    return redirect("searches:history_list")


@login_required
def history_rerun(request, pk):
    item = get_object_or_404(SearchHistory, pk=pk, user=request.user)

    params = {}
    # รองรับ query/keyword
    if hasattr(item, "query") and item.query:
        params["q"] = item.query
    elif hasattr(item, "keyword") and item.keyword:
        params["q"] = item.keyword

    for k, v in (item.filters_json or {}).items():
        params[k] = v

    base_path = item.path or "/"
    if "?" in base_path:
        base_path = base_path.split("?")[0]

    query = urlencode(params, doseq=True)
    url = f"{base_path}?{query}" if query else base_path
    return redirect(url)
