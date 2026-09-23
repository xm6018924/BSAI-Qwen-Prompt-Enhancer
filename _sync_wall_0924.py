# -*- coding: utf-8 -*-
"""修复海报墙数据源：web/templates.json 落后（55）-> 同步 templates/templates.json（102）。
海报墙 templates_wall.html fetch 同目录 web/templates.json；后端 common.py 加载 templates/templates.json。
"""
import io, json

ROOT = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer"
SRC = ROOT + r"\templates\templates.json"
DST = ROOT + r"\web\templates.json"

with io.open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

data.setdefault("meta", {})
data["meta"]["updated"] = "2026-09-24"
data["meta"]["note"] = (
    "official 模板为 Qwen 官方 PE 模型 system_prompt 原文（逐字保留）；其余为官方文档/社区最佳实践整理。"
    "file 字段指向插件内置文件（相对路径），text 字段为内联模板文本。"
    "本文件与 templates/templates.json 同步维护（海报墙数据源）。"
)

with io.open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("web/templates.json count:", len(data["templates"]))
import collections
c = collections.Counter(x.get("type") for x in data["templates"])
print("by type:", dict(c))
