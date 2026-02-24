# searches/views.py
import json
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.utils import timezone

from menus.models import Menu
from restaurants.models import Restaurant
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


# ✅ เพิ่ม: ขยายคำค้นหาให้เป็นคำใกล้เคียง (ไทย)
def expand_thai_keywords(q: str) -> list[str]:
    q = (q or "").strip()
    if not q:
        return []

    keywords = {q}

    # กฎทั่วไป: ถ้ามี "กะ" ให้ลองเพิ่มแบบ "กระ"
    if "กะ" in q:
        keywords.add(q.replace("กะ", "กระ"))
    if "กระ" in q:
        keywords.add(q.replace("กระ", "กะ"))

    # mapping แบบเจาะจง (เพิ่มได้เรื่อย ๆ)
    pairs = {
        "กะเพรา": ["กระเพรา", "ผัดกะเพรา", "ผัดกระเพรา"],
        "กระเพรา": ["กะเพรา", "ผัดกะเพรา", "ผัดกระเพรา"],
    }

    for k, alts in pairs.items():
        if k in q:
            for a in alts:
                keywords.add(a)

    return list(keywords)


def build_or_q(field: str, kws: list[str]) -> Q:
    cond = Q()
    for kw in kws:
        kw = (kw or "").strip()
        if kw:
            cond |= Q(**{f"{field}__icontains": kw})
    return cond


@login_required
def search(request):
    """
    /search/?q=...&scope=all|menus|restaurants|recipes|community
    """
    q = (request.GET.get("q") or "").strip()
    scope = (request.GET.get("scope") or "all").strip()

    menus = Menu.objects.none()
    restaurants = Restaurant.objects.none()
    recipes = Recipe.objects.none()
    topics = Topic.objects.none()

    keywords = expand_thai_keywords(q)

    if q:
        if scope in ("all", "menus"):
            menus = (
                Menu.objects.filter(
                    build_or_q("name", keywords) |
                    build_or_q("restaurant_name", keywords)
                )
                .order_by("-id")[:40]
            )

        if scope in ("all", "restaurants"):
            restaurants = (
                Restaurant.objects.filter(build_or_q("name", keywords))
                .order_by("-id")[:40]
            )

        if scope in ("all", "recipes"):
            recipes = (
                Recipe.objects.filter(
                    build_or_q("title", keywords) |
                    build_or_q("description", keywords) |
                    build_or_q("ingredients", keywords) |
                    build_or_q("steps", keywords)
                )
                .order_by("-created_at")[:40]
            )

        if scope in ("all", "community"):
            base_topics = Topic.objects.all()
            if not request.user.is_staff:
                base_topics = base_topics.filter(status="approved")

            topics = (
                base_topics.filter(
                    build_or_q("title", keywords) |
                    build_or_q("description", keywords)
                )
                .order_by("-created_at")[:40]
            )

    filters_json = {"scope": scope}
    result_count = int(menus.count() + restaurants.count() + recipes.count() + topics.count())

    create_kwargs = {
        "user": request.user,
        "path": request.path,
        "filters_json": filters_json,
        "result_count": result_count,
    }

    if hasattr(SearchHistory, "query"):
        create_kwargs["query"] = q
    elif hasattr(SearchHistory, "keyword"):
        create_kwargs["keyword"] = q

    try:
        lookup = {"user": request.user, "path": request.path, "filters_json": filters_json}
        if "query" in create_kwargs:
            lookup["query"] = q
        if "keyword" in create_kwargs:
            lookup["keyword"] = q

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