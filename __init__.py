# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 豆包/ComfyUI 自定义插件

把用户大白话提示词，按 Qwen Image 2.1 官方 PE 规则增强为可直接用于生成的高质量提示词。

节点清单（2026-09-21 起三合一）:
  1. BSAI_Qwen_Prompt_Enhancer   — 三合一增强通道（backend 下拉切换: 官方PE / 本地LLaMA / API）
  2. QwenImage21_Prompt_Template — Qwen Image 2.1 官方增强提示词模板库

官方 PE 模型使用:
  将 PE 权重放入 models/text_encoders/（相对路径），用 CLIPLoader 加载（type 任意，
  自动检测为 QWEN35_9B），再接入 BSAI_Qwen_Prompt_Enhancer 的 clip 输入（backend=官方PE）。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .nodes_enhancer import NODE_CLASS_MAPPINGS as _ENH, NODE_DISPLAY_NAME_MAPPINGS as _ENH_D
from .nodes_template import NODE_CLASS_MAPPINGS as _TPL, NODE_DISPLAY_NAME_MAPPINGS as _TPL_D
from .nodes_jev import NODE_CLASS_MAPPINGS as _JEV, NODE_DISPLAY_NAME_MAPPINGS as _JEV_D
from .nodes_markdown import NODE_CLASS_MAPPINGS as _MD, NODE_DISPLAY_NAME_MAPPINGS as _MD_D

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
for m in (_ENH, _TPL, _JEV, _MD):
    NODE_CLASS_MAPPINGS.update(m)
for m in (_ENH_D, _TPL_D, _JEV_D, _MD_D):
    NODE_DISPLAY_NAME_MAPPINGS.update(m)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

# ComfyUI 前端 JS 扩展目录（注入"打开海报墙"按钮 + backend 动态显隐参数）
WEB_DIRECTORY = "./web"

# 【v1.03.0】动态模板 API：/api/bsai/templates
# 返回内置模板 + 用户模板区（user_templates/）的合并结果（含全文），
# 供海报墙与前端下拉实时读取：用户每次新增自定义模板，无需改静态文件即可立即生效。

# 【v1.06.0】缩略图自动同步工具链（保存/上传模板时自动生成或同步缩略图到海报墙）
def _bsai_thumb_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "thumbnails")
    os.makedirs(d, exist_ok=True)
    return d


def _bsai_thumb_path(tid):
    return os.path.join(_bsai_thumb_dir(), "%s.png" % tid)


def _bsai_save_thumb_bytes(raw, dest):
    if not raw:
        return False
    try:
        with open(dest, "wb") as f:
            f.write(raw)
        return os.path.getsize(dest) > 100
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] 缩略图写盘失败: %s" % e)
        return False


def _bsai_save_thumb_from_url(url, dest):
    try:
        import urllib.request as _u
        with _u.urlopen(url, timeout=20) as r:
            return _bsai_save_thumb_bytes(r.read(), dest)
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] 缩略图 URL 下载失败: %s -> %s" % (url, e))
        return False


def _bsai_save_thumb_from_b64(b64, dest):
    try:
        import base64 as _b
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        return _bsai_save_thumb_bytes(_b.b64decode(b64), dest)
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] 缩略图 base64 解码失败: %s" % e)
        return False


def _bsai_gen_thumb_placeholder(name, desc, tid):
    """PIL 程序合成 448x448 用户模板占位缩略图（绿色分类条+模板名+描述+百声AI底标），
    自动同步到海报墙 thumbnails/{tid}.png。无 PIL 环境时跳过（海报墙 onerror 有 SVG 兜底）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    dest = _bsai_thumb_path(tid)
    W, H = 448, 448
    img = Image.new("RGB", (W, H), "#0f172a")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 48], fill="#16a34a")
    d.rectangle([0, H - 58, W, H], fill="#1e293b")
    try:
        f_label = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 20)
        f_name = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 34)
        f_desc = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
        f_logo = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    except Exception:
        f_label = f_name = f_desc = f_logo = ImageFont.load_default()
    d.text((18, 12), "用户模板 · USER TEMPLATE", font=f_label, fill="#ffffff")
    nm = str(name or tid or "模板")
    d.text((24, 110), nm[:10], font=f_name, fill="#fbbf24")
    ds = str(desc or "").strip() or "用户自定义共享模板"
    d.text((24, 200), ds[:30], font=f_desc, fill="#cbd5e1")
    d.text((W // 2 - 66, H - 48), "百声AI · BSAI", font=f_logo, fill="#94a3b8")
    img.save(dest, "PNG")
    return True


def _bsai_ensure_user_thumb(tid, name, desc):
    """缩略图缺失时惰性生成占位卡（老用户模板/合成失败自动补齐）"""
    if not tid:
        return False
    dest = _bsai_thumb_path(tid)
    if os.path.exists(dest) and os.path.getsize(dest) > 100:
        return True
    return _bsai_gen_thumb_placeholder(name, desc, tid)


def _bsai_apply_thumbnail(tid, thumb, raw_bytes=None):
    """按优先级落地缩略图：raw_bytes > base64/URL/本地路径 > 程序合成"""
    if not tid:
        return False
    dest = _bsai_thumb_path(tid)
    if raw_bytes:
        return _bsai_save_thumb_bytes(raw_bytes, dest)
    if isinstance(thumb, str) and thumb:
        if thumb.startswith("data:") or thumb.startswith("base64,"):
            return _bsai_save_thumb_from_b64(thumb, dest)
        if thumb.startswith("http://") or thumb.startswith("https://"):
            return _bsai_save_thumb_from_url(thumb, dest)
        if os.path.isfile(thumb):
            try:
                with open(thumb, "rb") as f:
                    return _bsai_save_thumb_bytes(f.read(), dest)
            except Exception:
                return False
    return _bsai_gen_thumb_placeholder("", "", tid)


def _bsai_latest_output_url():
    """output 目录最新一张生成图 -> (view 相对 URL or None, 文件名)"""
    try:
        import glob as _g
        out = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "output"))
        pats = []
        for ext in ("png", "jpg", "jpeg", "webp"):
            pats += _g.glob(os.path.join(out, "*.%s" % ext))
        if not pats:
            return None, None
        fn = max(pats, key=os.path.getmtime)
        import urllib.parse as _up
        return "/view?filename=%s&type=output&subfolder=" % _up.quote(os.path.basename(fn)), os.path.basename(fn)
    except Exception:
        return None, None


def _register_template_api():
    try:
        import json as _json
        from server import PromptServer
        from aiohttp import web
        from .common import PLUGIN_ROOT, load_text, TEMPLATES_JSON, load_user_templates

        server = PromptServer.instance

        @server.routes.get("/api/bsai/templates")
        def _bsai_templates(request):
            try:
                with open(TEMPLATES_JSON, "r", encoding="utf-8") as f:
                    data = _json.load(f)
            except Exception:
                data = {"meta": {}, "templates": []}
            templates = list(data.get("templates", [])) + load_user_templates()
            items = []
            for t in templates:
                if t.get("file"):
                    txt = load_text(os.path.join(PLUGIN_ROOT, t["file"]), "")
                else:
                    txt = t.get("text", "")
                if t.get("type") == "user":
                    _bsai_ensure_user_thumb(t.get("id"), t.get("name", ""), t.get("desc", ""))
                items.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "type": t.get("type", "?"),
                    "desc": t.get("desc", ""),
                    "text": txt,
                })
            return web.json_response(
                {"meta": data.get("meta", {}), "templates": items},
                headers={"Cache-Control": "no-store, max-age=0"},
            )

        print("[BSAI_Qwen_Prompt_Enhancer] 模板 API 已注册: GET /api/bsai/templates")
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 模板 API 注册失败(不影响节点): {e}")

_register_template_api()

# 【v1.04.0】海报墙直达路由：GET /bsai_templates_wall
# 部分 ComfyUI 版本/网络环境下，前端 /extensions/ 静态路由会返回无效响应
# （浏览器报 ERR_INVALID_RESPONSE，海报墙打不开）。本路由由插件直接
# FileResponse 返回 templates_wall.html，绕开前端静态服务，任何版本都能打开。
def _register_wall_route():
    try:
        from server import PromptServer
        from aiohttp import web
        wall_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "templates_wall.html")

        server = PromptServer.instance

        @server.routes.get("/bsai_templates_wall")
        async def _bsai_wall(request):
            # v1.06.0: 禁止缓存——浏览器每次打开海报墙都拉取最新 HTML/缩略图列表
            return web.FileResponse(wall_html, headers={"Cache-Control": "no-store, max-age=0"})

        print("[BSAI_Qwen_Prompt_Enhancer] 海报墙直达路由已注册: GET /bsai_templates_wall")
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 海报墙直达路由注册失败(不影响节点): {e}")

_register_wall_route()

# 【v1.06.0】用户模板写入 API：
#   POST /bsai_save_user_template   {name, desc, text}           -> 存为 user_templates/{name}.json
#   POST /bsai_upload_user_template multipart file(.json)         -> 校验后写入 user_templates/（多条目自动拆分）
# load_user_templates() 每次实时扫描 user_templates/，保存/上传后无需重启，下拉与海报墙即时可见。
def _register_user_template_api():
    try:
        import json as _json
        import re as _re
        from server import PromptServer
        from aiohttp import web
        from .common import USER_TEMPLATES_DIR

        os.makedirs(USER_TEMPLATES_DIR, exist_ok=True)

        def _safe_name(name):
            s = _re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(name or "").strip())
            return s or "untitled"

        def _unique_path(base_stem, ext=".json"):
            p = os.path.join(USER_TEMPLATES_DIR, base_stem + ext)
            n = 2
            while os.path.exists(p):
                p = os.path.join(USER_TEMPLATES_DIR, "%s (%d)%s" % (base_stem, n, ext))
                n += 1
            return p

        server = PromptServer.instance

        @server.routes.post("/bsai_save_user_template")
        async def _bsai_save_template(request):
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"ok": False, "message": "请求体不是有效 JSON"})
            name = _safe_name(str(data.get("name") or ""))
            text = str(data.get("text") or "").strip()
            desc = str(data.get("desc") or "用户自定义共享模板").strip()
            if not text:
                return web.json_response({"ok": False, "message": "模板内容为空，无法保存"})
            path = _unique_path(name)
            tid = "user_" + os.path.splitext(os.path.basename(path))[0].lower().replace(" ", "_")
            payload = {"id": tid, "name": name, "type": "user", "desc": desc, "text": text}
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(payload, f, ensure_ascii=False, indent=2)
            # 【v1.06.0】缩略图自动同步：请求带 thumbnail(URL/base64) 则落地；无则程序合成占位卡
            thumb = data.get("thumbnail") or ""
            if isinstance(thumb, str) and thumb.startswith("/view"):
                try:
                    thumb = "http://%s%s" % (request.host or "127.0.0.1:8188", thumb)
                except Exception:
                    thumb = ""
            _bsai_apply_thumbnail(tid, thumb)
            print(f"[BSAI_Qwen_Prompt_Enhancer] 已保存用户模板: {os.path.basename(path)} (缩略图已同步海报墙)")
            return web.json_response({"ok": True, "name": name, "file": os.path.basename(path), "id": tid})

        @server.routes.post("/bsai_upload_user_template")
        async def _bsai_upload_template(request):
            try:
                reader = await request.multipart()
                fld = await reader.next()
                if not fld or fld.name != "file":
                    return web.json_response({"ok": False, "message": "未找到上传文件字段 'file'"})
                fn = fld.filename or "template.json"
                if not str(fn).lower().endswith(".json"):
                    return web.json_response({"ok": False, "message": "仅支持 .json 模板文件"})
                raw = await fld.read()
                try:
                    parsed = _json.loads(raw.decode("utf-8"))
                except Exception:
                    return web.json_response({"ok": False, "message": "文件不是有效 JSON"})
                items = parsed if isinstance(parsed, list) else parsed.get("templates", [parsed] if isinstance(parsed, dict) else [])
                if not isinstance(items, list) or not items:
                    return web.json_response({"ok": False, "message": "JSON 中没有模板条目（需含 name 字段）"})
                # 【v1.06.0】multipart 可选 thumbnail 文件字段（单模板场景使用）
                thumb_bytes = None
                try:
                    nxt = await reader.next()
                    if nxt and nxt.name == "thumbnail":
                        thumb_bytes = await nxt.read()
                except Exception:
                    thumb_bytes = None
                saved = []
                for it in items:
                    if not isinstance(it, dict) or not it.get("name"):
                        continue
                    nm = _safe_name(str(it["name"]))
                    path = _unique_path(nm)
                    tid = "user_" + os.path.splitext(os.path.basename(path))[0].lower().replace(" ", "_")
                    payload = dict(it)
                    payload["id"] = tid
                    payload.setdefault("type", "user")
                    payload.setdefault("desc", "用户自定义共享模板")
                    # file 引用字段在共享模板场景不可靠（相对路径可能不存在），一律内联 text
                    payload.pop("file", None)
                    it_thumb = payload.pop("thumbnail", None)
                    with open(path, "w", encoding="utf-8") as f:
                        _json.dump(payload, f, ensure_ascii=False, indent=2)
                    # 【v1.06.0】缩略图自动同步：multipart文件 > JSON内thumbnail(URL/base64/本地路径) > 程序合成占位卡
                    if len(items) == 1 and thumb_bytes:
                        _bsai_apply_thumbnail(tid, None, raw_bytes=thumb_bytes)
                    elif isinstance(it_thumb, str) and it_thumb:
                        _bsai_apply_thumbnail(tid, it_thumb)
                    else:
                        _bsai_apply_thumbnail(tid, None)
                    saved.append(os.path.basename(path))
                if not saved:
                    return web.json_response({"ok": False, "message": "JSON 中无有效模板条目（缺少 name 字段）"})
                print(f"[BSAI_Qwen_Prompt_Enhancer] 已上传用户模板: {', '.join(saved)}")
                return web.json_response({"ok": True, "files": saved})
            except Exception as e:
                return web.json_response({"ok": False, "message": "上传失败: %s" % e})

        @server.routes.get("/bsai_latest_output")
        def _bsai_latest_output(request):
            """返回 output 目录最新一张生成图（供前端保存模板时自动作为缩略图）"""
            url, fn = _bsai_latest_output_url()
            if not url:
                return web.json_response({"ok": False, "message": "output 目录暂无生成图片"})
            return web.json_response({"ok": True, "url": url, "filename": fn})

        print("[BSAI_Qwen_Prompt_Enhancer] 用户模板写入 API 已注册: POST /bsai_save_user_template / POST /bsai_upload_user_template / GET /bsai_latest_output")
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 用户模板写入 API 注册失败(不影响节点): {e}")

_register_user_template_api()


# 【v1.03.0】启动横幅：ComfyUI 日志第一屏即可确认加载的插件版本。
_PLUGIN_VERSION = "v1.06.0 (2026-09-24)"
print(f"[BSAI_Qwen_Prompt_Enhancer] 插件已加载 | 版本 {_PLUGIN_VERSION} | "
      f"已含: 新旧版ComfyUI校验兼容 / 前端combo自愈 / Jev并行决策 / 海报墙134模板11分类+用户模板区 / MarkdownNote兼容 / 潜空间放大示例 / 动态模板API / 海报墙直达路由")

