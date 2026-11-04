# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — AI clothing reference node
Node: BSAI_Qwen_Clothing_Wall
"""
import os

from . import clothing_library as cl


class BSAI_Qwen_Clothing_Wall:
    """AI clothing reference library (wall selection -> numbered reference list)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "library_root": ("STRING", {
                    "default": cl.get_library_root(),
                    "multiline": False,
                    "tooltip": "Root directory of the clothing reference library. Check apply_root below and run once to rebuild.",
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
    FUNCTION = "get_clothing_references"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True

    DESCRIPTION = (
        "AI clothing reference library: reads outfits selected in the Clothing Wall (🖼 button below the node), "
        "and outputs a numbered reference list (REFERENCE_LIST), an English prompt snippet (PROMPT_SNIPPET), "
        "and a stats summary (SUMMARY).\n"
        "Order = input order: item 1 maps to the enhancer node's image_1, item 2 to image_2..."
    )

    def get_clothing_references(self, library_root="", apply_root=False):
        root = cl.get_library_root()
        if apply_root:
            wanted = str(library_root or "").strip()
            if wanted and os.path.normpath(wanted) != os.path.normpath(root):
                try:
                    root = cl.set_library_root(wanted)
                    cl.build_manifest(root, force=True)
                    print("[BSAI_Qwen_Prompt_Enhancer] clothing library root switched: %s" % root)
                except Exception as e:
                    print("[BSAI_Qwen_Prompt_Enhancer] clothing library root switch failed: %s" % e)

        manifest = cl.load_manifest()
        if manifest.get("root") != root:
            manifest = cl.build_manifest(root, force=True)

        items = cl.load_selection()
        ref_list = cl.selection_text(items)
        prompt = cl.selection_prompt_snippet(items)

        cats = len(manifest.get("categories", []))
        total = manifest.get("count", 0)
        summary = "Clothing library: %d images · %d categories · %d selected | %s" % (
            total, cats, len(items), manifest.get("root", root))
        if not items:
            summary += " | (no outfits selected — click the 🖼 Clothing Wall button below to pick)"

        return (ref_list, prompt, summary)


NODE_CLASS_MAPPINGS = {
    "BSAI_Qwen_Clothing_Wall": BSAI_Qwen_Clothing_Wall,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Qwen_Clothing_Wall": "AI Clothing Reference Wall",
}
