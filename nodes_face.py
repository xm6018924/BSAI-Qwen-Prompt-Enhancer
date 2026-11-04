# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — AI face/styling reference node
Node: BSAI_Qwen_Face_Wall
"""
import os

from . import face_library as fl


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

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("REFERENCE_LIST", "PROMPT_SNIPPET", "SUMMARY")
    FUNCTION = "get_face_references"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True

    DESCRIPTION = (
        "AI face/styling reference library: reads faces selected in the Face Wall (🖼 button below the node), "
        "and outputs a numbered reference list (REFERENCE_LIST), an English prompt snippet (PROMPT_SNIPPET), "
        "and a stats summary (SUMMARY).\n"
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

        return (ref_list, prompt, summary)


NODE_CLASS_MAPPINGS = {
    "BSAI_Qwen_Face_Wall": BSAI_Qwen_Face_Wall,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Qwen_Face_Wall": "AI Face & Styling Reference Wall",
}
