# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — AI 姿势素材库节点
节点: BSAI_Qwen_Pose_Wall

把「AI 姿势海报墙」（web/pose_wall.html）里挑好的姿势参考图，整理成带编号的清单输出：
  · REFERENCE_LIST —— 中文编号清单（第 1 项 = image_1，第 2 项 = image_2 …）
  · PROMPT_SNIPPET —— 可直接粘进 Qwen-Image 2.1 的英文提示词片段（自带图序）
  · SUMMARY        —— 素材库统计摘要（总张数 / 组数 / 机位数 / 已选张数 / 素材库路径）

海报墙上的选择顺序 = 这里的编号顺序 = 模型 image_1..image_N 的输入顺序，
用户最在意的「参考图编号 + 输入顺序」由这条链路统一保证。

节点底部的「🖼 打开姿势海报墙」按钮由前端 JS 注入（web/prompt_enhancer.js）。
"""
import os
import hashlib

from . import pose_library as pl
from . import wall_images as wi


class BSAI_Qwen_Pose_Wall:
    """AI pose reference library (wall selection -> numbered reference list)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "library_root": ("STRING", {
                    "default": pl.get_library_root(),
                    "multiline": False,
                    "tooltip": "Root directory of the pose reference library. Check apply_root below and run once to rebuild.",
                }),
                "apply_root": ("BOOLEAN", {
                    "default": False,
                    "label": "Apply library root (rescan manifest)",
                    "tooltip": "Save the path above as plugin config and rescan the library (check once).",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("REFERENCE_LIST", "PROMPT_SNIPPET", "SUMMARY", "IMAGE")
    FUNCTION = "get_pose_references"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """姿势墙选择清单是节点外部状态（墙页卡点只写服务端 JSON）。
        按 selection.json 内容做哈希，换图后强制重跑，避免命中缓存吐旧图。"""
        try:
            with open(pl.SELECTION_PATH, "r", encoding="utf-8") as f:
                return hashlib.sha1(f.read().encode("utf-8")).hexdigest()
        except Exception:
            return ""

    DESCRIPTION = (
        "AI pose reference library: reads poses selected in the Pose Wall (🖼 button below the node), "
        "and outputs a numbered reference list (REFERENCE_LIST), an English prompt snippet (PROMPT_SNIPPET), "
        "a stats summary (SUMMARY), and the selected reference images as an IMAGE batch (IMAGE).\n"
        "Order = input order: item 1 maps to the enhancer node's image_1, item 2 to image_2..."
    )

    def get_pose_references(self, library_root="", apply_root=False):
        # 1) Only persist + rescan when user explicitly asks
        root = pl.get_library_root()
        if apply_root:
            wanted = str(library_root or "").strip()
            if wanted and os.path.normpath(wanted) != os.path.normpath(root):
                try:
                    root = pl.set_library_root(wanted)
                    pl.build_manifest(root, force=True)
                    print("[BSAI_Qwen_Prompt_Enhancer] pose library root switched: %s" % root)
                except Exception as e:
                    print("[BSAI_Qwen_Prompt_Enhancer] pose library root switch failed: %s" % e)

        # 2) Selection list (wall selection results)
        manifest = pl.load_manifest()
        if manifest.get("root") != root:
            manifest = pl.build_manifest(root, force=True)

        items = pl.load_selection()
        ref_list = pl.selection_text(items)
        prompt = pl.selection_prompt_snippet(items)

        groups = len(manifest.get("groups", []))
        views = len(manifest.get("views", []))
        total = manifest.get("count", 0)
        summary = "Pose library: %d images · %d groups · %d views · %d selected | %s" % (
            total, groups, views, len(items), manifest.get("root", root))
        if not items:
            summary += " | (no poses selected — click the 🖼 Pose Wall button below to pick)"

        image, _kept, _info = wi.load_wall_images(pl, "Pose Wall")
        return (ref_list, prompt, summary, image)


NODE_CLASS_MAPPINGS = {
    "BSAI_Qwen_Pose_Wall": BSAI_Qwen_Pose_Wall,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Qwen_Pose_Wall": "AI Pose Reference Wall",
}
