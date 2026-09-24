# -*- coding: utf-8 -*-
"""
BSAI MarkdownNote 兼容节点

背景：示例工作流（BSAI-Qwen-Image-2.1+提示词增强器...）与潜空间放大示例中使用了
rgthree 的 MarkdownNote（纯注释节点）。新版 rgthree-comfy 已移除该节点，
导致干净环境打开工作流时报 "MarkdownNote 未找到"。
本插件内置同名兼容节点，保证 BSAI 示例工作流开箱即用（不依赖 rgthree 旧版）。
注意：若环境中同时安装了含 MarkdownNote 的旧版 rgthree，类名会重复注册；
ComfyUI 以最后加载者为准，功能一致（纯文本注释），无副作用。
"""
import io


class MarkdownNote:
    """Markdown 文本注释节点（与 rgthree 旧版 MarkdownNote 兼容）。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "markdown_text": (
                    "STRING",
                    {"multiline": True, "default": "", "placeholder": "在此输入 Markdown 说明文字…"},
                )
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "utils"
    OUTPUT_NODE = False

    def noop(self, **kwargs):
        """纯注释节点，不产出任何数据。"""
        return ()


NODE_CLASS_MAPPINGS = {
    "MarkdownNote": MarkdownNote,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MarkdownNote": "Markdown Note (BSAI Compat)",
}
