# -*- coding: utf-8 -*-
import io, re

P = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"
with io.open(r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\_top_v101_0924.py", "r", encoding="utf-8") as f:
    t = f.read()
m = re.search(r'en = """(.*?)"""', t, re.S)
txt = m.group(1)
with io.open(P, "r", encoding="utf-8") as f:
    s = f.read()
anchor = "## \U0001F680 Latest Updates\n\n"
if "### v1.01 (2026-09-24)" in s:
    print("EN already has v1.01 at top, skip")
elif anchor not in s:
    print("EN ANCHOR NOT FOUND")
else:
    s = s.replace(anchor, anchor + txt, 1)
    with io.open(P, "w", encoding="utf-8") as f:
        f.write(s)
    print("EN top insert OK")
