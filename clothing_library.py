# -*- coding: utf-8 -*-
"""
BSAI AI clothing library backend — Clothing Wall

Library source: C:\\BSAI\\AI资料\\素材库离线版带网页预览\\AI服装
Naming: {PREFIX}-{NNNN}.webp   e.g. AUT-0001.webp
  · AUT: Automotive (244)
  · LNG: Lingerie (199)
  · PTY: Party (48)
  · SPR: Sport (215)
  · SUM: Summer (254)
  · SWM: Swimwear (54)
  · SXY: Sexy (140)
  · WIN: Winter (253)

This module handles:
  1. Scan library -> manifest JSON
  2. Lazy thumbnail generation (web/clothing_thumbnails/)
  3. Selection list persistence (clothing_selection.json)
  4. Route registration (wall HTML + manifest API + image/thumb serving)
"""
import json
import os
import re
import time

try:
    from .common import PLUGIN_ROOT
except ImportError:
    PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))

WEB_DIR = os.path.join(PLUGIN_ROOT, "web")
THUMB_DIR = os.path.join(WEB_DIR, "clothing_thumbnails")
MANIFEST_PATH = os.path.join(WEB_DIR, "clothing_manifest.json")
SELECTION_PATH = os.path.join(PLUGIN_ROOT, "clothing_selection.json")
CONFIG_PATH = os.path.join(PLUGIN_ROOT, "clothing_library.json")

DEFAULT_LIBRARY_ROOT = r"C:\BSAI\AI资料\素材库离线版带网页预览\AI服装"

THUMB_WIDTH = 300
THUMB_HEIGHT = 400
THUMB_QUALITY = 82

# Category prefix -> display label
CATEGORY_LABELS = {
    "AUT": "Automotive",
    "LNG": "Lingerie",
    "PTY": "Party",
    "SPR": "Sport",
    "SUM": "Summer",
    "SWM": "Swimwear",
    "SXY": "Sexy",
    "WIN": "Winter",
}

CATEGORY_ORDER = ["AUT", "LNG", "PTY", "SPR", "SUM", "SWM", "SXY", "WIN"]

# Naming: {PREFIX}-{NNNN}.webp
_NAME_RE = re.compile(r"^(?P<cat>[A-Z]{3})-(?P<num>\d{4})\.(?P<ext>webp|jpg|jpeg|png)$", re.IGNORECASE)

_manifest_cache = {"data": None, "mtime": None}


def get_library_root():
    env = os.environ.get("BSAI_CLOTHING_LIBRARY", "").strip()
    if env and os.path.isdir(env):
        return os.path.normpath(env)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        root = str(cfg.get("root", "") or "").strip()
        if root and os.path.isdir(root):
            return os.path.normpath(root)
    except Exception:
        pass
    return DEFAULT_LIBRARY_ROOT


def set_library_root(root):
    root = str(root or "").strip()
    payload = {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        payload = {}
    payload["root"] = root
    payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return get_library_root()


def _image_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


def scan_library(root=None):
    root = os.path.normpath(root or get_library_root())
    entries = []
    if not os.path.isdir(root):
        return entries
    try:
        names = os.listdir(root)
    except Exception:
        return entries
    for fn in names:
        m = _NAME_RE.match(fn)
        if not m:
            continue
        full = os.path.join(root, fn)
        if not os.path.isfile(full):
            continue
        cat = m.group("cat").upper()
        num = m.group("num")
        eid = "%s-%s" % (cat, num)
        try:
            size = os.path.getsize(full)
        except Exception:
            size = 0
        w, h = _image_size(full)
        entries.append({
            "id": eid,
            "file": fn,
            "category": cat,
            "category_label": CATEGORY_LABELS.get(cat, cat),
            "num": num,
            "w": w,
            "h": h,
            "bytes": size,
        })
    cat_rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    entries.sort(key=lambda e: (cat_rank.get(e["category"], 99), int(e["num"])))
    return entries


def build_manifest(root=None, force=False):
    root = os.path.normpath(root or get_library_root())
    try:
        mtime = os.path.getmtime(MANIFEST_PATH)
    except Exception:
        mtime = None
    if not force and _manifest_cache["data"] and _manifest_cache["mtime"] == mtime:
        return _manifest_cache["data"]

    entries = scan_library(root)
    categories = []
    for cid in CATEGORY_ORDER:
        n = len([e for e in entries if e["category"] == cid])
        if n:
            categories.append({"id": cid, "label": CATEGORY_LABELS[cid], "count": n})
    for e in entries:
        if not any(c["id"] == e["category"] for c in categories):
            categories.append({
                "id": e["category"],
                "label": CATEGORY_LABELS.get(e["category"], e["category"]),
                "count": len([x for x in entries if x["category"] == e["category"]]),
            })

    manifest = {
        "root": root,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(entries),
        "categories": categories,
        "thumb_size": [THUMB_WIDTH, THUMB_HEIGHT],
        "entries": entries,
    }
    try:
        os.makedirs(WEB_DIR, exist_ok=True)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
        _manifest_cache["mtime"] = os.path.getmtime(MANIFEST_PATH)
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] clothing manifest write failed: %s" % e)
    _manifest_cache["data"] = manifest
    return manifest


def load_manifest():
    if _manifest_cache["data"]:
        return _manifest_cache["data"]
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _manifest_cache["data"] = data
        _manifest_cache["mtime"] = os.path.getmtime(MANIFEST_PATH)
        return data
    except Exception:
        return build_manifest()


def find_entry(entry_id):
    if not entry_id:
        return None
    for e in load_manifest().get("entries", []):
        if e["id"] == entry_id:
            return e
    return None


def thumb_abs_path(entry):
    return os.path.join(THUMB_DIR, "%s.jpg" % entry["id"])


def ensure_thumb(entry):
    if not entry:
        return False
    dest = thumb_abs_path(entry)
    try:
        if os.path.exists(dest) and os.path.getsize(dest) > 512:
            return True
    except Exception:
        pass
    src = os.path.join(get_library_root(), entry["file"])
    if not os.path.isfile(src):
        return False
    try:
        from PIL import Image
        os.makedirs(THUMB_DIR, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            scale = THUMB_WIDTH / float(im.width)
            nh = max(1, int(round(im.height * scale)))
            im = im.resize((THUMB_WIDTH, nh), Image.LANCZOS)
            if nh < THUMB_HEIGHT:
                canvas = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), "#ffffff")
                canvas.paste(im, (0, (THUMB_HEIGHT - nh) // 2))
                im = canvas
            elif nh > THUMB_HEIGHT:
                canvas = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), "#ffffff")
                canvas.paste(im.crop((0, 0, THUMB_WIDTH, THUMB_HEIGHT)), (0, 0))
                im = canvas
            im.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return True
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] clothing thumbnail failed %s: %s" % (entry.get("id"), e))
        return False


def ensure_thumbs_bulk(entries=None):
    if entries is None:
        entries = load_manifest().get("entries", [])
    ok = 0
    fail = 0
    for e in entries:
        try:
            if os.path.exists(thumb_abs_path(e)) and os.path.getsize(thumb_abs_path(e)) > 512:
                ok += 1
                continue
        except Exception:
            pass
        if ensure_thumb(e):
            ok += 1
        else:
            fail += 1
    return ok, fail


def load_selection():
    try:
        with open(SELECTION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save_selection(items):
    valid = []
    seen = set()
    for it in (items or []):
        eid = it.get("id", "") if isinstance(it, dict) else str(it)
        if not eid or eid in seen:
            continue
        if not find_entry(eid):
            continue
        seen.add(eid)
        valid.append(eid)
    payload = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items": valid,
    }
    try:
        with open(SELECTION_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] clothing selection write failed: %s" % e)
    return valid


def selection_text(items=None):
    items = items if items is not None else load_selection()
    lines = []
    for i, eid in enumerate(items, 1):
        e = find_entry(eid)
        if not e:
            continue
        lines.append("img%d = %s (%s, #%s)" % (
            i, e["file"], e["category_label"], e["num"]))
    return "\n".join(lines)


def selection_prompt_snippet(items=None):
    items = items if items is not None else load_selection()
    lines = []
    for i, eid in enumerate(items, 1):
        e = find_entry(eid)
        if not e:
            continue
        lines.append(
            "Image %d - %s (%s outfit reference, clothing design guide)"
            % (i, e["file"], e["category_label"])
        )
    if not lines:
        return ""
    head = "Reference images (use them in exactly this order):"
    tail = (
        "Follow the clothing design, fabric, color, and cut of each reference image. "
        "Adapt the outfit to the character and scene. "
        "The reference images are clothing guides only; render them as the final artwork."
    )
    return head + "\n" + "\n".join(lines) + "\n" + tail


def register_clothing_routes():
    try:
        from server import PromptServer
        from aiohttp import web

        server = PromptServer.instance
        wall_html = os.path.join(WEB_DIR, "clothing_wall.html")

        @server.routes.get("/bsai_clothing_wall")
        async def _bsai_clothing_wall(request):
            if not os.path.isfile(wall_html):
                return web.Response(status=404, text="clothing_wall.html missing")
            return web.FileResponse(wall_html, headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.get("/api/bsai/clothing")
        async def _bsai_clothing_manifest(request):
            root = get_library_root()
            m = load_manifest()
            if m.get("root") != root:
                m = build_manifest(root, force=True)
            return web.json_response(m, headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.get("/bsai_clothing_image")
        async def _bsai_clothing_image(request):
            eid = request.query.get("id", "")
            entry = find_entry(eid)
            if not entry:
                return web.Response(status=404, text="unknown clothing id")
            src = os.path.join(get_library_root(), entry["file"])
            if not os.path.isfile(src):
                return web.Response(status=404, text="source file missing")
            return web.FileResponse(src, headers={"Cache-Control": "public, max-age=86400"})

        @server.routes.get("/bsai_clothing_thumb")
        async def _bsai_clothing_thumb(request):
            eid = request.query.get("id", "")
            entry = find_entry(eid)
            if not entry:
                return web.Response(status=404, text="unknown clothing id")
            if not ensure_thumb(entry):
                return web.Response(status=404, text="thumbnail missing")
            return web.FileResponse(thumb_abs_path(entry),
                                    headers={"Cache-Control": "public, max-age=604800"})

        @server.routes.get("/api/bsai/clothing_selection")
        async def _bsai_clothing_selection_get(request):
            return web.json_response(
                {"items": load_selection(), "text": selection_text()},
                headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.post("/bsai_clothing_selection")
        async def _bsai_clothing_selection_post(request):
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"ok": False, "message": "invalid json"}, status=400)
            items = data.get("items")
            if not isinstance(items, list):
                return web.json_response({"ok": False, "message": "items must be a list"}, status=400)
            saved = save_selection(items)
            return web.json_response({"ok": True, "items": saved, "text": selection_text(saved)})

        @server.routes.post("/bsai_clothing_rescan")
        async def _bsai_clothing_rescan(request):
            root = get_library_root()
            m = build_manifest(root, force=True)
            ok, fail = ensure_thumbs_bulk(m.get("entries", []))
            return web.json_response({
                "ok": True,
                "root": root,
                "count": m.get("count", 0),
                "thumbs_ok": ok,
                "thumbs_fail": fail,
            })

        print("[BSAI_Qwen_Prompt_Enhancer] clothing wall routes registered: GET /bsai_clothing_wall")
        return True
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] clothing wall route registration failed (non-fatal): %s" % e)
        return False
