# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 官方增强提示词模板库节点
节点: QwenImage21_Prompt_Template

从模板库（官方 PE 规则 + 全网搜集的官方文档/社区模板 + 9 类设计模板）选择一个 system prompt 输出，
可接入本插件的三个增强通道，或单独查看/复制使用。

设计模板支持用户自定义变量：在 variables 里按 "KEY: value" 填写自己的标题/品牌/主图等，
节点自动把模板里的 {{KEY}} 占位符替换为实际内容。

【v2 升级】海报墙交互 + 用户要求拼接
  · 海报墙选卡片时，把模板原文直接实时推到本节点第 1 路 SYSTEM_PROMPT（下游 Show Text 立刻可见），
    而不需要等后端 LLM 跑完。
  · 第 5 路新增 MERGED_TEXT：把「模板原文 + 用户要求」按可配置分隔符拼成一段最终提示词，
    直接接 KSampler.positive 或其它下游节点用，不必再绕 LLM。
"""
import os

from .common import PLUGIN_ROOT, load_templates, load_text, parse_variables, apply_variables


# 拼接「模板原文 + 用户要求」时的默认分隔符
DEFAULT_MERGED_SEPARATOR = "\n\n【用户要求】\n"

# 拼接「模板原文 + 用户要求」时，给用户要求再加一层包装前缀（避免直接拼接到 system prompt 末尾被误读）
DEFAULT_MERGED_HEADER = "用户对当前任务的额外要求：\n"
DEFAULT_MERGED_FOOTER = "\n（请务必在生成时满足以上用户要求。）"


class QwenImage21_Prompt_Template:
    # 【v1.01】一键兼容旧工作流存档：模板库版本变化后，旧存档 template_name 可能不在当前下拉列表，
    # 放行 combo 校验避免 "Value not in list" 红框报错阻塞整图；运行时 get_template 对未知模板给出中文提示。
    @staticmethod
    def VALIDATE_INPUTS(input_name, input_value):
        return None

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
                # ↓↓↓ 新增：用户在两个红框位（界面上的小红框 + 大红框）输入的内容 ↓↓↓
                "user_requirement": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "用户对当前任务的具体要求（与 custom_system_prompt 同源，输出到 MERGED_TEXT）。\n例：封面含主标题+副标题；画面左侧放主视觉，右侧留白放文案；配色用深蓝+橙金。",
                }),
                # 前端 JS / 海报墙点选时会推送该信号；后端据此区分「实时预览」与「真正运行」
                "_preview_signal": ("STRING", {
                    "default": "",
                    "hidden": True,
                }),
            },
        }

    @staticmethod
    def template_names():
        return [f"{t.get('name', '?')} [{t.get('id', '?')}]" for t in load_templates()]

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("SYSTEM_PROMPT", "TEMPLATE_ID", "DESCRIPTION", "USED_VARS", "MERGED_TEXT")
    FUNCTION = "get_template"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Qwen Image 2.1 官方增强提示词模板库：官方 PE-T2I / PE-I2I 系统规则（逐字原文）"
        "+ 官方文档与社区搜集的增强模板 + 9 类设计模板（封面/海报/壁纸/广告看板等）。"
        "设计模板在 variables 里填 KEY: value，自动替换 {{占位符}}。\n"
        "海报墙选中后第 1 路 SYSTEM_PROMPT 实时输出模板原文；第 5 路 MERGED_TEXT = 模板原文 + user_requirement 拼接，可直接接 KSampler。"
    )

    @staticmethod
    def _build_merged_text(template_text, user_requirement):
        """把模板原文 + 用户要求按规则拼接。
        - 用户要求为空时：MERGED_TEXT == SYSTEM_PROMPT，保持一致。
        - 用户要求非空时：在尾部追加「【用户要求】\n<要求>\n（请务必在生成时满足以上用户要求。）」
        """
        if not user_requirement or not user_requirement.strip():
            return template_text
        body = user_requirement.strip()
        merged = (
            template_text.rstrip()
            + DEFAULT_MERGED_SEPARATOR
            + DEFAULT_MERGED_HEADER
            + body
            + DEFAULT_MERGED_FOOTER
        )
        return merged

    def get_template(self, template_name, custom_text="", variables="",
                     user_requirement="", _preview_signal=""):
        used_vars = ""
        if custom_text.strip():
            text = custom_text.strip()
            merged = self._build_merged_text(text, user_requirement)
            return {
                "ui": {
                    "text": [text, merged],
                    "merged_text": [merged],
                    "user_requirement": [user_requirement or "(空)"],
                },
                "result": (text, "custom", "自定义模板", "", merged),
            }

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

        merged = self._build_merged_text(text, user_requirement)

        return {
            "ui": {
                "text": [text, merged],
                "merged_text": [merged],
                "user_requirement": [user_requirement or "(空)"],
            },
            "result": (text, tpl.get("id", "?"), desc, used_vars, merged),
        }


NODE_CLASS_MAPPINGS = {
    "QwenImage21_Prompt_Template": QwenImage21_Prompt_Template,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "QwenImage21_Prompt_Template": "Qwen Image 2.1 官方增强提示词模板",
}
