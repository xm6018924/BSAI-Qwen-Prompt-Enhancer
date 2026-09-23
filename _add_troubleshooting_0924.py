# -*- coding: utf-8 -*-
import io

ZH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.md"
EN = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"

zh = """

---

## ❓ 常见问题 / Troubleshooting

### Q：打开工作流报错 `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`，节点弹红框「无效输入」，控制台刷 `Output will be ignored`？

**原因**：工作流是在**另一台电脑**保存的，`hf_model_name`（本地 HF 后端）选了 `Florence-2-base [Florence2ForConditionalGeneration]`；当前电脑的 `ComfyUI/models/LLM` 下**没有该模型**（未下载 / 目录不同），下拉列表只剩 `<未发现 HF 模型>`，ComfyUI 校验失败 → 红框 + 整图被忽略。

**✅ 一键解决（v1.01+，无需任何手动操作）**：升级到 **v1.01**，插件内置两层自愈：

1. **后端放行**：`VALIDATE_INPUTS` 跳过 combo 的 value-in-list 校验 → 开图不再红框、不再阻塞整图；
2. **前端自动重置**：加载工作流时把非法下拉值自动重置为当前列表首项，并在节点 tooltip 提示「下拉选项已自动重置」。

升级后打开工作流即恢复正常，在 `hf_model_name` 下拉里重新选择本机实际存在的模型即可。

**手动解决（根治）**：把 Florence-2 模型放入 `ComfyUI/models/LLM/`（目录结构：`models/LLM/<模型目录>/model.safetensors` + `config.json` 等 Transformers 目录格式）。下载参考：

```
pip install -U huggingface_hub
hf download microsoft/Florence-2-base --local-dir ComfyUI/models/LLM/Florence-2-base
```

### Q：其他下拉也报 `Value not in list`？

同一原因（旧存档值不在当前选项列表，如模板库版本变化后的 `system_template`、模型目录变化后的 `llm_model_name`）。v1.01 对**全部下拉**统一做了自愈，重启 ComfyUI 后打开工作流即自动重置，无需手动改节点。

---

## v1.01 (2026-09-24) — 一键兼容旧工作流 / One-click compatibility for saved workflows

- **修复跨电脑打开工作流红框报错**：combo 存档值不在当前选项列表（典型：另一台电脑选了 Florence-2，本机未下载该模型）时，不再弹「无效输入」/ 刷 `Value not in list` / `Output will be ignored`。后端 `VALIDATE_INPUTS` 放行 + 前端加载时自动重置非法下拉值，开图即用 / Fixes red-frame validation errors when opening workflows saved on another PC (stored combo values missing on this machine, e.g. Florence-2 not downloaded): backend VALIDATE_INPUTS pass-through + frontend auto-reset of invalid combo values on load.
- **README 双语新增疑难解答** / Bilingual troubleshooting added.
"""

en = """

---

## ❓ Troubleshooting

### Q: Opening a workflow shows `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`, the node turns red with "Invalid input", and the console logs `Output will be ignored`?

**Cause**: The workflow was saved on **another PC**. Its `hf_model_name` (Local HF backend) was set to `Florence-2-base [Florence2ForConditionalGeneration]`, but **that model is not present** under this machine's `ComfyUI/models/LLM` (not downloaded / different layout). The dropdown only contains `<未发现 HF 模型>`, so ComfyUI's combo validation fails → red frame + the whole graph gets ignored.

**✅ One-click fix (v1.01+, zero manual steps)**: Upgrade to **v1.01** — the plugin ships two layers of self-healing:

1. **Backend pass-through**: `VALIDATE_INPUTS` skips the combo value-in-list check → no red frame on load, graph is no longer blocked;
2. **Frontend auto-reset**: on workflow load, invalid combo values are automatically reset to the first item of the current list, and the node tooltip says "dropdown options were auto-reset".

After upgrading, open the workflow as usual and simply re-pick the model that actually exists on this machine from the `hf_model_name` dropdown.

**Manual fix (root cause)**: put the Florence-2 model into `ComfyUI/models/LLM/` (Transformers folder layout: `models/LLM/<model-dir>/model.safetensors` + `config.json` etc.). Download example:

```
pip install -U huggingface_hub
hf download microsoft/Florence-2-base --local-dir ComfyUI/models/LLM/Florence-2-base
```

### Q: Other dropdowns also report `Value not in list`?

Same cause (stored value not in the current option list — e.g. `system_template` after template-library updates, `llm_model_name` after model-folder changes). v1.01 applies the same self-healing to **all** dropdowns; restart ComfyUI and open the workflow — values are auto-reset, no manual node editing needed.

---

## v1.01 (2026-09-24) — One-click compatibility for saved workflows

- **Fix: red-frame errors when opening workflows saved on another PC** — combo values stored in the workflow that are missing from the current option list (e.g. Florence-2 selected on another machine but not downloaded here) no longer trigger "Invalid input" / `Value not in list` / `Output will be ignored`. Backend VALIDATE_INPUTS pass-through + frontend auto-reset of invalid combo values on load.
- **Bilingual troubleshooting added to README**.
"""

for p, t in ((ZH, zh), (EN, en)):
    with io.open(p, "r", encoding="utf-8") as f:
        s = f.read()
    if "## v1.01 (2026-09-24)" in s:
        print(p, "already has v1.01, skip")
        continue
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(t)
    print(p, "appended OK")
