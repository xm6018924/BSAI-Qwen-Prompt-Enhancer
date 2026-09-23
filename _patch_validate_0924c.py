# -*- coding: utf-8 -*-
"""v1.01.2 修复：VALIDATE_INPUTS 返回值按 ComfyUI 版本语义兼容。
- 旧版 ComfyUI：位置参两参调用 VALIDATE_INPUTS(input_name, input_value)，返回 None 表示通过；
  新版 ComfyUI：以 **kwargs 传入全部输入调用，要求返回 True（None/False 判为失败，
  报 "Custom validation failed for node: X - None"），且 kwargs 形态会自动跳过 combo 校验。
- 判别：kwargs 非空 => 新版 => 返回 True；仅两个位置参 => 旧版 => 返回 None。
"""
import io

ENH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_enhancer.py"
TPL = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_template.py"

OLD = """    @staticmethod
    def VALIDATE_INPUTS(*args, **kwargs):
        # v1.01.1: 兼容所有 ComfyUI 版本的调用方式（部分版本无参调用 VALIDATE_INPUTS()）。
        # 固定签名 (input_name, input_value) 会抛 "missing 2 required positional arguments"，
        # 可变参数对任何调用方式都放行 combo 校验，实现跨版本一键自愈。
        return None"""

NEW = """    @staticmethod
    def VALIDATE_INPUTS(*args, **kwargs):
        # v1.01.2: 返回值兼容新旧两代 ComfyUI 校验语义：
        # - 旧版以位置参调用 VALIDATE_INPUTS(input_name, input_value)，返回 None 表示通过；
        # - 新版以 **kwargs 传入全部输入调用，要求返回 True（返回 None 会报
        #   "Custom validation failed for node: X - None"），且 kwargs 形态自动跳过 combo 校验。
        # 判别：收到 kwargs（新版形态）=> True；仅两个位置参（旧版形态）=> None。
        if not kwargs and len(args) == 2:
            return None
        return True"""

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
