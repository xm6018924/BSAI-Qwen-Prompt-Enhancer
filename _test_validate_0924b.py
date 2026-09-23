# -*- coding: utf-8 -*-
"""模拟 ComfyUI 两种已知调用方式，验证 VALIDATE_INPUTS 兼容。"""
import ast, io

ENH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_enhancer.py"
TPL = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\nodes_template.py"

for p in (ENH, TPL):
    src = io.open(p, encoding="utf-8").read()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "VALIDATE_INPUTS":
            args = [a.arg for a in node.args.args]
            has_vararg = node.args.vararg is not None
            found = True
            print(p.split("\\")[-1], "-> VALIDATE_INPUTS args:", args, "vararg:", has_vararg)
            # 直接编译执行函数体（无外部依赖），模拟两种调用
            fn_src = ast.get_source_segment(src, node)
            ns = {}
            exec(compile(ast.parse("import sys\n" + fn_src), "<t>", "exec"), ns)
            fn = ns["VALIDATE_INPUTS"]
            # 调用方式1：ComfyUI 传统两参
            r1 = fn("hf_model_name", "Florence-2-base [Florence2ForConditionalGeneration]")
            # 调用方式2：新版无参
            r2 = fn()
            # 调用方式3：带 kwargs
            r3 = fn(input_name="x", input_value="y", input_info=[])
            assert r1 is None and r2 is None and r3 is None, (p, r1, r2, r3)
            print(p.split("\\")[-1], "-> 三种调用方式全部返回 None ✅")
    if not found:
        print(p, "-> VALIDATE_INPUTS NOT FOUND ❌")
