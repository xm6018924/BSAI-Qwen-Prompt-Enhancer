# -*- coding: utf-8 -*-
"""验证 VALIDATE_INPUTS 双版本语义兼容：模拟新版 kwargs 调用 + 旧版两位置参调用。"""
import ast, io

FILES = [
    r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_enhancer.py",
    r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_template.py",
]

for p in FILES:
    src = io.open(p, encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "VALIDATE_INPUTS":
            fn_src = ast.get_source_segment(src, node)
            ns = {}
            exec(compile(ast.parse(fn_src), "<t>", "exec"), ns)
            fn = ns["VALIDATE_INPUTS"]

            # 旧版两位置参调用：期望 None（旧版语义 = 通过）
            r_old = fn("hf_model_name", "Florence-2-base [Florence2ForConditionalGeneration]")
            # 新版 kwargs 调用：期望 True（新版语义 = 通过）
            r_new = fn(backend="本地LLaMA (GGUF+mmproj)", prompt_text="test", clip=None,
                       hf_model_name="<未发现 HF 模型>", llm_model_name="x.gguf",
                       system_template="tpl", preview_only=False)
            # 新版可能带部分 kwargs + 位置参
            r_mix = fn("backend", "x", other=1)

            name = p.split("\\")[-1]
            ok = (r_old is None) and (r_new is True) and (r_mix is True)
            print(f"{name}: old={r_old!r} new={r_new!r} mix={r_mix!r} -> {'OK' if ok else 'FAIL'}")
            assert ok
