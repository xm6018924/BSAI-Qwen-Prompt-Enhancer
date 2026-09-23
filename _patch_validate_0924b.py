# -*- coding: utf-8 -*-
"""v1.01.1 修复：VALIDATE_INPUTS 签名兼容所有 ComfyUI 版本。
部分 ComfyUI 版本以「无参」方式调用 VALIDATE_INPUTS()，
固定签名 (input_name, input_value) 会抛 missing 2 required positional arguments。
改为 *args/**kwargs 万能签名：无论无参/两参/带 kwargs 调用都放行。
"""
import io

ENH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_enhancer.py"
TPL = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_template.py"

OLD = """    @staticmethod
    def VALIDATE_INPUTS(input_name, input_value):
        return None"""

NEW = """    @staticmethod
    def VALIDATE_INPUTS(*args, **kwargs):
        # v1.01.1: 兼容所有 ComfyUI 版本的调用方式（部分版本无参调用 VALIDATE_INPUTS()）。
        # 固定签名 (input_name, input_value) 会抛 "missing 2 required positional arguments"，
        # 可变参数对任何调用方式都放行 combo 校验，实现跨版本一键自愈。
        return None"""

for p in (ENH, TPL):
    with io.open(p, "r", encoding="utf-8") as f:
        s = f.read()
    if NEW in s:
        print(p, "already patched, skip")
        continue
    if OLD not in s:
        print(p, "ANCHOR NOT FOUND")
        continue
    s = s.replace(OLD, NEW, 1)
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)
    print(p, "patched OK")
