# -*- coding: utf-8 -*-
import io

ZH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.md"
EN = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"

zh = """### v1.01 (2026-09-24) — 跨电脑打开工作流红框报错一键自愈 / One-click fix: validation errors when opening workflows saved on another PC

> **遇到 `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`、节点红框「无效输入」、控制台刷 `Output will be ignored`？** 这是**旧工作流存档的下拉值在本机不存在**（例如另一台电脑选了 Florence-2，本机 `models/LLM` 下没这个模型）。
> **升级到 v1.01 后自动解决，无需任何手动操作**：后端 `VALIDATE_INPUTS` 放行 combo 校验（不再红框/阻塞整图）+ 前端加载时自动把非法下拉值重置为列表首项。手动根治方法见文末「常见问题 / Troubleshooting」。
>
> **See `Value not in list: hf_model_name: ... not in ['<未发现 HF 模型>']`, a red "Invalid input" frame, or `Output will be ignored` spam?** The workflow saved a dropdown value that does not exist on this machine (e.g. Florence-2 was selected on another PC but is not in this PC's `models/LLM`). **v1.01 fixes this automatically — zero manual steps**: backend `VALIDATE_INPUTS` pass-through (no red frame / no blocked graph) + frontend auto-reset of invalid combo values on load. Manual root-cause fix in "Troubleshooting" at the end of this README.

---

"""

en = """### v1.01 (2026-09-24) — One-click fix: validation errors when opening workflows saved on another PC

> **Hit `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`, a red "Invalid input" frame, or `Output will be ignored` spam?** This means a dropdown value stored in the saved workflow does not exist on this machine (e.g. Florence-2 was selected on another PC, but this PC's `models/LLM` has no such model).
> **Upgrading to v1.01 resolves it automatically — no manual steps needed**: backend `VALIDATE_INPUTS` pass-through (no red frame / no blocked graph) + frontend auto-reset of invalid combo values on load. Manual root-cause fix in "Troubleshooting" at the end of this README.

---

"""


def insert(path, text, anchor, label):
    with io.open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if "### v1.01 (2026-09-24)" in s:
        print(label, "already has v1.01 at top, skip")
        return
    if anchor not in s:
        print(label, "ANCHOR NOT FOUND")
        return
    s = s.replace(anchor, anchor + text, 1)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print(label, "top insert OK")


insert(ZH, zh, "## 🚀 最新更新 / Latest Updates\n\n", "README.md")
insert(EN, en, "## 🚀 Latest Updates / 最新更新\n\n", "README.en.md")
