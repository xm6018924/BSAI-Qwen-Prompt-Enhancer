# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 官方增强提示词模板库节点
节点: QwenImage21_Prompt_Template

从模板库（官方 PE 规则 + 全网搜集的官方文档/社区模板 + 9 类设计模板）选择一个 system prompt 输出，
可接入本插件的三个增强通道，或单独查看/复制使用。

设计模板支持用户自定义变量：在 variables 里按 "KEY: value" 填写自己的标题/品牌/主图等，
节点自动把模板里的 {{KEY}} 占位符替换为实际内容。
"""
import os

from .common import PLUGIN_ROOT, load_templates, load_text, parse_variables, apply_variables


class QwenImage21_Prompt_Template:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template_name": (cls.template_names(), {"default": "Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]"}),
            },
            "optional": {
                "custom_text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "自定义模板文本（非空时覆盖上方选择）",
                }),
                "variables": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "设计模板专用：每行一个变量，格式 KEY: value\n例:\nTITLE: 夏日新品发布会\nSUBTITLE: 2026 秋季系列\nBRAND: BSAI\nMAIN_SUBJECT: 一个穿红裙的女孩\nCOLOR: 深蓝+橙金\nSTYLE: 商业摄影",
                }),
            },
        }

    @staticmethod
    def template_names():
        return [f"{t.get('name', '?')} [{t.get('id', '?')}]" for t in load_templates()]

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("SYSTEM_PROMPT", "TEMPLATE_ID", "DESCRIPTION", "USED_VARS")
    FUNCTION = "get_template"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Qwen Image 2.1 官方增强提示词模板库：官方 PE-T2I / PE-I2I 系统规则（逐字原文）"
        "+ 官方文档与社区搜集的增强模板 + 9 类设计模板（封面/海报/壁纸/广告看板等）。"
        "设计模板在 variables 里填 KEY: value，自动替换 {{占位符}}。"
    )

    def get_template(self, template_name, custom_text="", variables=""):
        used_vars = ""
        if custom_text.strip():
            text = custom_text.strip()
            return {"ui": {"text": [text]}, "result": (text, "custom", "自定义模板", "")}

        templates = load_templates()
        tpl = None
        for t in templates:
            if template_name.startswith(t.get("name", "$$$NOMATCH$$$")):
                tpl = t
                break
        if tpl is None:
            raise ValueError(f"[BSAI_Qwen_Prompt_Enhancer] 模板不存在: {template_name}")

        if tpl.get("file"):
            text = load_text(os.path.join(PLUGIN_ROOT, tpl["file"]), "")
        else:
            text = tpl.get("text", "")
        text = text.strip()
        desc = tpl.get("desc", "")

        # 设计模板变量替换
        vars_dict = parse_variables(variables)
        if vars_dict:
            text, used_list = apply_variables(text, vars_dict)
            # 检查未替换的占位符
            import re
            remaining = re.findall(r"\{\{(\w+)\}\}", text)
            used_vars = ", ".join(used_list)
            if remaining:
                used_vars += "  | 未替换: " + ", ".join(sorted(set(remaining)))

        return {"ui": {"text": [text]}, "result": (text, tpl.get("id", "?"), desc, used_vars)}


NODE_CLASS_MAPPINGS = {
    "QwenImage21_Prompt_Template": QwenImage21_Prompt_Template,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "QwenImage21_Prompt_Template": "Qwen Image 2.1 官方增强提示词模板",
}
