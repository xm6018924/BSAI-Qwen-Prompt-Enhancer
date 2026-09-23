# -*- coding: utf-8 -*-
"""BSAI_Qwen_Prompt_Enhancer v1.01 一键兼容补丁：
1) nodes_enhancer.py  - BSAI_Qwen_Prompt_Enhancer 加 VALIDATE_INPUTS 放行 combo
2) nodes_template.py  - QwenImage21_Prompt_Template 加 VALIDATE_INPUTS 放行 combo
"""
import io

ENH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_enhancer.py"
TPL = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_template.py"

ENH_PATCH = '''class BSAI_Qwen_Prompt_Enhancer:
    # 【v1.01】一键兼容旧工作流存档：hf_model_name / llm_model_name / system_template 等 combo
    # 在「模型未下载 / 模型目录变化 / 模板库版本不同」时，存档值可能不在当前下拉列表
    # （典型报错：Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']）。
    # ComfyUI 默认会对 combo 做 value-in-list 校验并红框报错、阻塞整图（Output will be ignored）。
    # 这里放行所有 combo 校验：开图不红框、不阻塞；运行时后端逻辑会给出友好中文提示，
    # 前端 JS（prompt_enhancer.js）还会在加载工作流时自动把非法 combo 值重置为当前列表首项。
    @staticmethod
    def VALIDATE_INPUTS(input_name, input_value):
        return None

    @classmethod
    def INPUT_TYPES(cls):'''

TPL_PATCH = '''class QwenImage21_Prompt_Template:
    # 【v1.01】一键兼容旧工作流存档：模板库版本变化后，旧存档 template_name 可能不在当前下拉列表，
    # 放行 combo 校验避免 "Value not in list" 红框报错阻塞整图；运行时 get_template 对未知模板给出中文提示。
    @staticmethod
    def VALIDATE_INPUTS(input_name, input_value):
        return None

    @classmethod
    def INPUT_TYPES(cls):'''

def apply(path, old, new, label):
    with io.open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if new in s:
        print(label, "already patched, skip")
        return
    if old not in s:
        print(label, "ANCHOR NOT FOUND")
        return
    s = s.replace(old, new, 1)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(label, "patched OK")

apply(ENH, "class BSAI_Qwen_Prompt_Enhancer:\n    @classmethod\n    def INPUT_TYPES(cls):", ENH_PATCH, "nodes_enhancer")
apply(TPL, "class QwenImage21_Prompt_Template:\n    @classmethod\n    def INPUT_TYPES(cls):", TPL_PATCH, "nodes_template")
