# -*- coding: utf-8 -*-
"""README 双语新增「更新与自查」小节（其他电脑如何确认已更新到 v1.01.2）"""
import io

ZH = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.md"
EN = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\README.en.md"

zh = """

## 🔄 更新与自查（其他电脑务必看这里）/ Update & self-check (for other PCs)

> **症状**：其他电脑打开工作流仍报 `Custom validation failed for node: X - None` 或 `Value not in list`。
> **99% 是因为插件没更新到 v1.01.2（或更新后没重启）。** 请按下面两步确认：

**第 1 步 — 更新插件到 v1.01.2**（在插件目录 `ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer` 执行）：

```bash
git pull origin main
# 或重新下载最新仓库 zip 覆盖（ComfyUI Manager 用户：点 UPDATE ALL 后选本插件）
```

**第 2 步 — 完全重启 ComfyUI**（不是刷新浏览器页面）：关掉 ComfyUI 进程，重新启动。

**自查是否已生效**：重启后看 ComfyUI 控制台第一屏，应有横幅：

```
[BSAI_Qwen_Prompt_Enhancer] 插件已加载 | 版本 v1.01.2 (2026-09-24) | ...
```

- 看到 `v1.01.2` → 已更新，重新打开工作流即正常。
- 没有这行 / 版本号是 v1.01.1 或更早 → 插件没更新成功：检查插件目录里 `git pull` 是否成功、ComfyUI 是否完全重启、或从 G 盘/旧 zip 拷的是不是旧文件。

**命令行确认版本**：

```bash
git -C ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer log --oneline -1
# 应显示 5ea6300 或更新的提交
```
"""

en = """

## 🔄 Update & self-check (for other PCs)

> **Symptom**: another PC still shows `Custom validation failed for node: X - None` or `Value not in list` when opening the workflow.
> **99% of the time the plugin is not updated to v1.01.2 (or ComfyUI wasn't fully restarted after updating).** Confirm with these two steps:

**Step 1 — Update to v1.01.2** (inside the plugin folder `ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer`):

```bash
git pull origin main
# or re-download the latest repo zip and overwrite (ComfyUI Manager users: click UPDATE ALL and select this plugin)
```

**Step 2 — Fully restart ComfyUI** (not just refresh the browser page): close the ComfyUI process and start it again.

**Verify it took effect**: after restart, the first screen of the ComfyUI console should show the banner:

```
[BSAI_Qwen_Prompt_Enhancer] 插件已加载 | 版本 v1.01.2 (2026-09-24) | ...
```

- You see `v1.01.2` → updated; reopen the workflow and it works.
- No such line / version is v1.01.1 or older → the update didn't land: check whether `git pull` succeeded, whether ComfyUI was fully restarted, or whether files were copied from an old G-drive/zip.

**Check version from the command line**:

```bash
git -C ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer log --oneline -1
# should show 5ea6300 or a newer commit
```
"""


def append(path, text, label):
    with io.open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if "## 🔄 更新与自查" in s or "## 🔄 Update & self-check" in s:
        print(label, "already exists, skip")
        return
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(text)
    print(label, "appended OK")


append(ZH, zh, "README.md")
append(EN, en, "README.en.md")
