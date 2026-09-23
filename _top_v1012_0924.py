# -*- coding: utf-8 -*-
"""README 顶部插入 v1.01.2 修复说明（中英双语）+ Troubleshooting 补充"""
import io

ZH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.md"
EN = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"

zh = """### v1.01.2 (2026-09-24) — 兼容新旧两代 ComfyUI 的校验语义 / Compatible with old & new ComfyUI validation semantics

> **新版 ComfyUI 上报 `Custom validation failed for node: backend - None`（每个输入都报）？**
> 新版以 `VALIDATE_INPUTS(**全部输入)` 方式调用并**要求返回 `True`**（返回 None/False 都判失败）；旧版则以 `VALIDATE_INPUTS(input_name, input_value)` 两位置参调用、返回 None 表示通过。
> **v1.01.2 已按调用形态自动判别返回值**（kwargs 形态返回 True、两位置参返回 None），新旧版 ComfyUI 全部通过校验，开图即用。请更新到 v1.01.2。
>
> **Newer ComfyUI shows `Custom validation failed for node: backend - None` (for every input)?** New builds call `VALIDATE_INPUTS(**all_inputs)` and **require `True`** (None/False both count as failure); legacy builds call `VALIDATE_INPUTS(input_name, input_value)` and treat None as pass.
> **v1.01.2 detects the calling convention and returns the right value** (True for kwargs form, None for two-positional form), so both old and new ComfyUI pass validation cleanly on load. Update to v1.01.2.

---

"""

en = """### v1.01.2 (2026-09-24) — Compatible with old & new ComfyUI validation semantics

> **Newer ComfyUI shows `Custom validation failed for node: backend - None` (for every input)?** New builds call `VALIDATE_INPUTS(**all_inputs)` and **require `True`** (None/False both count as failure); legacy builds call `VALIDATE_INPUTS(input_name, input_value)` and treat None as pass.
> **v1.01.2 detects the calling convention and returns the right value** (True for kwargs form, None for two-positional form), so both old and new ComfyUI pass validation cleanly on load. Update to v1.01.2.

---

"""

zh_ts = """

### Q：新版 ComfyUI 报 `Custom validation failed for node: backend - None`（每个输入都刷）？

v1.01.1 的放行逻辑被新版 ComfyUI 判为失败：新版以 `**kwargs` 传入全部输入调用 `VALIDATE_INPUTS`，**要求返回 `True`** 才通过。**升级 v1.01.2** 即自动兼容（kwargs 形态返回 True、旧版两位置参形态返回 None），无需手动改节点。
"""

en_ts = """

### Q: Newer ComfyUI reports `Custom validation failed for node: backend - None` (spammed for every input)?

v1.01.1's pass-through logic is treated as failure by new ComfyUI builds: they call `VALIDATE_INPUTS(**all_inputs)` and **require `True`** to pass. **Upgrade to v1.01.2** — it auto-adapts (returns True for the kwargs form, None for the legacy two-positional form); no manual node editing needed.
"""


def insert(path, text, anchor, label):
    with io.open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if "### v1.01.2 (2026-09-24)" in s:
        print(label, "already has v1.01.2, skip")
        return
    if anchor not in s:
        print(label, "ANCHOR NOT FOUND")
        return
    s = s.replace(anchor, anchor + text, 1)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(label, "top insert OK")


def append(path, text, marker, label):
    with io.open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if "Custom validation failed for node: backend" in s:
        print(label, "troubleshooting already appended, skip")
        return
    if marker not in s:
        print(label, "TROUBLE ANCHOR NOT FOUND")
        return
    s = s.replace(marker, marker + text, 1)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(label, "troubleshooting appended OK")


insert(ZH, zh, "## 🚀 最新更新 / Latest Updates\n\n", "README.md")
insert(EN, en, "## 🚀 Latest Updates\n\n", "README.en.md")
append(ZH, zh_ts, "### Q：其他下拉也报 `Value not in list`？", "README.md")
append(EN, en_ts, "### Q: Other dropdowns also report `Value not in list`?", "README.en.md")
