# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — AI face/styling reference node
Node: BSAI_Qwen_Face_Wall
"""
import os
import hashlib

from . import face_library as fl
from . import wall_images as wi


class BSAI_Qwen_Face_Wall:
    """AI face/styling reference library (wall selection -> numbered reference list)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "library_root": ("STRING", {
                    "default": fl.get_library_root(),
                    "multiline": False,
                    "tooltip": "Root directory of the face/styling reference library. Check apply_root below and run once to rebuild.",
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
    FUNCTION = "get_face_references"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """人脸墙选择清单是节点外部状态，按 selection.json 内容哈希强制重跑。"""
        try:
            with open(fl.SELECTION_PATH, "r", encoding="utf-8") as f:
                return hashlib.sha1(f.read().encode("utf-8")).hexdigest()
        except Exception:
            return ""

    DESCRIPTION = (
        "AI face/styling reference library: reads faces selected in the Face Wall (🖼 button below the node), "
        "and outputs a numbered reference list (REFERENCE_LIST), an English prompt snippet (PROMPT_SNIPPET), "
        "a stats summary (SUMMARY), and the selected reference images as an IMAGE batch (IMAGE).\n"
        "Order = input order: item 1 maps to the enhancer node's image_1, item 2 to image_2...\n"
        "Source: PoseAtlas portrait atlas (faces 893 + styling 606), CC0 1.0."
    )

    def get_face_references(self, library_root="", apply_root=False):
        root = fl.get_library_root()
        if apply_root:
            wanted = str(library_root or "").strip()
            if wanted and os.path.normpath(wanted) != os.path.normpath(root):
                try:
                    root = fl.set_library_root(wanted)
                    fl.build_manifest(root, force=True)
                    print("[BSAI_Qwen_Prompt_Enhancer] face library root switched: %s" % root)
                except Exception as e:
                    print("[BSAI_Qwen_Prompt_Enhancer] face library root switch failed: %s" % e)

        manifest = fl.load_manifest()
        if manifest.get("root") != root:
            manifest = fl.build_manifest(root, force=True)

        items = fl.load_selection()
        ref_list = fl.selection_text(items)
        prompt = fl.selection_prompt_snippet(items)

        secs = len(manifest.get("sections", []))
        total = manifest.get("count", 0)
        summary = "Face library: %d images · %d sections · %d selected | %s" % (
            total, secs, len(items), manifest.get("root", root))
        if not items:
            summary += " | (no faces selected — click the 🖼 Face Wall button below to pick)"

        image, _kept, _info = wi.load_wall_images(fl, "Face Wall")
        return (ref_list, prompt, summary, image)


NODE_CLASS_MAPPINGS = {
    "BSAI_Qwen_Face_Wall": BSAI_Qwen_Face_Wall,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Qwen_Face_Wall": "AI Face & Styling Reference Wall",
}
