# -*- coding: utf-8 -*-
"""
BSAI AI肖像素材库后端 —— 肖像海报墙（Face Wall）

素材库来源：C:\\BSAI\\AI资料\\素材库离线版带网页预览\\AI肖像
命名规则：{12位hex}.png   例：f71f980dde3.png（与 PoseAtlas faces.json 的 id 一一对应）
来源：PoseAtlas 肖像图集（脸部 893 + 造型 606 = 1499 张，源站 ai-portrait-gallery.pages.dev，CC0 1.0）
分组维度：
  · sec（分区）：face=脸部 / styling=造型
  · hair（发型）：short=短发 / medium=中发 / semilong=中长发 / long=长发

本模块负责：
  1. 扫描素材库 -> manifest（清单 JSON，web/face_manifest.json）
  2. 缩略图惰性生成（web/face_thumbnails/，300x400 JPEG）
  3. 参考图选择清单的持久化（face_selection.json，供节点输出）
  4. 注册海报墙相关路由（直达路由 + 清单 API + 原图按需服务）

设计要点（与 pose/clothing 两套海报墙完全同构）：
  · 原图不复制、不缓存，直接从素材库按需流式返回
  · 缩略图只做小图（300x400 JPEG），海报墙滚动才不卡
  · 所有读取都走 manifest 白名单，路由不接受任意路径
"""
import json
import os
import re
import time

try:
    from .common import PLUGIN_ROOT
except ImportError:  # 独立脚本运行时没有包上下文
    PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))

WEB_DIR = os.path.join(PLUGIN_ROOT, "web")
THUMB_DIR = os.path.join(WEB_DIR, "face_thumbnails")
MANIFEST_PATH = os.path.join(WEB_DIR, "face_manifest.json")
META_PATH = os.path.join(WEB_DIR, "face_meta.json")   # PoseAtlas faces.json 精简元数据（id/sec/hair/style）
SELECTION_PATH = os.path.join(PLUGIN_ROOT, "face_selection.json")
CONFIG_PATH = os.path.join(PLUGIN_ROOT, "face_library.json")

# 素材库默认根目录（可在 face_library.json / 环境变量 BSAI_FACE_LIBRARY 里覆盖）
DEFAULT_LIBRARY_ROOT = r"C:\BSAI\AI资料\素材库离线版带网页预览\AI肖像"

THUMB_WIDTH = 300
THUMB_HEIGHT = 400
THUMB_QUALITY = 82

# sec 分区 -> display label
SEC_LABELS = {
    "face": "脸部",
    "styling": "造型",
}
SEC_ORDER = ["face", "styling"]

# hair 发型 -> display label
HAIR_LABELS = {
    "short": "短发",
    "medium": "中发",
    "semilong": "中长发",
    "long": "长发",
}
HAIR_ORDER = ["short", "medium", "semilong", "long"]

# 文件名解析：{11位hex}.png
_NAME_RE = re.compile(r"^([0-9a-f]{11})\.(?P<ext>png|jpg|jpeg|webp)$", re.IGNORECASE)

# manifest 内存缓存
_manifest_cache = {"data": None, "mtime": None}

# 元数据缓存（faces.json 精简版）
_meta_cache = None


def get_library_root():
    """素材库根目录：环境变量 > face_library.json > 默认值。"""
    env = os.environ.get("BSAI_FACE_LIBRARY", "").strip()
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
    """把素材库根目录写进 face_library.json（供节点/用户持久化）。"""
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


def _load_meta():
    """加载 face_meta.json（id -> sec/hair/style）。缺失时返回空 dict。"""
    global _meta_cache
    if _meta_cache is not None:
        return _meta_cache
    by_id = {}
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        for im in meta.get("images", []):
            by_id[str(im.get("id", ""))] = im
    except Exception:
        pass
    _meta_cache = by_id
    return by_id


def _image_size(path):
    """读图片尺寸；PIL 不可用时返回 (0, 0)。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


def scan_library(root=None):
    """扫描素材库目录，返回 entry 列表（已按 分区/发型/id 排序）。"""
    root = os.path.normpath(root or get_library_root())
    entries = []
    if not os.path.isdir(root):
        return entries
    try:
        names = os.listdir(root)
    except Exception:
        return entries
    meta = _load_meta()
    for fn in names:
        m = _NAME_RE.match(fn)
        if not m:
            continue
        full = os.path.join(root, fn)
        if not os.path.isfile(full):
            continue
        fid = m.group(1).lower()
        eid = fid
        md = meta.get(fid, {})
        sec = md.get("sec", "") or ""
        hair = md.get("hair", "") or ""
        try:
            size = os.path.getsize(full)
        except Exception:
            size = 0
        w, h = _image_size(full)
        entries.append({
            "id": eid,
            "file": fn,
            "sec": sec,
            "sec_label": SEC_LABELS.get(sec, sec),
            "hair": hair,
            "hair_label": HAIR_LABELS.get(hair, hair),
            "style": md.get("style", "") or "",
            "w": w,
            "h": h,
            "bytes": size,
        })
    sec_rank = {s: i for i, s in enumerate(SEC_ORDER)}
    hair_rank = {h: i for i, h in enumerate(HAIR_ORDER)}
    entries.sort(key=lambda e: (
        sec_rank.get(e["sec"], 99),
        hair_rank.get(e["hair"], 99),
        e["id"],
    ))
    return entries


def build_manifest(root=None, force=False):
    """生成/读取 manifest。返回 dict。"""
    root = os.path.normpath(root or get_library_root())
    try:
        mtime = os.path.getmtime(MANIFEST_PATH)
    except Exception:
        mtime = None
    if not force and _manifest_cache["data"] and _manifest_cache["mtime"] == mtime:
        return _manifest_cache["data"]

    entries = scan_library(root)

    # 分区统计
    sections = []
    for sid in SEC_ORDER:
        n = len([e for e in entries if e["sec"] == sid])
        if n:
            sections.append({"id": sid, "label": SEC_LABELS[sid], "count": n})
    for e in entries:  # 兜底：未登记的 sec 也展示出来
        if e["sec"] and not any(s["id"] == e["sec"] for s in sections):
            sections.append({
                "id": e["sec"],
                "label": SEC_LABELS.get(e["sec"], e["sec"]),
                "count": len([x for x in entries if x["sec"] == e["sec"]]),
            })

    # 发型统计
    hairs = []
    for hid in HAIR_ORDER:
        n = len([e for e in entries if e["hair"] == hid])
        if n:
            hairs.append({"id": hid, "label": HAIR_LABELS[hid], "count": n})
    for e in entries:  # 兜底：未登记的发型也展示出来
        if e["hair"] and not any(h["id"] == e["hair"] for h in hairs):
            hairs.append({
                "id": e["hair"],
                "label": HAIR_LABELS.get(e["hair"], e["hair"]),
                "count": len([x for x in entries if x["hair"] == e["hair"]]),
            })

    manifest = {
        "root": root,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(entries),
        "sections": sections,
        "hairs": hairs,
        "thumb_size": [THUMB_WIDTH, THUMB_HEIGHT],
        "entries": entries,
    }
    try:
        os.makedirs(WEB_DIR, exist_ok=True)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
        _manifest_cache["mtime"] = os.path.getmtime(MANIFEST_PATH)
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] face manifest write failed: %s" % e)
    _manifest_cache["data"] = manifest
    return manifest


def load_manifest():
    """读取 manifest（不存在则现场扫描一次）。"""
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
    """按 id 查 entry（只查 manifest 里的，天然是白名单）。"""
    if not entry_id:
        return None
    for e in load_manifest().get("entries", []):
        if e["id"] == entry_id:
            return e
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 缩略图
# ─────────────────────────────────────────────────────────────────────────────
def thumb_abs_path(entry):
    return os.path.join(THUMB_DIR, "%s.jpg" % entry["id"])


def ensure_thumb(entry):
    """确保某张图的缩略图存在，缺失则按需生成一张（惰性）。"""
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
            # 等比缩放到 THUMB_WIDTH 宽，贴到 THUMB_WIDTH x THUMB_HEIGHT 白底画布
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
        print("[BSAI_Qwen_Prompt_Enhancer] face thumbnail failed %s: %s" % (entry.get("id"), e))
        return False


def ensure_thumbs_bulk(entries=None):
    """批量补齐缩略图，返回 (成功数, 失败数)。"""
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


# ─────────────────────────────────────────────────────────────────────────────
# 参考图选择清单（顺序 = 送进模型的输入顺序）
# ─────────────────────────────────────────────────────────────────────────────
def load_selection():
    try:
        with open(SELECTION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save_selection(items):
    """保存选择清单（items 为 entry id 列表，按顺序）。"""
    valid = []
    seen = set()
    for it in (items or []):
        if isinstance(it, dict):
            eid = it.get("id", "")
        else:
            eid = str(it)
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
        print("[BSAI_Qwen_Prompt_Enhancer] face selection write failed: %s" % e)
    return valid


def selection_text(items=None):
    """把选择清单渲染成多行文本（节点 REFERENCE_LIST 输出）。"""
    items = items if items is not None else load_selection()
    lines = []
    for i, eid in enumerate(items, 1):
        e = find_entry(eid)
        if not e:
            continue
        lines.append("img%d = %s (%s · %s)" % (
            i, e["file"], e["sec_label"], e["hair_label"]))
    return "\n".join(lines)


def selection_prompt_snippet(items=None):
    """生成英文提示词片段（Qwen-Image 2.1 用），参考图编号顺序与清单一致。"""
    items = items if items is not None else load_selection()
    lines = []
    for i, eid in enumerate(items, 1):
        e = find_entry(eid)
        if not e:
            continue
        lines.append(
            "Image %d - %s (%s reference, %s hairstyle)"
            % (i, e["file"], e["sec_label"], e["hair_label"])
        )
    if not lines:
        return ""
    head = "Reference images (use them in exactly this order):"
    tail = (
        "Follow the facial features, hair style, and overall look of each reference image exactly. "
        "Keep the same character identity and hairstyle across all images. "
        "The reference images are face and styling guides only; render them as the final artwork."
    )
    return head + "\n" + "\n".join(lines) + "\n" + tail


# ─────────────────────────────────────────────────────────────────────────────
# 路由注册
# ─────────────────────────────────────────────────────────────────────────────
def register_face_routes():
    """注册肖像海报墙相关路由（在 __init__.py 里调用）。"""
    try:
        from server import PromptServer
        from aiohttp import web

        server = PromptServer.instance
        wall_html = os.path.join(WEB_DIR, "face_wall.html")

        @server.routes.get("/bsai_face_wall")
        async def _bsai_face_wall(request):
            """肖像海报墙直达路由（与 pose/clothing 同思路）。"""
            if not os.path.isfile(wall_html):
                return web.Response(status=404, text="face_wall.html missing")
            return web.FileResponse(wall_html, headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.get("/api/bsai/faces")
        async def _bsai_face_manifest(request):
            """肖像素材清单（分区 / 发型 / 每张图的元数据）。"""
            root = get_library_root()
            m = load_manifest()
            if m.get("root") != root:
                m = build_manifest(root, force=True)
            return web.json_response(m, headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.get("/bsai_face_image")
        async def _bsai_face_image(request):
            """按需返回素材库原图（只认 manifest 白名单里的 id）。"""
            eid = request.query.get("id", "")
            entry = find_entry(eid)
            if not entry:
                return web.Response(status=404, text="unknown face id")
            src = os.path.join(get_library_root(), entry["file"])
            if not os.path.isfile(src):
                return web.Response(status=404, text="source file missing")
            return web.FileResponse(src, headers={"Cache-Control": "public, max-age=86400"})

        @server.routes.get("/bsai_face_thumb")
        async def _bsai_face_thumb(request):
            """按需返回缩略图（缺失时实时生成一张）。"""
            eid = request.query.get("id", "")
            entry = find_entry(eid)
            if not entry:
                return web.Response(status=404, text="unknown face id")
            if not ensure_thumb(entry):
                return web.Response(status=404, text="thumbnail missing")
            return web.FileResponse(thumb_abs_path(entry),
                                    headers={"Cache-Control": "public, max-age=604800"})

        @server.routes.get("/api/bsai/face_selection")
        async def _bsai_face_selection_get(request):
            return web.json_response(
                {"items": load_selection(), "text": selection_text()},
                headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.post("/bsai_face_selection")
        async def _bsai_face_selection_post(request):
            """保存当前选择（顺序即输入顺序），供节点输出 / 跨页恢复。"""
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"ok": False, "message": "invalid json"}, status=400)
            items = data.get("items")
            if not isinstance(items, list):
                return web.json_response({"ok": False, "message": "items must be a list"}, status=400)
            saved = save_selection(items)
            return web.json_response({"ok": True, "items": saved, "text": selection_text(saved)})

        @server.routes.post("/bsai_face_rescan")
        async def _bsai_face_rescan(request):
            """重新扫描素材库 + 补齐缩略图。"""
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

        print("[BSAI_Qwen_Prompt_Enhancer] face wall routes registered: GET /bsai_face_wall · /api/bsai/faces · /bsai_face_image · /bsai_face_thumb")
        return True
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] face wall route registration failed (non-fatal): %s" % e)
        return False
