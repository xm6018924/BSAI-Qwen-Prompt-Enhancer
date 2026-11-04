# -*- coding: utf-8 -*-
"""
BSAI AI姿势素材库后端 —— 姿势海报墙（Pose Wall）

素材库来源：C:\\BSAI\\AI资料\\素材库离线版带网页预览\\AI姿势
命名规则：{组}_P{编号}_{机位}.png   例：full_sexy_P001_front.png
  · 组（group）：full_sexy / full_single / pair60 / upper80v2
  · 编号（pose）：P001 ~ P080
  · 机位（view）：front / high / low / side / diag

本模块负责：
  1. 扫描素材库 -> manifest（清单 JSON）
  2. 缩略图惰性生成（web/pose_thumbnails/）
  3. 参考图选择清单的持久化（pose_selection.json，供节点输出）
  4. 注册海报墙相关路由（直达路由 + 清单 API + 原图按需服务）

设计要点：
  · 原图不复制、不缓存，直接从素材库按需流式返回（省 600MB+ 磁盘）
  · 缩略图只做小图（300x400 JPEG），海报墙滚动才不卡
  · 所有读取都走 manifest 白名单，路由不接受任意路径
"""
import json
import os
import re
import time

try:
    from .common import PLUGIN_ROOT
except ImportError:  # 独立脚本运行时（gen_pose_thumbs.py）没有包上下文
    PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))

WEB_DIR = os.path.join(PLUGIN_ROOT, "web")
THUMB_DIR = os.path.join(WEB_DIR, "pose_thumbnails")
MANIFEST_PATH = os.path.join(WEB_DIR, "pose_manifest.json")
SELECTION_PATH = os.path.join(PLUGIN_ROOT, "pose_selection.json")
CONFIG_PATH = os.path.join(PLUGIN_ROOT, "pose_library.json")

# 素材库默认根目录（可在 pose_library.json / 环境变量 BSAI_POSE_LIBRARY 里覆盖）
DEFAULT_LIBRARY_ROOT = r"C:\BSAI\AI资料\素材库离线版带网页预览\AI姿势"

THUMB_WIDTH = 300
THUMB_HEIGHT = 400
THUMB_QUALITY = 82

# Pose group -> display label
GROUP_LABELS = {
    "full_sexy": "Full Body · Sexy",
    "full_single": "Full Body · Single",
    "pair60": "Pair Interaction",
    "upper80v2": "Upper Body v2",
}

# Camera view -> display label
VIEW_LABELS = {
    "front": "Front",
    "high": "High Angle",
    "low": "Low Angle",
    "side": "Side",
    "diag": "Diagonal",
}

# 机位展示顺序（与素材库的命名习惯一致）
VIEW_ORDER = ["front", "high", "low", "side", "diag"]

# 文件名解析：{组}_P{编号}_{机位}.png
_NAME_RE = re.compile(r"^(?P<group>.+?)_P(?P<pose>\d{2,4})_(?P<view>[a-zA-Z]+)\.(?P<ext>png|jpg|jpeg|webp)$")

# manifest 内存缓存
_manifest_cache = {"data": None, "mtime": None}
_manifest_lock_placeholder = None


# ─────────────────────────────────────────────────────────────────────────────
# 配置 / 路径
# ─────────────────────────────────────────────────────────────────────────────
def get_library_root():
    """素材库根目录：环境变量 > pose_library.json > 默认值。

    pose_library.json 形如： {"root": "D:\\素材库\\AI姿势"}
    """
    env = os.environ.get("BSAI_POSE_LIBRARY", "").strip()
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
    """把素材库根目录写进 pose_library.json（供节点/用户持久化）。"""
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


# ─────────────────────────────────────────────────────────────────────────────
# 扫描
# ─────────────────────────────────────────────────────────────────────────────
def _image_size(path):
    """读图片尺寸；PIL 不可用时返回 (0, 0)。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


def scan_library(root=None):
    """扫描素材库目录，返回 entry 列表（已按 组/编号/机位 排序）。"""
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
        group = m.group("group")
        pose = m.group("pose")
        view = m.group("view").lower()
        eid = "%s_P%s_%s" % (group, pose, view)
        try:
            size = os.path.getsize(full)
        except Exception:
            size = 0
        w, h = _image_size(full)
        entries.append({
            "id": eid,
            "file": fn,
            "group": group,
            "group_label": GROUP_LABELS.get(group, group),
            "pose": pose,
            "view": view,
            "view_label": VIEW_LABELS.get(view, view),
            "w": w,
            "h": h,
            "bytes": size,
            "thumb": "pose_thumbnails/%s.jpg" % eid,
        })
    # 组按 GROUP_LABELS 的登记顺序，机位按 VIEW_ORDER，编号升序
    group_rank = {g: i for i, g in enumerate(GROUP_LABELS.keys())}
    view_rank = {v: i for i, v in enumerate(VIEW_ORDER)}
    entries.sort(key=lambda e: (
        group_rank.get(e["group"], 99),
        int(e["pose"]),
        view_rank.get(e["view"], 99),
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
    groups = []
    for gid in GROUP_LABELS.keys():
        n = len([e for e in entries if e["group"] == gid])
        if n:
            groups.append({"id": gid, "label": GROUP_LABELS[gid], "count": n})
    for e in entries:  # 兜底：未登记的组也展示出来
        if not any(g["id"] == e["group"] for g in groups):
            groups.append({
                "id": e["group"],
                "label": GROUP_LABELS.get(e["group"], e["group"]),
                "count": len([x for x in entries if x["group"] == e["group"]]),
            })
    views = []
    for vid in VIEW_ORDER:
        n = len([e for e in entries if e["view"] == vid])
        if n:
            views.append({"id": vid, "label": VIEW_LABELS.get(vid, vid), "count": n})
    for e in entries:
        if not any(v["id"] == e["view"] for v in views):
            views.append({
                "id": e["view"],
                "label": VIEW_LABELS.get(e["view"], e["view"]),
                "count": len([x for x in entries if x["view"] == e["view"]]),
            })
    poses = sorted({e["pose"] for e in entries}, key=lambda p: int(p))

    manifest = {
        "root": root,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(entries),
        "groups": groups,
        "views": views,
        "poses": poses,
        "thumb_size": [THUMB_WIDTH, THUMB_HEIGHT],
        "entries": entries,
    }
    try:
        os.makedirs(WEB_DIR, exist_ok=True)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
        _manifest_cache["mtime"] = os.path.getmtime(MANIFEST_PATH)
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] pose manifest write failed: %s" % e)
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
        print("[BSAI_Qwen_Prompt_Enhancer] thumbnail generation failed %s: %s" % (entry.get("id"), e))
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
        print("[BSAI_Qwen_Prompt_Enhancer] selection list write failed: %s" % e)
    return valid


def selection_text(items=None):
    """把选择清单渲染成多行文本（节点 REFERENCE_LIST 输出）。"""
    items = items if items is not None else load_selection()
    lines = []
    for i, eid in enumerate(items, 1):
        e = find_entry(eid)
        if not e:
            continue
        lines.append("img%d = %s (%s · P%s · %s)" % (
            i, e["file"], e["group_label"], e["pose"], e["view_label"]))
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
            "Image %d - %s (%s, pose %s, %s view, 3D mannequin pose reference, white background)"
            % (i, e["file"], e["group_label"], e["pose"], e["view_label"])
        )
    if not lines:
        return ""
    head = "Reference images (use them in exactly this order):"
    tail = (
        "Follow the body pose and camera angle of each reference image exactly. "
        "Keep the same character, outfit, hairstyle and lighting across all images. "
        "The reference images are pose and camera-angle guides only; render them as the final artwork."
    )
    return head + "\n" + "\n".join(lines) + "\n" + tail


# ─────────────────────────────────────────────────────────────────────────────
# 路由注册
# ─────────────────────────────────────────────────────────────────────────────
def register_pose_routes():
    """注册姿势海报墙相关路由（在 __init__.py 里调用）。"""
    try:
        from server import PromptServer
        from aiohttp import web

        server = PromptServer.instance
        wall_html = os.path.join(WEB_DIR, "pose_wall.html")

        @server.routes.get("/bsai_pose_wall")
        async def _bsai_pose_wall(request):
            """姿势海报墙直达路由（与 /bsai_templates_wall 同思路，绕开前端静态路由）。"""
            if not os.path.isfile(wall_html):
                return web.Response(status=404, text="pose_wall.html missing")
            return web.FileResponse(wall_html, headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.get("/api/bsai/poses")
        async def _bsai_pose_manifest(request):
            """姿势素材清单（分组 / 机位 / 编号 / 每张图的元数据）。"""
            root = get_library_root()
            m = load_manifest()
            if m.get("root") != root:
                m = build_manifest(root, force=True)
            return web.json_response(m, headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.get("/bsai_pose_image")
        async def _bsai_pose_image(request):
            """按需返回素材库原图（只认 manifest 白名单里的 id）。"""
            eid = request.query.get("id", "")
            entry = find_entry(eid)
            if not entry:
                return web.Response(status=404, text="unknown pose id")
            src = os.path.join(get_library_root(), entry["file"])
            if not os.path.isfile(src):
                return web.Response(status=404, text="source file missing")
            return web.FileResponse(src, headers={"Cache-Control": "public, max-age=86400"})

        @server.routes.get("/bsai_pose_thumb")
        async def _bsai_pose_thumb(request):
            """按需返回缩略图（缺失时实时生成一张）。"""
            eid = request.query.get("id", "")
            entry = find_entry(eid)
            if not entry:
                return web.Response(status=404, text="unknown pose id")
            if not ensure_thumb(entry):
                return web.Response(status=404, text="thumbnail missing")
            return web.FileResponse(thumb_abs_path(entry),
                                    headers={"Cache-Control": "public, max-age=604800"})

        @server.routes.get("/api/bsai/pose_selection")
        async def _bsai_pose_selection_get(request):
            return web.json_response(
                {"items": load_selection(), "text": selection_text()},
                headers={"Cache-Control": "no-store, max-age=0"})

        @server.routes.post("/bsai_pose_selection")
        async def _bsai_pose_selection_post(request):
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

        @server.routes.post("/bsai_pose_rescan")
        async def _bsai_pose_rescan(request):
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

        print("[BSAI_Qwen_Prompt_Enhancer] pose wall routes registered: GET /bsai_pose_wall · /api/bsai/poses · /bsai_pose_image · /bsai_pose_thumb")
        return True
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] pose wall route registration failed (non-fatal): %s" % e)
        return False
