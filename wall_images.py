# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 单面海报墙已选图 → IMAGE batch 直出

供 Pose / Clothing / Face 三面墙节点复用：读取该墙 selection.json 里勾选的
参考图（顺序 = 墙上勾选顺序 = 下游 image_1..image_N 输入顺序），拼成一个
ComfyUI IMAGE tensor（B,H,W,3，float32，0..1）直出给下游。

· 单张：保持原尺寸，不加白边；
· 多张：尺寸不一致时按最大画布居中、白底 letterbox；
· 无选中图 / 读图失败：返回 64x64 纯白占位图，保证下游不断链。

每个 library 模块需提供与 pose_library 一致的接口：
  load_selection() / find_entry(eid) / get_library_root() / entry["file"]
"""
import os

PLACEHOLDER_SIDE = 64
_MAX_ITEMS = 16


def _entry_id(it):
    """selection.json 条目可能是 eid 字符串，也可能是 {"id": ...} dict。"""
    if isinstance(it, dict):
        return str(it.get("id", "") or "")
    return str(it or "")


def _entry_label(entry):
    return (entry.get("group_label") or entry.get("category_label")
            or entry.get("cat_label") or entry.get("sec_label") or "")


def _placeholder(wall_label="wall", reason=""):
    """无可用图时的白底占位图（同时打印原因，避免静默出白图）。"""
    msg = "── %s IMAGE ── no usable selected image -> %dx%d white placeholder" % (
        wall_label, PLACEHOLDER_SIDE, PLACEHOLDER_SIDE)
    if reason:
        msg += " (%s)" % reason
    try:
        import torch
        return torch.ones((1, PLACEHOLDER_SIDE, PLACEHOLDER_SIDE, 3),
                          dtype=torch.float32), [], msg
    except Exception as e:
        print("[BSAI_Qwen_Prompt_Enhancer] %s: torch 不可用，无法生成占位图: %s" % (wall_label, e))
        return None, [], msg


def load_wall_images(lib, wall_label="wall", max_items=_MAX_ITEMS):
    """读取某一面墙的已选图，返回 (image_tensor, kept, info_text)。

    kept: [(img_index, abs_path, label), ...]，1-based，顺序与 batch 一致。
    """
    items = lib.load_selection() or []
    root = lib.get_library_root()

    picks = []
    for it in items:
        eid = _entry_id(it)
        if not eid:
            continue
        entry = lib.find_entry(eid)
        if not entry:
            print("[BSAI_Qwen_Prompt_Enhancer] %s 条目不在清单白名单内，已忽略: %s" % (wall_label, eid))
            continue
        path = os.path.join(root, entry["file"])
        if not os.path.isfile(path):
            print("[BSAI_Qwen_Prompt_Enhancer] %s 图片文件缺失，已忽略: %s" % (wall_label, path))
            continue
        picks.append((eid, path, _entry_label(entry)))

    if not picks:
        return _placeholder(wall_label, "海报墙没有选中任何图")

    if len(picks) > max_items:
        print("[BSAI_Qwen_Prompt_Enhancer] %s 已选 %d 张，超过上限 %d，只输出前 %d 张"
              % (wall_label, len(picks), max_items, max_items))
        picks = picks[:max_items]

    try:
        import numpy as np
        import torch
        from PIL import Image
    except Exception as e:
        return _placeholder(wall_label, "图像库不可用: %s" % e)

    arrays = []
    kept = []
    for pos, (eid, path, label) in enumerate(picks, 1):
        try:
            with Image.open(path) as im:
                arrays.append(np.asarray(im.convert("RGB")))
            kept.append((pos, path, label))
        except Exception as e:
            print("[BSAI_Qwen_Prompt_Enhancer] %s 读图失败，跳过 %s: %s" % (wall_label, path, e))

    if not arrays:
        return _placeholder(wall_label, "选中的图全部读取失败")

    if len(arrays) == 1:
        tensor = torch.from_numpy(arrays[0].astype("float32") / 255.0)[None, ...]
        h, w = arrays[0].shape[0], arrays[0].shape[1]
        info = "── %s IMAGE（直出 @img%d）── %s\n%s" % (wall_label, kept[0][0], kept[0][2], kept[0][1])
        print("[BSAI_Qwen_Prompt_Enhancer] %s IMAGE: 直出 @img%d · %dx%d · %s"
              % (wall_label, kept[0][0], w, h, kept[0][1]))
        return tensor, kept, info

    max_h = max(a.shape[0] for a in arrays)
    max_w = max(a.shape[1] for a in arrays)
    batch = np.full((len(arrays), max_h, max_w, 3), 255, dtype="uint8")
    for i, a in enumerate(arrays):
        h, w = a.shape[0], a.shape[1]
        y0 = (max_h - h) // 2
        x0 = (max_w - w) // 2
        batch[i, y0:y0 + h, x0:x0 + w] = a

    tensor = torch.from_numpy(batch.astype("float32") / 255.0)
    info = "── %s IMAGE（batch=%d，画布 %dx%d）──" % (wall_label, len(kept), max_w, max_h)
    for idx, path, label in kept:
        info += "\n@img%d = %s | %s" % (idx, label, path)
    print("[BSAI_Qwen_Prompt_Enhancer] %s IMAGE: 输出 %d 张 · 画布 %dx%d"
          % (wall_label, len(kept), max_w, max_h))
    return tensor, kept, info
