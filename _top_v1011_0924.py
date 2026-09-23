# -*- coding: utf-8 -*-
"""README 顶部插入 v1.01.1 修复说明（中英双语）"""
import io

ZH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.md"
EN = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"

zh = """### v1.01.1 (2026-09-24) — 修复跨 ComfyUI 版本的校验签名兼容 / Fix VALIDATE_INPUTS signature across ComfyUI versions

> **v1.01 在部分 ComfyUI 版本上会报新错：`Exception when validating inner node: BSAI_Qwen_Prompt_Enhancer.VALIDATE_INPUTS() missing 2 required positional arguments: 'input_name' and 'input_value'`。**
> 原因：这些版本以**无参方式**调用 `VALIDATE_INPUTS()`，v1.01 固定签名 `(input_name, input_value)` 因而抛错。
> **v1.01.1 已改为可变参数签名 `VALIDATE_INPUTS(*args, **kwargs)`，兼容无参 / 两参 / 带 kwargs 的所有调用方式，任何 ComfyUI 版本都开图即用、不再红框。** 请把插件更新到 v1.01.1（`git pull` 或重新下载）。
>
> **v1.01 could fail on some ComfyUI builds with: `Exception when validating inner node: ...VALIDATE_INPUTS() missing 2 required positional arguments: 'input_name' and 'input_value'`** — those builds call `VALIDATE_INPUTS()` with **no arguments**. **v1.01.1 switches to a variadic signature `VALIDATE_INPUTS(*args, **kwargs)` that accepts any calling convention (no args / two args / kwargs), so every ComfyUI version loads cleanly with no red frame.** Update the plugin to v1.01.1 (`git pull` or re-download).

---

"""

en = """### v1.01.1 (2026-09-24) — Fix VALIDATE_INPUTS signature across ComfyUI versions

> **v1.01 could fail on some ComfyUI builds with: `Exception when validating inner node: BSAI_Qwen_Prompt_Enhancer.VALIDATE_INPUTS() missing 2 required positional arguments: 'input_name' and 'input_value'`** — those builds call `VALIDATE_INPUTS()` with **no arguments**, while v1.01's fixed signature `(input_name, input_value)` then throws.
> **v1.01.1 switches to a variadic signature `VALIDATE_INPUTS(*args, **kwargs)` that accepts any calling convention (no args / two args / kwargs), so every ComfyUI version loads cleanly with no red frame and no blocked graph.** Update the plugin to v1.01.1 (`git pull` or re-download).

---

"""


def insert(path, text, anchor, label):
    with io.open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if "### v1.01.1 (2026-09-24)" in s:
        print(label, "already has v1.01.1, skip")
        return
    if anchor not in s:
        print(label, "ANCHOR NOT FOUND")
        return
    s = s.replace(anchor, anchor + text, 1)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(label, "top insert OK")


insert(ZH, zh, "## 🚀 最新更新 / Latest Updates\n\n", "README.md")
insert(EN, en, "## 🚀 Latest Updates\n\n", "README.en.md")
