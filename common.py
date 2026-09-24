# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 公共模块
提供: 官方 system_prompt 规则加载、模板库加载、PE 输出解析、消息构造。
所有模型/内置文件均使用相对路径读取（相对 ComfyUI 目录 / 插件目录），禁止硬编码盘符。
"""
import json
import os
import re

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPTS_DIR = os.path.join(PLUGIN_ROOT, "system_prompts")
TEMPLATES_JSON = os.path.join(PLUGIN_ROOT, "templates", "templates.json")

# 官方 system_prompt 规则文件（已按官方仓库原样下载）
OFFICIAL_T2I_FILE = os.path.join(SYSTEM_PROMPTS_DIR, "qwen_image_2.1_pe_t2i_system_prompt.txt")
OFFICIAL_I2I_FILE = os.path.join(SYSTEM_PROMPTS_DIR, "qwen_image_2.1_pe_i2i_system_prompt.txt")

# PE 输出 JSON 字段
JSON_KEYS = ("rewritten_prompt", "wh_ratio", "ratio_follow")


def load_text(path, default=""):
    """读取文本文件（相对路径），失败返回默认值"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 读取失败: {path} -> {e}")
        return default


def load_official_system_prompt(pe_mode):
    """加载官方 PE 系统规则（pe_mode: 'T2I' / 'I2I'）"""
    path = OFFICIAL_T2I_FILE if pe_mode == "T2I" else OFFICIAL_I2I_FILE
    text = load_text(path, "")
    if not text:
        raise RuntimeError(
            f"[BSAI_Qwen_Prompt_Enhancer] 官方 system_prompt 规则缺失: {path}\n"
            "请确认插件目录完整（system_prompts/ 下两个 txt 文件存在）。"
        )
    return text


def load_templates():
    """加载模板库 -> 模板 dict 列表（内置 templates.json + 用户模板区 user_templates/ 合并）。
    用户模板区的文件会被自动汇聚，作为「共享用户模板」供所有工作流与海报墙使用。
    """
    try:
        with open(TEMPLATES_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        templates = data.get("templates", [])
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 模板库加载失败: {e}")
        templates = []
    templates += load_user_templates()
    return templates


# 用户模板区：插件根目录下的 user_templates/ 目录
# 用户把自己的自定义模板 JSON 放进去（可建子目录），会被自动合并进模板库（type=user）。
# 支持的 JSON 结构（三选一）：
#   1) 单个模板对象  {"id","name","desc","text":"模板全文"}
#   2) 模板对象 + 文件引用 {"id","name","desc","file":"相对插件根的 txt/md 路径"}
#   3) 模板列表       {"templates":[{...},{...}]}
USER_TEMPLATES_DIR = os.path.join(PLUGIN_ROOT, "user_templates")

# 用户模板扫描提示只打印一次，避免每次 load_templates 刷屏
_USER_TEMPLATES_LOGGED = {"done": False}


def load_user_templates():
    """扫描 user_templates/ 下所有 *.json（含子目录），汇聚为模板 dict 列表。
    - 自动补全 type="user"（若未显式指定）。
    - id 与内置模板冲突时自动加 "user_" 前缀，避免解析歧义。
    - 解析失败的文件会打印提示并跳过，不影响其它模板。
    """
    out = []
    if not os.path.isdir(USER_TEMPLATES_DIR):
        return out
    builtin_ids = set()
    try:
        with open(TEMPLATES_JSON, "r", encoding="utf-8") as f:
            builtin_ids = {t.get("id") for t in json.load(f).get("templates", [])}
    except Exception:
        pass
    used_ids = set(builtin_ids)
    for root, _dirs, files in os.walk(USER_TEMPLATES_DIR):
        for fn in sorted(files):
            if not fn.lower().endswith(".json"):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as e:
                print(f"[BSAI_Qwen_Prompt_Enhancer] 用户模板解析失败(跳过): {path} -> {e}")
                continue
            items = raw if isinstance(raw, list) else raw.get("templates", [raw] if isinstance(raw, dict) else [])
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict) or not it.get("name"):
                    continue
                t = dict(it)
                t.setdefault("type", "user")
                t.setdefault("desc", "用户自定义共享模板")
                tid = str(t.get("id") or t["name"])
                if tid in used_ids:
                    tid = "user_" + tid
                    t["id"] = tid
                used_ids.add(tid)
                out.append(t)
    if out and not _USER_TEMPLATES_LOGGED["done"]:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 用户模板区已汇聚 {len(out)} 个自定义模板 (user_templates/)")
        _USER_TEMPLATES_LOGGED["done"] = True
    return out


# 历史重命名别名表：旧显示名 -> 模板 id
# 当 templates.json 里某模板的 name 被修改后，旧工作流 / 旧存档里仍存着旧显示名，
# 这里维护别名映射，保证旧值既能通过 ComfyUI enum 校验、又能在运行时解析到正确模板。
_LEGACY_ALIAS_MAP = {
    "中文高质量描述技巧 [lightning_zh]": "lightning_zh",
}

# 无模板选项：显示名以 [none] 结尾时 resolve_template 返回空 system prompt（清空输出）
NONE_TEMPLATE_DISPLAY = "无模板（清空输出，不使用系统规则）[none]"


def template_display_list():
    """模板库下拉列表: ['模板名 [id]', ...] + 历史别名（向后兼容旧工作流）
    首项为「无模板（清空输出）」：选中后 resolve_template 返回空 system prompt。
    """
    items = [NONE_TEMPLATE_DISPLAY]
    items += [f"{t.get('name', '?')} [{t.get('id', '?')}]" for t in load_templates()]
    # 追加历史别名（若不在标准列表中），保证旧工作流里存的旧显示名能通过 enum 校验
    for alias in _LEGACY_ALIAS_MAP:
        if alias not in items:
            items.append(alias)
    return items


def _render_template(t):
    """从模板 dict 取 system prompt 文本：有 file 读文件，否则用内联 text"""
    if t.get("file"):
        return load_text(os.path.join(PLUGIN_ROOT, t["file"])), t.get("id", "?")
    return t.get("text", "").strip(), t.get("id", "?")


def resolve_template(template_display, custom_system_prompt=""):
    """根据下拉值 + 自定义文本 解析出最终的 system prompt 文本。
    返回 (system_prompt, template_id)
    匹配优先级: 自定义 > 无模板[none] > 标准 name 前缀 > 历史别名 > [id] 后缀 > 兜底官方 T2I
    """
    if custom_system_prompt and custom_system_prompt.strip():
        return custom_system_prompt.strip(), "custom"
    # 无模板（清空输出）：选中「无模板…[none]」时返回空 system prompt，不再兜底官方规则
    if template_display and template_display.strip().endswith("[none]"):
        return "", "none"
    templates = load_templates()
    # 1) 标准 name 前缀匹配
    for t in templates:
        if template_display.startswith(t.get("name", "$$$NOMATCH$$$")):
            return _render_template(t)
    # 2) 历史别名映射到 id（name 重命名后旧值走这里）
    legacy_id = _LEGACY_ALIAS_MAP.get(template_display)
    if legacy_id:
        for t in templates:
            if t.get("id") == legacy_id:
                return _render_template(t)
    # 3) 按尾部 [id] 后缀匹配（name 改过后仍能通过 id 定位到模板）
    m = re.search(r"\[([^\[\]]+)\]\s*$", template_display.strip())
    if m:
        tail_id = m.group(1).strip()
        for t in templates:
            if t.get("id") == tail_id:
                return _render_template(t)
    # 兜底：官方 T2I 规则
    return load_official_system_prompt("T2I"), "official_t2i"


def build_official_chat(system_prompt, user_prompt, image_count=0, thinking=True):
    """按官方 chat_template.jinja 构造 Qwen3.5 消息文本。
    图片 token 置于 user 内容最前（官方 I2I 惯例 <imageN> 之前的视觉占位）。
    """
    if image_count > 0:
        vision = "<|vision_start|><|image_pad|><|vision_end|>" * image_count
        user_block = vision + user_prompt
    else:
        user_block = user_prompt
    full = (
        "<|im_start|>system\n" + system_prompt + "<|im_end|>\n"
        "<|im_start|>user\n" + user_block + "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    if thinking:
        full += "<think>\n"
    else:
        full += "<think>\n\n</think>\n\n"
    return full


def parse_pe_output(raw_text):
    """解析 PE 生成输出 -> (thinking, answer, json_dict)
    兼容: <think>…</think> 思考块、直接 JSON、带 <|im_end|> 尾部、代码围栏。
    """
    if not raw_text:
        return "", "", {}
    text = raw_text.strip()
    # 去掉尾部未闭合标记
    text = re.sub(r"<\|im_end\|>\s*$", "", text).strip()
    text = re.sub(r"<\|im_end\|>\s*$", "", text).strip()
    text = re.sub(r"<\|endoftext\|>\s*$", "", text).strip()

    thinking = ""
    answer = text
    if "<think>" in text and "</think>" in text:
        parts = text.split("</think>", 1)
        thinking = parts[0].split("<think>", 1)[-1].strip()
        answer = parts[1].strip()
    elif "<think>" in text and "</think>" not in text:
        # 思考块未闭合（被 max_length 截断）: 丢弃思考部分
        thinking = text.split("<think>", 1)[-1].strip()
        answer = ""

    # 去代码围栏
    answer = re.sub(r"^```(?:json)?\s*", "", answer.strip()).strip()
    answer = re.sub(r"\s*```$", "", answer).strip()

    data = {}
    try:
        data = json.loads(answer)
    except Exception:
        # 宽松提取首个 {...} 块
        m = re.search(r"\{.*\}", answer, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = {}
        # 极宽松: 键值对
        if not data:
            for key in JSON_KEYS:
                m = re.search(r'"' + key + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', answer)
                if m:
                    data[key] = m.group(1)
    return thinking, answer, data


def get_enhanced_result(raw_text):
    """从原始输出提取最终交付字段 (enhanced_prompt, wh_ratio, ratio_follow, raw, thinking)"""
    thinking, answer, data = parse_pe_output(raw_text)
    enhanced = data.get("rewritten_prompt", answer if answer else raw_text)
    wh_ratio = data.get("wh_ratio", "")
    ratio_follow = data.get("ratio_follow", "")
    if isinstance(ratio_follow, bool):
        ratio_follow = "true" if ratio_follow else "false"
    else:
        ratio_follow = str(ratio_follow)
    return enhanced, wh_ratio, ratio_follow, raw_text, thinking


def image_tensor_to_data_urls(images):
    """IMAGE tensor (B,H,W,C float32 [0,1]) -> data URL 列表 (JPEG base64)"""
    try:
        import torch
        from PIL import Image
        import io
        import base64
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 图片处理依赖缺失: {e}")
        return []
    urls = []
    imgs = images.cpu().numpy()
    if imgs.ndim == 3:
        imgs = imgs[None, ...]
    for arr in imgs:
        import numpy as np
        arr = np.clip(255.0 * arr, 0, 255).astype("uint8")
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        urls.append("data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii"))
    return urls


def parse_variables(text):
    """解析 variables 输入文本 -> {KEY: value}
    格式: 每行 "KEY: value"（支持中文冒号），KEY 不区分大小写。
    空行/无冒号行忽略。
    """
    vars_dict = {}
    if not text:
        return vars_dict
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # 统一中文冒号
        line = line.replace("：", ":")
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().upper()
        v = v.strip()
        if k:
            vars_dict[k] = v
    return vars_dict


def apply_variables(template_text, vars_dict):
    """把模板里的 {{KEY}} 占位符替换为用户变量。
    返回 (替换后文本, 实际替换的 key 列表)。未提供的占位符保留原样。
    """
    used = []

    def repl(m):
        key = m.group(1).upper()
        if key in vars_dict and vars_dict[key]:
            used.append(key)
            return vars_dict[key]
        return m.group(0)

    out = re.sub(r"\{\{(\w+)\}\}", repl, template_text)
    return out, used


def collect_images(*imgs):
    """把多个 IMAGE 输入（image_1..image_16，每个 B,H,W,C）按顺序拼成一个 batch tensor。
    全部为 None 返回 None；单个返回该 tensor；多个按 dim=0 拼接。
    """
    valid = [im for im in imgs if im is not None]
    if not valid:
        return None
    tensors = []
    for im in valid:
        if im.ndim == 3:
            im = im[None, ...]
        tensors.append(im)
    if len(tensors) == 1:
        return tensors[0]
    try:
        import torch
        return torch.cat(tensors, dim=0)
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 多图 batch 拼接失败({e})，使用第一张")
        return tensors[0]
