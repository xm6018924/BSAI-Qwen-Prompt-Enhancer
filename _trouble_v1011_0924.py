# -*- coding: utf-8 -*-
import io

ZH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.md"
EN = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"

pairs_zh = [
    ("**✅ 一键解决（v1.01+，无需任何手动操作）**：升级到 **v1.01**，插件内置两层自愈：",
     "**✅ 一键解决（v1.01.1+，无需任何手动操作）**：升级到 **v1.01.1**，插件内置两层自愈："),
    ("v1.01 对**全部下拉**统一做了自愈", "v1.01.1 对**全部下拉**统一做了自愈"),
    ("**✅ 一键解决（v1.01+，无需任何手动操作）**：升级到 **v1.01**，插件内置两层自愈：",
     "**✅ 一键解决（v1.01.1+，无需任何手动操作）**：升级到 **v1.01.1**，插件内置两层自愈："),
]
pairs_en = [
    ("**✅ One-click fix (v1.01+, zero manual steps)**: Upgrade to **v1.01** — the plugin ships two layers of self-healing:",
     "**✅ One-click fix (v1.01.1+, zero manual steps)**: Upgrade to **v1.01.1** — the plugin ships two layers of self-healing:"),
    ("v1.01 applies the same self-healing to **all** dropdowns", "v1.01.1 applies the same self-healing to **all** dropdowns"),
]

for p, pairs in ((ZH, pairs_zh), (EN, pairs_en)):
    with io.open(p, "r", encoding="utf-8") as f:
        s = f.read()
    n = 0
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new)
            n += 1
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)
    print(p.split("\\")[-1], "replaced", n, "spots")
