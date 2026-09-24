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

# 【v1.02.0】启动横幅：ComfyUI 日志第一屏即可确认加载的插件版本。
# 排查"其他电脑仍报 Custom validation failed / Value not in list / 节点 undefined"时，先看这行：
# 如果版本号不是 v1.02.0，说明插件未更新到最新（git pull 后需完全重启 ComfyUI）。
_PLUGIN_VERSION = "v1.02.0 (2026-09-24)"
print(f"[BSAI_Qwen_Prompt_Enhancer] 插件已加载 | 版本 {_PLUGIN_VERSION} | "
      f"已含: 新旧版ComfyUI校验兼容 / 前端combo自愈 / Jev并行决策 / 海报墙102模板10分类 / MarkdownNote兼容 / 潜空间放大示例")

