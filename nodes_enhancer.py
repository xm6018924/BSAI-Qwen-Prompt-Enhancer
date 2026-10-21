# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 四合一增强通道节点
节点: BSAI_Qwen_Prompt_Enhancer

一个节点、四种增强后端，用 backend 下拉一键切换：
  1. 官方PE (本地 Qwen3.5-9B)  — CLIPLoader 加载官方 PE 模型，clip.tokenize/generate/decode
     （与 ComfyUI 0.37 官方 TextGenerate 同一体系，官方 chat_template.jinja 构造消息）
  2. 本地LLaMA (GGUF+mmproj)   — llama.cpp 加载本地视觉大模型，create_chat_completion
     （自动扫描 models/LLM 与 models/text_encoders 下的 *.gguf，自动配对 mmproj，自动识别 chat_handler）
     [移植自 G 盘 BSAI_QwenNodes] MTP 层自动检测与剥离 / LLM 状态重置 / 签名兼容调用
  3. 本地HF (Transformers)      — 加载 models/LLM 下 HuggingFace safetensors 模型（Florence-2 / Llama 等）
  4. API (OpenAI兼容)          — 在线/本地 OpenAI 兼容 Chat Completions 接口

参数分层（前端 JS 按 backend 自动显隐后端专属 widget）：
  · 公共参数（四后端共用）：prompt_text / system_template / custom_system_prompt /
    temperature / top_p / top_k / repeat_penalty / seed / max_tokens / speed_preset / image_1~16
  · 官方PE 专属：clip(输入) / pe_mode / min_p / thinking / mtp
  · 本地LLaMA 专属：llm_model_name / mmproj_name / chat_handler / n_ctx / n_gpu_layers / load_mtp / keep_loaded
  · 本地HF 专属：hf_model_name / hf_task / hf_device / hf_keep_loaded
  · API 专属：api_base / api_key / api_model_name / timeout

输出统一 10 路（四个后端一致）：
  ENHANCED_PROMPT / WH_RATIO / RATIO_FOLLOW / RAW_OUTPUT / THINKING /
  RECOMMENDED_STEPS / RECOMMENDED_CFG / RECOMMENDED_SAMPLER / RECOMMENDED_SCHEDULER /
  MERGED_TEXT

模型目录（相对路径）：ComfyUI/models/LLM  —  放置所有 GGUF / HF 模型文件
"""
import gc
import inspect
import json
import os
import re
import time
import struct as _struct
import urllib.request

import folder_paths

try:
    import comfy.model_management as mm
except Exception:
    mm = None

# BSAI Qwen image 2.1 采样器依赖（老式节点，参照官方 SamplerCustomAdvanced / KSampler 语义）
try:
    import comfy.samplers as _comfy_samplers
    import comfy.sample as _comfy_sample
    import comfy.utils as _comfy_utils
    import comfy.nested_tensor as _comfy_nested_tensor
    import latent_preview as _latent_preview
    _BSAI_SAMPLER_NAMES = list(_comfy_samplers.KSampler.SAMPLERS)
    _BSAI_SCHEDULER_NAMES = list(_comfy_samplers.KSampler.SCHEDULERS)
except Exception:
    _comfy_samplers = None
    _comfy_sample = None
    _comfy_utils = None
    _comfy_nested_tensor = None
    _latent_preview = None
    _BSAI_SAMPLER_NAMES = ["euler", "euler_ancestral", "heun", "dpmpp_2m", "dpmpp_2m_sde",
                            "dpmpp_sde", "ddim", "uni_pc", "lcm", "tcd"]
    _BSAI_SCHEDULER_NAMES = ["normal", "karras", "exponential", "sgm_uniform",
                             "simple", "ddim_uniform", "beta"]

# llama-cpp-python（本地 GGUF 模型推理），未安装时不影响其他后端
try:
    from llama_cpp import Llama
except Exception:
    Llama = None

# 专用 chat handler（与 BSAI_ComfyUI_Nodes 对齐，优先用专用 handler 而非 MTMDChatHandler）
try:
    from llama_cpp.llama_chat_format import Qwen3VLChatHandler
except Exception:
    Qwen3VLChatHandler = None

try:
    from llama_cpp.llama_chat_format import Qwen35ChatHandler
except Exception:
    Qwen35ChatHandler = None

try:
    from llama_cpp.llama_chat_format import Gemma4ChatHandler
except Exception:
    Gemma4ChatHandler = None

from .common import (
    build_official_chat, collect_images, get_enhanced_result,
    image_tensor_to_data_urls, load_official_system_prompt,
    resolve_template, template_display_list,
)

# ---- Backend options (the front-end JS matches these labels exactly to show/hide
#      the matching widget groups; keep them in sync with web/prompt_enhancer.js) ----
BACKEND_PE = "Official PE (local Qwen3.5-9B)"
BACKEND_LLAMA = "Local LLaMA (GGUF+mmproj)"
BACKEND_HF = "Local HF (Transformers)"
BACKEND_API = "API (OpenAI-compatible)"
BACKEND_STRATA = "BSAI Strata (Qwen3.8-Flash-Next @8080)"
BACKEND_NEMOTRON = "BSAI Nemotron (llama.cpp @8085)"
BACKEND_NINFER = "BSAI NInfer (local reverse-engineer @808x)"
BACKEND_LABELS = [BACKEND_PE, BACKEND_LLAMA, BACKEND_HF, BACKEND_API, BACKEND_STRATA, BACKEND_NEMOTRON, BACKEND_NINFER]

_DEFAULT_SPEED = "Standard 25 steps/CFG1 (recommended)"


# ============================================================
# 本地 LLaMA 通道辅助（扫描/配对/加载，逻辑与原 nodes_local_llama.py 一致）
# ============================================================
def _scan_gguf():
    """递归扫描本地 GGUF（model 与 mmproj），返回 ([model 列表], [mmproj 列表])
    递归所有子目录，文件名带相对子路径，便于区分同名模型。
    模型目录：ComfyUI/models/LLM 与 ComfyUI/models/text_encoders（相对路径）。"""
    # 确保 LLM 文件夹在 folder_paths 中注册（与 G 盘 BSAI_QwenNodes 对齐）
    llm_dir = os.path.join(folder_paths.models_dir, "LLM")
    try:
        if "LLM" not in folder_paths.folder_names_and_paths:
            folder_paths.folder_names_and_paths["LLM"] = (
                [llm_dir], {".gguf", ".safetensors", ".bin", ".pth", ".pt"}
            )
    except Exception:
        pass

    models, mmprojs = [], []
    dirs = []
    try:
        llm_dirs = folder_paths.get_folder_paths("LLM")
        dirs += llm_dirs
    except Exception:
        pass
    # 兜底：始终加入 models/LLM 与 models/text_encoders（相对 ComfyUI 根目录）
    dirs.append(os.path.join(folder_paths.models_dir, "LLM"))
    dirs.append(os.path.join(folder_paths.models_dir, "text_encoders"))
    seen = set()
    for d in dirs:
        if not os.path.isdir(d):
            continue
        # 递归遍历所有子目录
        for root, _subdirs, files in os.walk(d):
            for f in sorted(files):
                if not f.lower().endswith(".gguf"):
                    continue
                # 用相对路径做去重键（不同子目录同名文件视为不同）
                rel = os.path.relpath(os.path.join(root, f), d)
                if rel in seen:
                    continue
                seen.add(rel)
                if "mmproj" in f.lower():
                    mmprojs.append(rel)
                else:
                    models.append(rel)
    return sorted(models), sorted(mmprojs)


def _auto_pair_mmproj(model_name, mmprojs):
    """按名称前缀自动配对 mmproj"""
    stem = os.path.splitext(model_name)[0].lower()
    # 尝试: 去掉版本/量化后缀后按前缀匹配
    for m in mmprojs:
        mstem = os.path.splitext(m)[0].lower()
        common = os.path.commonprefix([stem, mstem])
        if len(common) >= 8:
            return m
    # 兜底: 首字母系列匹配
    for m in mmprojs:
        if model_name[:10].lower() in m.lower() or m[:10].lower() in model_name.lower():
            return m
    return ""


def _pick_chat_handler(model_name):
    """根据模型名自动选择 llama.cpp chat handler 类名。
    返回的优先是 llama-cpp-python 当前版本里**确实存在**的 handler；
    如果模型对应的新版 handler（如 Qwen35/GLM46V/LFM25VL/Step3VL）在你装的
    llama-cpp-python 里没有，自动降级到 MTMDChatHandler（llama.cpp 0.3.x
    官方推荐的"GGUF + mtmd 投影器"通用方案，Qwen3.5+/Gemma4/GLM/Step 等
    带 mtmd-mmproj 的模型都能用）。实在没法识别时返回空串，由调用方报错。"""
    n = model_name.lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
    # ----- 第一优先级：本版本 llama-cpp-python 里真实存在的专用 handler -----
    if "qwen2vl" in n or "qwen25vl" in n or "qwen2.5vl" in n:
        return "Qwen25VLChatHandler"
    if "gemma4" in n:
        return "Gemma4ChatHandler"
    if "gemma3" in n:
        return "Gemma3ChatHandler"
    if "minicpmv45" in n or "minicpm45" in n or "minicpmv26" in n or "minicpm26" in n:
        # 优先 v4.5（若 llama-cpp-python 已合入），否则 v2.6
        return "MiniCPMv45ChatHandler" if "45" in n else "MiniCPMv26ChatHandler"

    # ----- 第二优先级：模型家族名 → 期望的 handler 类名 -----
    # 这些 handler 在新版 llama-cpp-python（≥0.3.36/nightly）才存在；
    # 0.3.35（PyPI 当前最新）里没有，所以下面用 _resolve_handler_cls() 自动降级
    preferred = ""
    if "qwen38" in n or "qwen36" in n or "qwen35" in n:
        preferred = "Qwen35ChatHandler"
    elif "qwen3vl" in n or "qwen3" in n:
        preferred = "Qwen3VLChatHandler"
    elif "glm46" in n:
        preferred = "GLM46VChatHandler"
    elif "glm41" in n or "glm4" in n:
        preferred = "GLM41VChatHandler"
    elif "lfm25" in n:
        preferred = "LFM25VLChatHandler"
    elif "lfm2" in n:
        preferred = "LFM2VLChatHandler"
    elif "step3" in n:
        preferred = "Step3VLChatHandler"
    if preferred:
        return preferred

    # ----- 第三优先级：兜底 mtmd（带 mmproj-BF16 的模型基本都是 mtmd 投影） -----
    return "MTMDChatHandler"


def _resolve_handler_cls(preferred_name):
    """把期望的 handler 类名解析成**当前 llama-cpp-python 里真实可用**的类。
    顺序：preferred（若存在）→ MTMDChatHandler（若存在）→ None。
    返回 None 时上层报错，并附上当前可用 handler 清单便于排错。"""
    # 1) 首选专用 handler
    cls = _get_handler_cls(preferred_name)
    if cls is not None:
        return cls
    # 2) mtmd 通用兜底
    if preferred_name != "MTMDChatHandler":
        cls = _get_handler_cls("MTMDChatHandler")
        if cls is not None:
            print(f"[BSAI_Qwen_Prompt_Enhancer] 提示：你装的 llama-cpp-python 没有 {preferred_name}，"
                  f"已自动改用 MTMDChatHandler（通用多模态，mtmd-mmproj 投影器均可）。")
            return cls
    return None


def _list_available_handlers():
    """动态枚举 llama_cpp.llama_chat_format 里实际可用的 *ChatHandler（视觉类优先）"""
    try:
        from llama_cpp import llama_chat_format as lcf
        handlers = [n for n in dir(lcf) if n.endswith("ChatHandler")]
        # 视觉/多模态优先排序（含 V/vision/VL 字样或知名视觉模型）
        vision_kw = ("VL", "Vision", "GLM", "Gemma", "MiniCPM", "Moondream", "Llava",
                     "Step", "LFM", "Qwen", "Obsidian")
        vision = sorted([h for h in handlers if any(k in h for k in vision_kw)],
                        key=lambda x: (0, x))
        other = sorted([h for h in handlers if h not in vision], key=lambda x: (1, x))
        return vision + other
    except Exception:
        return ["Qwen3VLChatHandler", "Qwen25VLChatHandler", "Qwen35ChatHandler",
                "Gemma3ChatHandler", "Gemma4ChatHandler"]


# 友好模型名标签 -> 实际 handler 类名（用户直观可见的"最新模型"列表）
_FRIENDLY_HANDLERS = [
    # mtmd generic multimodal first: broadest compatibility (any GGUF with mtmd-mmproj works)
    ("MTMD generic multimodal (recommended: Qwen3.5+/Gemma4/GLM with mtmd-mmproj)", "MTMDChatHandler"),
    ("Qwen 3.8 / 3.6 / 3.5 vision (requires updated llama-cpp-python)", "Qwen35ChatHandler"),
    ("Qwen 3 / 3-VL vision (requires updated llama-cpp-python)", "Qwen3VLChatHandler"),
    ("Qwen 2.5-VL / 2-VL vision", "Qwen25VLChatHandler"),
    ("Gemma 4 vision", "Gemma4ChatHandler"),
    ("Gemma 3 vision (requires updated llama-cpp-python)", "Gemma3ChatHandler"),
    ("GLM 4.6V vision (requires updated llama-cpp-python)", "GLM46VChatHandler"),
    ("GLM 4.1V vision (requires updated llama-cpp-python)", "GLM41VChatHandler"),
    ("MiniCPM-V4.5 (requires updated llama-cpp-python)", "MiniCPMv45ChatHandler"),
    ("MiniCPM-V2.6", "MiniCPMv26ChatHandler"),
    ("LFM 2.5-VL (requires updated llama-cpp-python)", "LFM25VLChatHandler"),
    ("LFM 2-VL (requires updated llama-cpp-python)", "LFM2VLChatHandler"),
    ("Step 3-VL (requires updated llama-cpp-python)", "Step3VLChatHandler"),
]
_AUTO_LABEL = "auto (auto-detect Qwen3.8/Gemma4/GLM4.6 and other supported models from the model name)"


def _chat_handler_labels():
    """chat_handler 下拉：auto + 友好模型名 + 其他实际可用 handler 类名 + None"""
    friendly_labels = [lbl for lbl, _ in _FRIENDLY_HANDLERS]
    available = set(_list_available_handlers())
    mapped_cls = {cls for _, cls in _FRIENDLY_HANDLERS}
    extra = sorted([h for h in available if h not in mapped_cls])
    return [_AUTO_LABEL] + friendly_labels + extra + ["None"]


def _resolve_handler_label(label):
    """友好标签 -> 实际 handler 类名；auto 走自动识别；纯类名原样返回。
    返回 '__auto__' 表示让 _pick_chat_handler(model_name) 自动判断。"""
    if not label or label == "None":
        return ""
    if label.startswith("auto"):
        return "__auto__"
    for friendly, cls in _FRIENDLY_HANDLERS:
        if label == friendly:
            return cls
    return label  # 纯类名（Llava/Moondream/Obsidian 等）兜底


_CHAT_HANDLER_CACHE = {}


def _get_handler_cls(handler_name):
    if not handler_name:
        return None
    if handler_name in _CHAT_HANDLER_CACHE:
        return _CHAT_HANDLER_CACHE[handler_name]
    try:
        from llama_cpp import llama_chat_format as lcf
        cls = getattr(lcf, handler_name, None)
        _CHAT_HANDLER_CACHE[handler_name] = cls
        return cls
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] 加载 chat handler {handler_name} 失败: {e}")
        _CHAT_HANDLER_CACHE[handler_name] = None
        return None


# ============================================================
# 本地 HF (HuggingFace Transformers) 通道辅助
# 扫描 models/LLM 下 safetensors/bin 的 HF 模型（Florence-2 / Llama / …），
# 用 transformers 加载，覆盖非 GGUF 的本地模型，实现"调用 LLM 目录全部模型"。
# ============================================================
def _scan_hf_models():
    """扫描 models/LLM 下的 HuggingFace 模型目录 -> [{id, path, arch, kind}]
    kind: 'florence2'（视觉 caption/prompt 生成，需要图片） | 'causal'（文本 LLM）
    判定依据 config.json 的 architectures。"""
    dirs = []
    try:
        dirs += folder_paths.get_folder_paths("LLM")
    except Exception:
        pass
    dirs.append(os.path.join(folder_paths.models_dir, "LLM"))
    seen = set()
    found = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _subdirs, files in os.walk(d):
            if "config.json" not in files:
                continue
            has_weights = any(f.endswith(".safetensors") or f.endswith(".bin") for f in files)
            if not has_weights:
                continue
            rel = os.path.relpath(root, d)
            if rel in seen:
                continue
            seen.add(rel)
            cfg_path = os.path.join(root, "config.json")
            arch = ""
            kind = "causal"
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                archs = cfg.get("architectures", [])
                if archs:
                    arch = archs[0]
                if arch == "Florence2ForConditionalGeneration":
                    kind = "florence2"
                elif arch in ("LlamaForCausalLM", "GemmaForCausalLM", "Qwen2ForCausalLM",
                              "MistralForCausalLM", "GPT2LMHeadModel", "Phi3ForCausalLM"):
                    kind = "causal"
                else:
                    # 未知架构：默认按文本 causal 尝试
                    kind = "causal"
            except Exception as e:
                print(f"[BSAI_Qwen_Prompt_Enhancer] 读取 HF config 失败 {cfg_path}: {e}")
            found.append({"id": rel, "path": root, "arch": arch, "kind": kind})
    return found


def _hf_model_display_list():
    """HF 模型下拉：'目录名 [arch]'"""
    items = []
    for m in _scan_hf_models():
        label = m["id"] if m["arch"] else m["id"]
        if m["arch"]:
            label = f"{m['id']} [{m['arch']}]"
        items.append(label)
    return items


def _ninfer_model_display_list():
    """NInfer 模型下拉：所有 models/LLM 下的 *.ninfer（相对路径）。"""
    try:
        import importlib.util as _ilu, os as _os
        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "..", "BSAI-LLM-Strata", "strata_manager.py")
        if not _os.path.exists(_p):
            return []
        _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
        _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        return ["(Auto — first model found)"] + [rel for rel, _abs in _m.NInferManager.list_models()]
    except Exception:
        return []


def _nemotron_model_display_list():
    """Nemotron 模型下拉：所有 models/LLM/Nemotron 下的 *.gguf（排除 mmproj）。"""
    try:
        import importlib.util as _ilu, os as _os
        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "..", "BSAI-LLM-Strata", "strata_manager.py")
        if not _os.path.exists(_p):
            return []
        _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
        _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        return ["(Auto — first model found)"] + [
            rel for rel, _abs, kind in _m.NemotronManager.list_models() if kind == "model"
        ]
    except Exception:
        return []


def _hf_model_id_from_label(label):
    """从下拉标签反查模型目录 id（去掉尾部 [arch]）"""
    if not label:
        return ""
    m = re.search(r"\[([^\[\]]+)\]\s*$", label.strip())
    if m:
        return label.strip()[:m.start()].strip()
    return label.strip()


_HF_CACHE = {}


def _load_hf(model_dir_id, device):
    """加载 HF 模型 -> dict {model, processor/tokenizer, kind, arch}"""
    key = (model_dir_id, device)
    if key in _HF_CACHE and _HF_CACHE[key] is not None:
        return _HF_CACHE[key]
    try:
        import torch
        from transformers import AutoProcessor, AutoTokenizer, AutoModelForCausalLM
    except ImportError as e:
        raise RuntimeError(
            f"[BSAI_Qwen_Prompt_Enhancer] Missing transformers/torch: {e}\n"
            "Please run inside this ComfyUI python env: pip install transformers torch")

    # 定位模型目录
    dirs = []
    try:
        dirs += folder_paths.get_folder_paths("LLM")
    except Exception:
        pass
    dirs.append(os.path.join(folder_paths.models_dir, "LLM"))
    model_dir = None
    for d in dirs:
        p = os.path.join(d, model_dir_id)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "config.json")):
            model_dir = p
            break
    if model_dir is None:
        raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] HF model directory not found: {model_dir_id}")

    # 判定架构
    arch = ""
    with open(os.path.join(model_dir, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    archs = cfg.get("architectures", [])
    if archs:
        arch = archs[0]

    dtype = torch.float16 if device != "cpu" else torch.float32
    torch_dtype = dtype

    if arch == "Florence2ForConditionalGeneration":
        # Florence-2 需要 trust_remote_code=True（自带 modeling/configuration 脚本）
        from transformers import AutoProcessor as _AP, AutoModelForCausalLM as _AM
        processor = _AP.from_pretrained(model_dir, trust_remote_code=True)
        model = _AM.from_pretrained(model_dir, trust_remote_code=True, torch_dtype=torch_dtype)
        model = model.to(device)
        model.eval()
        entry = {"model": model, "processor": processor, "tokenizer": None,
                 "kind": "florence2", "arch": arch}
    else:
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModelForCausalLM.from_pretrained(model_dir, torch_dtype=torch_dtype)
        model = model.to(device)
        model.eval()
        entry = {"model": model, "processor": None, "tokenizer": tokenizer,
                 "kind": "causal", "arch": arch}

    _HF_CACHE[key] = entry
    print(f"[BSAI_Qwen_Prompt_Enhancer] 加载本地 HF 模型: {model_dir_id} arch={arch} device={device}")
    return entry


def _clear_hf_cache():
    _HF_CACHE.clear()


def _run_florence2(entry, images, task, max_tokens, temperature, top_p, device):
    """Florence-2 视觉生成：支持 <CAPTION> / <DETAILED_CAPTION> / <MORE_DETAILED_CAPTION>
    以及 PromptGen 微调模型常用任务。返回文本。"""
    import torch
    model = entry["model"]
    processor = entry["processor"]
    if images is None or len(images.shape) < 3 or images.shape[0] == 0:
        raise RuntimeError("[BSAI_Qwen_Prompt_Enhancer] Florence-2 needs an image_1 input wired in (vision model)")
    # 取第一张图
    arr = images.cpu().numpy()
    if arr.ndim == 4:
        arr = arr[0]
    import numpy as np
    arr = np.clip(255.0 * arr, 0, 255).astype("uint8")
    from PIL import Image
    pil = Image.fromarray(arr).convert("RGB")

    task_prompt = task if task else "<MORE_DETAILED_CAPTION>"
    inputs = processor(text=task_prompt, images=pil, return_tensors="pt").to(device)
    gen_kwargs = {"max_new_tokens": int(max_tokens), "num_beams": 3}
    try:
        if float(temperature) > 0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = float(temperature)
            gen_kwargs["top_p"] = float(top_p)
    except Exception:
        pass
    with torch.no_grad():
        generated_ids = model.generate(**inputs, **gen_kwargs)
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return text


def _run_causal_hf(entry, system_prompt, prompt_text, max_tokens, temperature, top_p, top_k, device):
    """文本 causal LLM（Llama/Gemma/Qwen 等）用 chat_template 生成。"""
    import torch
    model = entry["model"]
    tokenizer = entry["tokenizer"]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt_text},
    ]
    has_template = hasattr(tokenizer, "chat_template") and tokenizer.chat_template
    if has_template:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        # 兜底：简单拼接
        text = system_prompt + "\n\n" + prompt_text
    inputs = tokenizer(text, return_tensors="pt").to(device)
    gen_kwargs = {"max_new_tokens": int(max_tokens), "do_sample": True,
                  "temperature": float(temperature), "top_p": float(top_p)}
    if int(top_k) > 0:
        gen_kwargs["top_k"] = int(top_k)
    with torch.no_grad():
        out = model.generate(**inputs, **gen_kwargs)
    full = tokenizer.decode(out[0], skip_special_tokens=True)
    # 去掉输入部分，只保留生成段
    if has_template:
        inp_text = tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)
        if full.startswith(inp_text):
            full = full[len(inp_text):].strip()
    return full


# ============================================================
# MTP / NextN 预测层检测与自动剥离（移植自 BSAI_QwenNodes）
# Qwen3.5/3.6/3.8 等模型常带 MTP 层，旧版 llama-cpp-python 不支持，
# 这里自动检测并生成去 MTP 版本的 GGUF，保证模型能正常加载。
# ============================================================
def _check_mtp_layer(model_path):
    """检查 GGUF 文件是否包含 MTP/NextN 预测层元数据。"""
    try:
        with open(model_path, 'rb') as f:
            magic = _struct.unpack('<I', f.read(4))[0]
            if magic != 0x46554747:  # GGUF magic
                return False
            version = _struct.unpack('<I', f.read(4))[0]
            tensor_count = _struct.unpack('<Q', f.read(8))[0]
            kv_count = _struct.unpack('<Q', f.read(8))[0]

            for i in range(kv_count):
                key_len = _struct.unpack('<Q', f.read(8))[0]
                key = f.read(key_len).decode('utf-8', errors='replace')
                vtype = _struct.unpack('<I', f.read(4))[0]

                if 'nextn_predict' in key:
                    return True

                if vtype == 8:  # string
                    str_len = _struct.unpack('<Q', f.read(8))[0]
                    f.read(str_len)
                elif vtype in (4, 5, 6):  # uint32 / int32 / float32
                    f.read(4)
                elif vtype == 10:  # uint64
                    f.read(8)
                elif vtype == 7:  # bool
                    f.read(1)
                elif vtype == 2:  # uint8
                    f.read(1)
                elif vtype == 9:  # array
                    array_type = _struct.unpack('<I', f.read(4))[0]
                    array_len = _struct.unpack('<Q', f.read(8))[0]
                    if array_type == 8:  # string array
                        for _ in range(array_len):
                            sl = _struct.unpack('<Q', f.read(8))[0]
                            f.read(sl)
                    elif array_type in (4, 5, 6):
                        f.read(4 * array_len)
                    elif array_type == 10:
                        f.read(8 * array_len)
                    elif array_type == 7:
                        f.read(array_len)
                    elif array_type == 2:
                        f.read(array_len)
                    else:
                        break
                else:
                    break
    except Exception:
        pass
    return False


def _strip_mtp_layer(model_path):
    """从 GGUF 文件中剥离 MTP/NextN 层，返回剥离后文件路径，失败返回 None。"""
    try:
        from gguf.constants import GGML_QUANT_SIZES
    except Exception:
        return None

    base, ext = os.path.splitext(model_path)
    no_mtp_path = base + "-noMTP" + ext
    if os.path.exists(no_mtp_path):
        return no_mtp_path

    GGUF_MAGIC = 0x46554747
    ALIGNMENT = 32
    TYPE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

    try:
        with open(model_path, 'rb') as fin:
            magic = _struct.unpack('<I', fin.read(4))[0]
            version = _struct.unpack('<I', fin.read(4))[0]
            tensor_count = _struct.unpack('<Q', fin.read(8))[0]
            kv_count = _struct.unpack('<Q', fin.read(8))[0]

            metadata = []
            for i in range(kv_count):
                key_len = _struct.unpack('<Q', fin.read(8))[0]
                key = fin.read(key_len)
                vtype = _struct.unpack('<I', fin.read(4))[0]
                pos_before = fin.tell()
                if vtype == 8:
                    str_len = _struct.unpack('<Q', fin.read(8))[0]
                    fin.read(str_len)
                elif vtype in TYPE_SIZES:
                    fin.read(TYPE_SIZES[vtype])
                elif vtype == 9:
                    array_type = _struct.unpack('<I', fin.read(4))[0]
                    array_len = _struct.unpack('<Q', fin.read(8))[0]
                    if array_type == 8:
                        for _ in range(array_len):
                            sl = _struct.unpack('<Q', f.read(8))[0]
                            fin.read(sl)
                    elif array_type in (4, 5, 6):
                        fin.read(4 * array_len)
                    elif array_type == 10:
                        fin.read(8 * array_len)
                    elif array_type == 7:
                        fin.read(array_len)
                    elif array_type == 2:
                        fin.read(array_len)
                pos_after = fin.tell()
                fin.seek(pos_before)
                raw_bytes = fin.read(pos_after - pos_before)
                metadata.append((key, vtype, raw_bytes))

            tensor_infos = []
            for i in range(tensor_count):
                name_len = _struct.unpack('<Q', fin.read(8))[0]
                name = fin.read(name_len)
                n_dims = _struct.unpack('<I', fin.read(4))[0]
                dims = [_struct.unpack('<Q', fin.read(8))[0] for _ in range(n_dims)]
                ttype = _struct.unpack('<I', fin.read(4))[0]
                offset = _struct.unpack('<Q', fin.read(8))[0]
                tensor_infos.append((name, n_dims, dims, ttype, offset))

            data_start = fin.tell()
            padded_data_start = (data_start + ALIGNMENT - 1) // ALIGNMENT * ALIGNMENT

        new_metadata = []
        for key, vtype, raw_bytes in metadata:
            key_str = key.decode('utf-8', errors='replace')
            if 'nextn_predict' in key_str:
                continue
            if key_str.endswith('.block_count'):
                old_val = _struct.unpack('<I', raw_bytes[-4:])[0]
                new_raw = raw_bytes[:-4] + _struct.pack('<I', old_val - 1)
                new_metadata.append((key, vtype, new_raw))
            else:
                new_metadata.append((key, vtype, raw_bytes))

        new_tensor_infos = [t for t in tensor_infos if b'blk.64.' not in t[0]]

        with open(no_mtp_path, 'wb') as fout:
            fout.write(_struct.pack('<I', GGUF_MAGIC))
            fout.write(_struct.pack('<I', version))
            fout.write(_struct.pack('<Q', len(new_tensor_infos)))
            fout.write(_struct.pack('<Q', len(new_metadata)))

            for key, vtype, raw_bytes in new_metadata:
                fout.write(_struct.pack('<Q', len(key)))
                fout.write(key)
                fout.write(_struct.pack('<I', vtype))
                fout.write(raw_bytes)

            current_offset = 0
            offset_map = []
            for name, n_dims, dims, ttype, old_offset in new_tensor_infos:
                fout.write(_struct.pack('<Q', len(name)))
                fout.write(name)
                fout.write(_struct.pack('<I', n_dims))
                for d in dims:
                    fout.write(_struct.pack('<Q', d))
                fout.write(_struct.pack('<I', ttype))
                fout.write(_struct.pack('<Q', current_offset))

                if ttype in GGML_QUANT_SIZES:
                    block_size, type_size = GGML_QUANT_SIZES[ttype]
                    num_elems = 1
                    for d in dims:
                        num_elems *= d
                    tensor_size = (num_elems // block_size) * type_size
                else:
                    tensor_size = 0
                offset_map.append((old_offset, current_offset, tensor_size))
                current_offset += tensor_size
                current_offset = (current_offset + ALIGNMENT - 1) // ALIGNMENT * ALIGNMENT

            header_end = fout.tell()
            padded = (header_end + ALIGNMENT - 1) // ALIGNMENT * ALIGNMENT
            fout.write(b'\x00' * (padded - header_end))

            with open(model_path, 'rb') as fin:
                for old_offset, new_offset, tensor_size in offset_map:
                    fin.seek(padded_data_start + old_offset)
                    data = fin.read(tensor_size)
                    fout.write(data)
                    padded_written = (len(data) + ALIGNMENT - 1) // ALIGNMENT * ALIGNMENT
                    if padded_written > len(data):
                        fout.write(b'\x00' * (padded_written - len(data)))

        print(f"[BSAI_Qwen_Prompt_Enhancer] 已自动生成去 MTP 版本: {os.path.basename(no_mtp_path)}")
        return no_mtp_path
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] MTP 剥离失败: {e}")
        return None


def _reset_llm_state(llm):
    """重置 LLM 上下文状态，避免多次推理间上下文残留污染输出。"""
    try:
        ctx = getattr(llm, "_ctx", None)
        if ctx is not None and hasattr(ctx, "memory_clear"):
            ctx.memory_clear(True)
    except Exception:
        pass
    try:
        reset = getattr(llm, "reset", None)
        if callable(reset):
            reset()
        elif hasattr(llm, "n_tokens"):
            llm.n_tokens = 0
    except Exception:
        pass


def _call_chat_completion(llm, messages, params):
    """签名兼容的 create_chat_completion 调用，自动适配不同版本 llama-cpp-python 的参数名。"""
    kwargs = dict(params or {})
    kwargs["messages"] = messages
    try:
        sig = inspect.signature(llm.create_chat_completion)
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    except Exception:
        sig = None
        has_var_kw = True

    if sig is not None and not has_var_kw:
        allowed = sig.parameters
        # 兼容 presence_penalty -> present_penalty 的拼写差异
        if "presence_penalty" in kwargs and "presence_penalty" not in allowed and "present_penalty" in allowed:
            kwargs["present_penalty"] = kwargs.pop("presence_penalty")
        kwargs = {k: v for k, v in kwargs.items() if k in allowed}
    return llm.create_chat_completion(**kwargs)


def _normalize_seed(seed_value):
    """规范化 seed 值，失败返回 None（让 llama.cpp 自己随机）。"""
    try:
        seed_value = int(seed_value)
    except Exception:
        return None
    if seed_value < 0:
        return None
    return seed_value


_LLM_CACHE = {}


def _detect_family_from_name(model_name):
    """从模型名推断模型系列（与 BSAI_ComfyUI_Nodes 的 family 下拉对应）。"""
    n = model_name.lower()
    if "qwen3.8" in n or "qwen3-8" in n:
        return "Qwen3.8-VL"
    if "qwen3.6" in n or "qwen3-6" in n:
        return "Qwen3.6-VL"
    if "qwen3.5" in n or "qwen3-5" in n:
        return "Qwen3.5-VL"
    if "qwen3vl" in n or "qwen3-vl" in n or ("qwen3" in n and "vl" in n):
        return "Qwen3-VL"
    if "gemma4" in n:
        return "Gemma4"
    return ""


def _build_accel_kwargs(n_cmoe=0, kv_cache_quant="auto", use_mmap=True,
                        use_mlock=False, flash_attn="auto", threads=0):
    """llama.cpp 极限提速参数映射（-ncmoe / -ctk/-ctv / --no-mmap / --mlock / -fa / -t）。
    仅 MoE 模型的 n_cmoe 有收益（专家拆分显存/内存），稠密模型无效。
    llama-cpp-python 0.3.36：n_cmoe 暂未暴露，检测到支持会自动透传（升级后即生效）。
    """
    out = {"use_mmap": bool(use_mmap), "use_mlock": bool(use_mlock)}
    q = str(kv_cache_quant).lower()
    # llama.h llama_type: f16=1, q8_0=8, q4_0=2
    kv = {"auto": None, "f16": 1, "q8_0": 8, "q4_0": 2}.get(q)
    if kv is not None:
        out["type_k"] = kv
        out["type_v"] = kv
    fa = str(flash_attn).lower()
    if fa == "on":
        out["flash_attn_type"] = 1  # LLAMA_FLASH_ATTN_TYPE_ENABLED
    elif fa == "off":
        out["flash_attn_type"] = 0  # LLAMA_FLASH_ATTN_TYPE_DISABLED
    # auto: 不传 → 默认 AUTO(-1)
    if int(threads) > 0:
        out["n_threads"] = int(threads)
    if int(n_cmoe) > 0:
        try:
            sig = inspect.signature(Llama.__init__)
            if "n_cmoe" in sig.parameters:
                out["n_cmoe"] = int(n_cmoe)
                print(f"[BSAI_Qwen_Prompt_Enhancer] 已启用 MoE 专家拆分加速 n_cmoe={n_cmoe}")
            else:
                print("[BSAI_Qwen_Prompt_Enhancer] 当前 llama-cpp-python 不支持 n_cmoe（需支持 -ncmoe 的新构建），"
                      "已跳过专家拆分；升级 llama-cpp-python 后此参数自动生效。")
        except Exception:
            pass
    return out


def _load_llm(model_name, mmproj_name, chat_handler_name, n_ctx, n_gpu_layers, load_mtp,
              n_cmoe=0, kv_cache_quant="auto", use_mmap=True, use_mlock=False,
              flash_attn="auto", threads=0):
    """加载本地 GGUF 模型 — 精确对齐 BSAI_ComfyUI_Nodes 的 BSAI_QwenNodes.py 加载逻辑。
    优先使用 Qwen35ChatHandler / Qwen3VLChatHandler / Gemma4ChatHandler 等专用 handler，
    不用 MTMDChatHandler（部分版本缺符号，会导致崩溃）。"""
    if Llama is None:
        raise RuntimeError(
            "llama-cpp-python (llama_cpp) not found. Please install the dependency first.\n"
            "Install: run `pip install llama-cpp-python` in the ComfyUI python environment."
        )

    key = (model_name, mmproj_name, chat_handler_name, n_ctx, n_gpu_layers, load_mtp,
           int(n_cmoe or 0), str(kv_cache_quant).lower(), bool(use_mmap), bool(use_mlock),
           str(flash_attn).lower(), int(threads or 0))
    if key in _LLM_CACHE and _LLM_CACHE[key] is not None:
        cached_llm, cached_active = _LLM_CACHE[key]
        return cached_llm, cached_active

    # ---- 模型目录：使用 ComfyUI 内置的 models/LLM 相对路径 ----
    dirs = []
    try:
        dirs += folder_paths.get_folder_paths("LLM")
    except Exception:
        pass
    dirs.append(os.path.join(folder_paths.models_dir, "LLM"))
    dirs.append(os.path.join(folder_paths.models_dir, "text_encoders"))

    def find(name):
        for d in dirs:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
        raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] Model file not found: {name} (searched {dirs})")

    model_path = find(model_name)

    # ---- MTP 层自动检测与预剥离（与 BSAI_QwenNodes 完全一致）----
    has_mtp = _check_mtp_layer(model_path)
    if has_mtp and not load_mtp:
        no_mtp_path = _strip_mtp_layer(model_path)
        if no_mtp_path and os.path.exists(no_mtp_path):
            model_path = no_mtp_path
            print(f"[BSAI_Qwen_Prompt_Enhancer] 检测到 MTP 层，已切换到去 MTP 版本: "
                  f"{os.path.basename(no_mtp_path)}")

    # ---- chat handler：优先用专用 handler（与 BSAI_QwenNodes 一致）----
    mmproj_path = None
    if mmproj_name:
        mmproj_path = find(mmproj_name)

    chat_handler = None
    mmproj_actually_active = False
    if mmproj_path:
        # 1) 先按模型名推断家族，尝试专用 handler（最可靠）
        family = _detect_family_from_name(model_name)

        # 2) 若用户在下拉里选了特定 handler 名（非 auto / 非 None），用那个覆盖
        resolved = _resolve_handler_label(chat_handler_name)
        if resolved and resolved != "__auto__":
            # 用户明确指定了 handler 类名，直接用
            handler_cls = _resolve_handler_cls(resolved)
            if handler_cls is not None:
                # 专用 handler：按 BSAI_QwenNodes 的参数组合构造
                try:
                    chat_handler = handler_cls(
                        clip_model_path=mmproj_path,
                        enable_thinking=False,
                        verbose=False,
                        use_gpu=False,
                        image_min_tokens=1024,
                    )
                except TypeError:
                    # 老版本 handler 参数不同，降级尝试
                    try:
                        chat_handler = handler_cls(
                            clip_model_path=mmproj_path,
                            verbose=False,
                            use_gpu=False,
                            image_min_tokens=1024,
                        )
                    except Exception:
                        chat_handler = None
                except Exception:
                    chat_handler = None

        # 3) 自动模式 / 指定 handler 失败 → 按家族用专用 handler（BSAI_QwenNodes 同款）
        if chat_handler is None and family in ("Qwen3.5-VL", "Qwen3.6-VL", "Qwen3.8-VL"):
            if Qwen35ChatHandler is not None:
                try:
                    chat_handler = Qwen35ChatHandler(
                        clip_model_path=mmproj_path,
                        enable_thinking=False,
                        verbose=False,
                        use_gpu=False,
                        image_min_tokens=1024,
                    )
                except Exception:
                    try:
                        chat_handler = Qwen35ChatHandler(
                            clip_model_path=mmproj_path,
                            verbose=False,
                            use_gpu=False,
                            image_min_tokens=1024,
                        )
                    except Exception:
                        chat_handler = None

        if chat_handler is None and family == "Qwen3-VL":
            if Qwen3VLChatHandler is not None:
                try:
                    chat_handler = Qwen3VLChatHandler(
                        clip_model_path=mmproj_path,
                        force_reasoning=False,
                        verbose=False,
                        use_gpu=False,
                        image_min_tokens=1024,
                    )
                except Exception:
                    try:
                        chat_handler = Qwen3VLChatHandler(
                            clip_model_path=mmproj_path,
                            verbose=False,
                            use_gpu=False,
                            image_min_tokens=1024,
                        )
                    except Exception:
                        chat_handler = None

        if chat_handler is None and family == "Gemma4":
            if Gemma4ChatHandler is not None:
                try:
                    chat_handler = Gemma4ChatHandler(
                        clip_model_path=mmproj_path,
                        enable_thinking=False,
                        verbose=False,
                        use_gpu=False,
                        image_min_tokens=1024,
                    )
                except Exception:
                    try:
                        chat_handler = Gemma4ChatHandler(
                            clip_model_path=mmproj_path,
                            verbose=False,
                            use_gpu=False,
                            image_min_tokens=1024,
                        )
                    except Exception:
                        chat_handler = None

        # 4) 专用 handler 都没有 → 尝试通用 MTMDChatHandler（注意：旧版可能缺符号）
        if chat_handler is None:
            mtmd_cls = _resolve_handler_cls("MTMDChatHandler")
            if mtmd_cls is not None:
                try:
                    chat_handler = mtmd_cls(clip_model_path=mmproj_path, verbose=False)
                except Exception as e:
                    print(
                        f"[BSAI_Qwen_Prompt_Enhancer] [WARN] MTMDChatHandler 初始化失败: {e}\n"
                        "    已降级为纯文本模式（图片将不会被发送给模型）。\n"
                        "    建议：更新 llama-cpp-python 到支持 Qwen35ChatHandler 的版本。"
                    )
                    chat_handler = None

        mmproj_actually_active = chat_handler is not None

    # ---- 加载模型：与 BSAI_QwenNodes 完全一致的参数组合 ----
    llama_kwargs = {
        "model_path": model_path,
        "chat_handler": chat_handler,
        "n_ctx": int(n_ctx),
        "n_gpu_layers": int(n_gpu_layers),
        "verbose": False,
    }

    # ── 视频同款极限提速参数（n_cmoe / KV量化 / mmap / mlock / flash-attn / 线程）──
    llama_kwargs.update(_build_accel_kwargs(
        n_cmoe=int(n_cmoe or 0),
        kv_cache_quant=str(kv_cache_quant),
        use_mmap=bool(use_mmap),
        use_mlock=bool(use_mlock),
        flash_attn=str(flash_attn),
        threads=int(threads or 0),
    ))

    display_name = os.path.basename(model_path)
    handler_label = type(chat_handler).__name__ if chat_handler else "None"
    print(f"[BSAI_Qwen_Prompt_Enhancer] 加载本地 LLaMA: {display_name} "
          f"+ {mmproj_name or '无'} handler={handler_label} "
          f"(active={mmproj_actually_active}) n_ctx={n_ctx} n_gpu_layers={n_gpu_layers}")

    try:
        llm = Llama(**llama_kwargs)
    except ValueError as e:
        err_str = str(e)
        if "Failed to load model from file" in err_str:
            # MTP 相关失败：自动尝试去 MTP 版本
            if has_mtp and not load_mtp:
                no_mtp_path = _strip_mtp_layer(model_path)
                if no_mtp_path and no_mtp_path != model_path:
                    print(f"[BSAI_Qwen_Prompt_Enhancer] 模型加载失败，尝试去 MTP 版本: "
                          f"{os.path.basename(no_mtp_path)}")
                    llama_kwargs["model_path"] = no_mtp_path
                    try:
                        llm = Llama(**llama_kwargs)
                        _LLM_CACHE[key] = (llm, mmproj_actually_active)
                        return llm, mmproj_actually_active
                    except Exception:
                        pass
                raise RuntimeError(
                    "Model load failed: this GGUF contains MTP/NextN prediction layers (nextn_predict_layers),\n"
                    "which the installed llama-cpp-python does not support.\n\n"
                    "Fix:\n"
                    "1. An MTP-stripped version was auto-generated if possible — look for a -noMTP.gguf next to the file\n"
                    "2. Manually use an MTP-stripped GGUF\n"
                    "3. Or use a Qwen3.5/3.6/3.8 model without MTP layers\n"
                    f"Original error: {e}"
                )
            raise RuntimeError(
                "Model load failed: Failed to load model from file\n"
                "Possible causes:\n"
                "1. The model file is corrupted or the format is unsupported\n"
                "2. The llama-cpp-python version does not support this model architecture\n"
                "3. The model file path is wrong\n"
                "Suggestions:\n"
                "- Check the model file integrity\n"
                "- Update llama-cpp-python to the latest version\n"
                "- Make sure the model path is correct"
            )
        if "Failed to create context with model" in err_str:
            raise RuntimeError(
                "Model load failed: Failed to create context with model\n"
                "Possible causes:\n"
                "1. The model file is corrupted or the format is unsupported\n"
                "2. The llama-cpp-python version does not support this model\n"
                "3. Out of VRAM\n"
                "4. The model file path is wrong\n"
                "Suggestions:\n"
                "- Check the model file integrity\n"
                "- Update llama-cpp-python to the latest version\n"
                "- Reduce GPU layers or use a smaller model\n"
                "- Make sure the model path is correct"
            )
        raise

    _LLM_CACHE[key] = (llm, mmproj_actually_active)
    return llm, mmproj_actually_active


def _clear_cache():
    """清空本地 LLaMA 缓存并释放显存（与 G 盘 BSAI_QwenNodes 对齐）。"""
    for key, entry in list(_LLM_CACHE.items()):
        try:
            llm = entry[0]
            if llm and hasattr(llm, 'close'):
                llm.close()
        except Exception:
            pass
    _LLM_CACHE.clear()
    gc.collect()
    if mm is not None:
        mm.soft_empty_cache()


# ============================================================
# 三合一增强节点
# ============================================================
class BSAI_Qwen_Prompt_Enhancer:
    # 【v1.01】一键兼容旧工作流存档：hf_model_name / llm_model_name / system_template 等 combo
    # 在「模型未下载 / 模型目录变化 / 模板库版本不同」时，存档值可能不在当前下拉列表
    # （典型报错：Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']）。
    # ComfyUI 默认会对 combo 做 value-in-list 校验并红框报错、阻塞整图（Output will be ignored）。
    # 这里放行所有 combo 校验：开图不红框、不阻塞；运行时后端逻辑会给出友好中文提示，
    # 前端 JS（prompt_enhancer.js）还会在加载工作流时自动把非法 combo 值重置为当前列表首项。
    @staticmethod
    def VALIDATE_INPUTS(*args, **kwargs):
        # Return-value compatibility across ComfyUI versions:
        # - Legacy positional call VALIDATE_INPUTS(input_name, input_value): return None = pass.
        # - Modern call passes all inputs as **kwargs and expects a boolean (None raises
        #   "Custom validation failed for node: X - None"); kwargs form also skips combo checks.
        if not kwargs and len(args) == 2:
            return None
        # Security: the Local HF backend loads weights with trust_remote_code=True, so an
        # attacker-supplied model name must be checked against the actually-scanned model
        # list instead of resolving to an arbitrary directory. Same for the local GGUF LLM.
        # Reject even when the scanned list is empty (no models available => no model name valid).
        try:
            backend = kwargs.get("backend")
            if backend == BACKEND_HF:
                sel = kwargs.get("hf_model_name") or ""
                if sel and not str(sel).startswith("<No "):
                    available = {m["id"] for m in _scan_hf_models()}
                    if _hf_model_id_from_label(str(sel)) not in available:
                        return False
            elif backend == BACKEND_LLAMA:
                sel = kwargs.get("llm_model_name") or ""
                models, mmprojs = _scan_gguf()
                if sel and str(sel) not in set(models):
                    return False
                # Also validate mmproj_name against the scanned list
                mmproj_sel = kwargs.get("mmproj_name") or ""
                if mmproj_sel and mmproj_sel not in set(mmprojs):
                    return False
        except Exception:
            # On scan error, reject rather than pass through — an unverified model name
            # must not reach the trust_remote_code loader.
            return False
        return True

    @classmethod
    def INPUT_TYPES(cls):
        # 每次打开节点都重新递归扫描，新增模型无需重启 ComfyUI
        models, mmprojs = _scan_gguf()
        no_model = "<No GGUF model found>"
        return {
            "required": {
                # ---- backend switch ----
                "backend": (BACKEND_LABELS, {"default": BACKEND_PE}),
                # ---- shared parameters (used by all backends) ----
                "prompt_text": ("STRING", {
                    "multiline": True,
                    "default": "A girl in a red dress standing under a cherry tree, holding bubble tea, evening light",
                    "placeholder": "Enter your plain-language prompt (Chinese or English). In I2I / multi-image mode use image_1/image_2... to refer to reference images.",
                }),
                "system_template": (template_display_list(), {"default": "Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]"}),
                "custom_system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "Leave empty to use the template above; fill in to override the template as the system prompt",
                }),
                # Extra user requirement (appended to the MERGED_TEXT output), not sent into the LLM internal chat.
                "user_requirement": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "Extra requirements for this task (appended to the MERGED_TEXT output, used together with the template wall below).\ne.g.: Cover has a main title + subtitle; put the hero visual on the left and leave white space for copy on the right; use a deep-blue + orange-gold palette.",
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.01}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01,
                                    "tooltip": "核采样阈值。注意：ComfyUI v0.42+（#17221）修正了 top-p 边界语义"
                                               "（>= 判定 + 右移一位），同一 seed 的输出与旧核心不保证一致；"
                                               "本地 LLaMA (llama.cpp) 后端不受影响。"}),
                "top_k": ("INT", {"default": 40, "min": 0, "max": 1000}),
                "repeat_penalty": ("FLOAT", {"default": 1.1, "min": 0.0, "max": 5.0, "step": 0.01}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "max_tokens": ("INT", {"default": 4096, "min": 64, "max": 32768}),
                "speed_preset": (list(cls._SPEED_PRESETS.keys()), {"default": _DEFAULT_SPEED}),
                # ---- 官方PE 专属 ----
                "pe_mode": (["auto", "T2I (text-to-image)", "I2I (image-to-image / edit)"], {"default": "auto"}),
                "min_p": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "thinking": ("BOOLEAN", {"default": True}),
                "mtp": (["auto", "off", "2", "3", "4", "5"], {"default": "auto"}),
                # ---- 本地LLaMA 专属 ----
                "llm_model_name": ((models if models else [no_model]), {"default": models[0] if models else no_model}),
                "mmproj_name": ([""] + mmprojs, {"default": _auto_pair_mmproj(models[0], mmprojs) if models else ""}),
                "chat_handler": (_chat_handler_labels(), {"default": _AUTO_LABEL}),
                "n_ctx": ("INT", {"default": 8192, "min": 512, "max": 65536}),
                "n_gpu_layers": ("INT", {"default": -1, "min": -1, "max": 200}),
                "load_mtp": ("BOOLEAN", {"default": False,
                    "tooltip": "MTP (Multi-Token Prediction) 层保留开关。官方 ComfyUI v0.42 / 新版 llama.cpp 已支持 Qwen 3.x/3.5 MTP（含图像场景，含 MTP embedding offload 修复）；模型带 nextn_predict 元数据且关闭本开关时自动剥离 MTP 层。追求吞吐加速可开启（需底层 llama.cpp 支持，开启失败时模型加载会报错，回退关闭即可）。"}),
                # ---- 极限提速参数（视频同款 llama.cpp：显存+内存混合模式）----
                "n_cmoe": ("INT", {
                    "default": 0, "min": 0, "max": 256, "step": 1,
                    "tooltip": "Split MoE experts across CPU/RAM layers (-ncmoe). Only effective for MoE models, not dense.\nQwen-35B-A3B is most stable around 24; 0 = off. Current 0.3.36 does not support it yet; it applies automatically after upgrading.",
                }),
                "kv_cache_quant": (["auto (f16, no quant)", "q8_0", "q4_0"], {
                    "default": "auto (f16, no quant)",
                    "tooltip": "KV cache quantization (-ctk/-ctv, q4_0 = video effect). Lower VRAM and faster, at a slight quality cost.",
                }),
                "use_mmap": ("BOOLEAN", {"default": True, "tooltip": "use_mmap; can disable when RAM is tight / swapping (--no-mmap)."}),
                "use_mlock": ("BOOLEAN", {"default": False, "tooltip": "use_mlock (--mlock) locks the model in RAM to avoid page-out."}),
                "flash_attn": (["auto", "on", "off"], {"default": "auto", "tooltip": "-fa. auto = enable when the model supports it."}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1, "tooltip": "-t thread count (video example: 14); 0 = auto."}),
                "keep_loaded": ("BOOLEAN", {"default": False}),
                # ---- API 专属 ----
                "api_base": ("STRING", {
                    "default": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "placeholder": "OpenAI-compatible endpoint, e.g. https://dashscope.aliyuncs.com/compatible-mode/v1 or http://127.0.0.1:8000/v1",
                }),
                "api_key": ("STRING", {"default": "", "placeholder": "API Key (required for online services)"}),
                "api_model_name": ("STRING", {
                    "default": "qwen3.5-vl-9b",
                    "placeholder": "Model name, e.g. qwen3.5-vl-9b / qwen-plus / a locally deployed model name",
                }),
                "timeout": ("INT", {"default": 120, "min": 10, "max": 600}),
                # ---- BSAI Strata only ----
                "strata_quant": (["Auto (auto-adapt)", "Q2_0 (fastest)", "IQ2_XS (slightly better)",
                                  "IQ3_XXS (better)", "IQ3_S (best quality)"],
                                 {"default": "Auto (auto-adapt)",
                                  "tooltip": "Strata quantization. Auto picks based on VRAM/RAM."}),
                # ---- BSAI NInfer only: which *.ninfer model to load ----
                "ninfer_model": (_ninfer_model_display_list() or ["(Auto — first model found)"],
                                 {"default": "(Auto — first model found)",
                                  "tooltip": "NInfer model to load (models/LLM/*.ninfer). Changing it restarts the NInfer engine on the next run."}),
                # ---- BSAI Nemotron only: which GGUF model to load ----
                "nemotron_model": (_nemotron_model_display_list() or ["(Auto — first model found)"],
                                  {"default": "(Auto — first model found)",
                                   "tooltip": "Nemotron GGUF model to load (models/LLM/Nemotron/*.gguf, excludes mmproj). Changing it restarts the llama.cpp server on the next run."}),
                # ---- Local HF (Transformers) only ----
                "hf_model_name": (_hf_model_display_list() or ["<No HF model found>"],),
                "hf_task": (["<MORE_DETAILED_CAPTION>", "<DETAILED_CAPTION>", "<CAPTION>", "<OD>", "<REGION_CAPTION>"], {"default": "<MORE_DETAILED_CAPTION>"}),
                "hf_device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "hf_keep_loaded": ("BOOLEAN", {"default": True}),
                # 【v3】纯预览：勾上后跳过所有模型调用，仅输出 MERGED_TEXT。
                # 海报墙选模板时会自动勾上 → 触发一次 queuePrompt → 下游 Show Text 立即显示。
                # 用户后续要 LLM 增强时手动关掉再 Queue Prompt。
                "preview_only": ("BOOLEAN", {"default": False, "label": "Preview only (skip LLM)"}),
            },
            "optional": {
                "clip": ("CLIP",),
                **{f"image_{i}": ("IMAGE",) for i in range(1, 17)},
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "INT", "FLOAT", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("ENHANCED_PROMPT", "WH_RATIO", "RATIO_FOLLOW", "RAW_OUTPUT", "THINKING",
                    "RECOMMENDED_STEPS", "RECOMMENDED_CFG", "RECOMMENDED_SAMPLER", "RECOMMENDED_SCHEDULER",
                    "MERGED_TEXT")
    FUNCTION = "enhance"
    CATEGORY = "BSAI/Qwen Image 2.1"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "One node, four enhancement backends (switch via the backend dropdown; the matching widgets are shown/hidden automatically):\n"
        "(1) Official PE (local Qwen3.5-9B): load the official PE model from text_encoders with CLIPLoader, "
        "generate via the official chat template, outputting rewritten_prompt / wh_ratio / ratio_follow; "
        "I2I mode accepts image_1~image_16 (up to 16 images), refer to them as image_1/image_2 in the prompt.\n"
        "(2) Local LLaMA (GGUF+mmproj): llama.cpp loads a local vision LLM, auto-scanning models/LLM and text_encoders, "
        "reverse-engineering multi-image prompts; chat_handler auto-detects the latest model families.\n"
        "(3) Local HF (Transformers): loads HuggingFace safetensors models under models/LLM, "
        "covering Florence-2 (vision caption-to-prompt, requires image_1) and text LLMs such as Llama/Gemma (chat_template generation).\n"
        "(4) API (OpenAI-compatible): configure api_base / api_key / model_name to call an online or local API.\n"
        "Shared parameters apply to all backends; outputs are unified across 10 ports. Pick a speed_preset and the RECOMMENDED_* ports "
        "output the matching KSampler settings; on a KSampler right-click steps/cfg -> Convert to input to apply them in one click. "
        "Qwen Image 2.1 is a CFG-distilled architecture; the official recommendation is cfg=1.0. Acceleration presets are based on official day-0 settings (25 steps/cfg1/euler/simple). "
        "v1.08.0 adds distilled-LoRA presets: Viggle Turbo 6 steps (official node) / Pruna 5-8 steps (community conversion) / Alibaba PAI Fun-Acc 4 steps (experimental). "
        "Distilled presets require the matching LoRA and fixed sigmas (Viggle Turbo Sigmas / ManualSigmas / PDD); see ACCELERATION_GUIDE.md."
    )

    # 加速档位 → (steps, cfg, sampler, scheduler[, hint])
    # Qwen Image 2.1 是 CFG-distilled 架构，cfg=1.0 为官方推荐值（非旧版的 3~4）
    # 官方 day-0 联调：25步/cfg1/euler/simple（ComfyUI v0.37.0+ 原生模板）
    # v1.08.0 新增：2026-09~10 已发布的 2.1 专用蒸馏 LoRA 档（Viggle / Pruna / 阿里PAI Fun-Acc）。
    # 蒸馏档必须搭配对应 LoRA + 固定 sigma（Viggle Turbo Sigmas / ManualSigmas / PDD），
    # 不能直接用普通 KSampler 的 scheduler 生成 sigma，否则出噪图；详见 ACCELERATION_GUIDE.md。
    _SPEED_PRESETS = {
        # ===== Native 2.1 correct settings (based on official day-0 tuning) =====
        _DEFAULT_SPEED: (25, 1.0, "euler", "simple"),
        "Fast 15 steps/CFG1 (iteration preview)": (15, 1.0, "euler", "simple"),
        "Turbo 10 steps/CFG1 (quick draft)": (10, 1.0, "euler", "simple"),
        "High quality 35 steps/CFG1 (detailed output)": (35, 1.0, "euler", "simple"),
        # ===== With external acceleration nodes (no LoRA) =====
        "Cached 20 steps/CFG1 (with EasyCache node)": (20, 1.0, "euler", "simple"),
        # ===== Distilled LoRA presets (2.1-specific distilled adapters, released 2026-09~10) =====
        "Viggle Turbo 6 steps/CFG1 (official node, recommended)": (
            6, 1.0, "euler", "simple",
            "Viggle v0.3: the comfyui/viggle_turbo.py model repo provides Viggle Turbo Sigmas + Viggle Turbo LoRA (unmerged). "
            "Wire BasicGuider + SamplerCustomAdvanced, CFG=1.0, leave the negative empty; do not use KSampler's own scheduler. "
            "Original 6-step sigma = 1.0,0.9375,0.875,0.75,0.5,0.25 (node shifts by resolution). "
            "The ComfyUI workflow uses the r128 build (downloaded to models/loras); this machine also has an older v0.1 4-step r64 build.",
        ),
        "Viggle Turbo 9 steps/CFG1 (diffusers only)": (
            9, 1.0, "euler", "simple",
            "v0.3 9-step mode = first 7 steps turbo + last 2 steps back to the base model; better detail/small text (about 3.5x faster than 40 steps). "
            "Currently only available in diffusers and the demo Space; not yet in ComfyUI.",
        ),
        "Pruna 8 steps/CFG1 (quality-first, recommended)": (
            8, 1.0, "euler", "simple",
            "Pruna 8 steps (official recommended default): sigma=1.0,0.933333333,0.857142857,0.769230769,0.666666667,"
            "0.545454545,0.4,0.222222222 (trailing 0 filled by the scheduler). Requires the community-converted LoRA (NidAll/pruna-image-2.1-comfyui-loras, "
            "with built-in alpha scalar) + ManualSigmas + SamplerCustom; CFG=1.0, leave negative empty.",
        ),
        "Pruna 5 steps/CFG1 (turbo)": (
            5, 1.0, "euler", "simple",
            "Pruna 5 steps: sigma=1.0,0.94,0.857142857,0.666666667,0.4; about 1.06s on H100 @1024 (5.7x faster). "
            "Quality is noticeably below the 8-step version; usage is the same (converted LoRA + ManualSigmas + SamplerCustom).",
        ),
        "Official Fun-Acc 4 steps/CFG1 (PAI, experimental)": (
            4, 1.0, "euler", "simple",
            "Alibaba PAI official 4-step distillation (PDD): sigma=1.0,0.9169867,0.7861579,0.549491,0.0; samples at 2048 by default. "
            "No official ComfyUI support: requires Kijai's Qwen-Image-2.1-PDD branch + LoRA conversion (norm_q/norm_k/text_norm are full-parameter). "
            "This is a community experimental path.",
        ),
        # ===== Legacy compatibility (keys kept so old workflows keep working; values corrected to 2.1-correct settings) =====
        "Legacy standard 20 steps/CFG3 (recommended, 7B native)": (25, 1.0, "euler", "simple"),
        "Legacy turbo 8 steps/CFG2": (8, 1.0, "euler", "simple"),
        "Legacy lightning 4 steps/CFG1 (requires 2.1 Lightning LoRA)": (4, 1.0, "euler", "simple"),
        "Legacy conservative 50 steps/CFG4": (35, 1.0, "euler", "simple"),
    }

    def enhance(self, backend, prompt_text, system_template, custom_system_prompt="",
                user_requirement="",
                temperature=0.7, top_p=0.95, top_k=40, repeat_penalty=1.1, seed=0,
                max_tokens=4096, speed_preset=_DEFAULT_SPEED,
                pe_mode="auto", min_p=0.0, thinking=True, mtp="auto",
                llm_model_name="", mmproj_name="", chat_handler="", n_ctx=8192,
                n_gpu_layers=-1, load_mtp=False, keep_loaded=False,
                n_cmoe=0, kv_cache_quant="auto (f16, no quant)", use_mmap=True, use_mlock=False,
                flash_attn="auto", threads=0,
                api_base="", api_key="", api_model_name="", timeout=120,
                strata_quant="Auto (auto-adapt)",
                ninfer_model="(Auto — first model found)",
                nemotron_model="(Auto — first model found)",
                hf_model_name="", hf_task="<MORE_DETAILED_CAPTION>", hf_device="auto", hf_keep_loaded=True,
                preview_only=False,
                clip=None,
                image_1=None, image_2=None, image_3=None, image_4=None, image_5=None, image_6=None,
                image_7=None, image_8=None, image_9=None, image_10=None, image_11=None, image_12=None,
                image_13=None, image_14=None, image_15=None, image_16=None):
        # 【v3】纯预览：勾上后跳过所有模型调用，仅输出 MERGED_TEXT。
        # 用于海报墙选模板时让下游 Show Text 立刻显示，无需加载 LLM。
        if preview_only:
            print(f"[BSAI_Qwen_Prompt_Enhancer] [preview] custom_system_prompt={custom_system_prompt!r} len={len(custom_system_prompt or '')} system_template={system_template!r}")
            merged_text = self._build_preview_merged(
                system_template=system_template,
                custom_system_prompt=custom_system_prompt,
                user_requirement=user_requirement,
            )
            steps, cfg, sampler, scheduler, *extra = self._SPEED_PRESETS.get(
                speed_preset, self._SPEED_PRESETS[_DEFAULT_SPEED])
            print(f"[BSAI_Qwen_Prompt_Enhancer] 纯预览模式 → 仅输出 MERGED_TEXT，不调用任何模型")
            # 【修复 2026-09-23】纯预览同样释放常驻 LLM（此前 keep_loaded=true 遗留的 27B 占 ~20GB 显存），
            # 否则预览/后续出图仍会被常驻 LLM 拖死。_clear_cache 只清本地 LLaMA 缓存，不影响 clip。
            _clear_cache()
            hint_line = f"\n⚠ {extra[0]}" if extra else ""
            ui_text = [
                merged_text,
                f"\n── Preview-only mode ──\nNo model was called. MERGED_TEXT is ready and can be used directly by a downstream Show Text / KSampler.\n"
                f"To run the LLM enhancement, disable 'Preview only' and Queue Prompt again.\n"
                f"\n── Current speed preset: {speed_preset} → steps={steps}, cfg={cfg}, sampler={sampler}, scheduler={scheduler} ──"
                f"{hint_line}",
            ]
            # 【修复 2026-09-23 v2】海报墙选模板后，ENHANCED_PROMPT(第1路) 输出模板拼接 merged_text：
            # 无论后端模式，选模板后提示词统一走 ENHANCED_PROMPT 展示模板效果（用户需求）。
            # 无模板且无用户要求时 merged_text 为空 → 回退用户原文 prompt_text，防空条件出沙土图。
            enhanced_out = merged_text if (merged_text or "").strip() else (prompt_text or "")
            return {
                "ui": {"text": ui_text, "merged_text": [merged_text]},
                "result": (enhanced_out, "", "", merged_text, "",
                           int(steps), float(cfg), sampler, scheduler, merged_text),
            }

        images = collect_images(image_1, image_2, image_3, image_4, image_5, image_6,
                                image_7, image_8, image_9, image_10, image_11, image_12,
                                image_13, image_14, image_15, image_16)
        if backend == BACKEND_PE:
            return self._enhance_official(
                clip=clip, prompt_text=prompt_text, pe_mode=pe_mode,
                system_template=system_template, custom_system_prompt=custom_system_prompt,
                user_requirement=user_requirement,
                max_tokens=max_tokens, temperature=temperature, top_p=top_p, top_k=top_k,
                repeat_penalty=repeat_penalty, min_p=min_p, seed=seed, thinking=thinking,
                mtp=mtp, speed_preset=speed_preset, images=images,
            )
        if backend == BACKEND_LLAMA:
            return self._enhance_local(
                llm_model_name=llm_model_name, mmproj_name=mmproj_name, chat_handler=chat_handler,
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, top_k=top_k, repeat_penalty=repeat_penalty,
                seed=seed, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, load_mtp=load_mtp,
                keep_loaded=keep_loaded, speed_preset=speed_preset, images=images,
                n_cmoe=n_cmoe, kv_cache_quant=kv_cache_quant, use_mmap=use_mmap,
                use_mlock=use_mlock, flash_attn=flash_attn, threads=threads,
            )
        if backend == BACKEND_HF:
            return self._enhance_hf(
                hf_model_name=hf_model_name, hf_task=hf_task, hf_device=hf_device,
                hf_keep_loaded=hf_keep_loaded,
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, top_k=top_k, seed=seed,
                speed_preset=speed_preset, images=images,
            )
        if backend == BACKEND_API:
            return self._enhance_api(
                api_base=api_base, api_key=api_key, api_model_name=api_model_name,
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, top_k=top_k, seed=seed,
                timeout=timeout, speed_preset=speed_preset, images=images,
            )
        if backend == BACKEND_STRATA:
            return self._enhance_strata(
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, seed=seed,
                timeout=timeout, speed_preset=speed_preset, images=images,
                quant_label=strata_quant,
            )
        if backend == BACKEND_NEMOTRON:
            return self._enhance_nemotron(
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, seed=seed,
                timeout=timeout, speed_preset=speed_preset, images=images,
                model_path=nemotron_model,
            )
        if backend == BACKEND_NINFER:
            return self._enhance_ninfer(
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, seed=seed,
                timeout=timeout, speed_preset=speed_preset, images=images,
                model_path=ninfer_model,
            )
        raise ValueError(f"[BSAI_Qwen_Prompt_Enhancer] Unknown backend: {backend!r}")

    # ---------------- 官方PE ----------------
    def _enhance_official(self, clip, prompt_text, pe_mode, system_template, custom_system_prompt,
                          user_requirement,
                          max_tokens, temperature, top_p, top_k, repeat_penalty, min_p,
                          seed, thinking, mtp, speed_preset, images):
        if clip is None:
            raise ValueError(
                "[BSAI_Qwen_Prompt_Enhancer] The Official PE backend needs a `clip` input:\n"
                "Use CLIPLoader to load the official PE model from text_encoders/ (qwen3.5_9b_qwen_image_2.1_pe_*.safetensors), "
                "then wire the CLIP output into this node's `clip` input."
            )
        # 1) 模式判定: auto -> 有图即 I2I
        has_images = images is not None and len(images.shape) > 1 and images.shape[0] > 0
        mode = "T2I"
        if pe_mode != "auto":
            mode = "I2I" if "I2I" in pe_mode else "T2I"
        elif has_images:
            mode = "I2I"

        # 2) system prompt: 自定义优先，否则模板（auto/I2I 且未改模板时自动切官方 I2I 规则）
        DEFAULT_T2I = "Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]"
        DEFAULT_I2I = "Qwen-Image-2.1 官方 PE-I2I 系统规则 [official_i2i]"
        system_prompt = custom_system_prompt.strip() if custom_system_prompt.strip() else None
        template_id = "custom"
        if system_prompt is None:
            if mode == "I2I" and system_template == DEFAULT_T2I:
                system_template = DEFAULT_I2I
            system_prompt, template_id = resolve_template(system_template, "")
            # 【修复 2026-09-23】官方PE 是专用微调模型，无系统规则时输出不可控（乱图/沙土）：
            # 空 system prompt 自动回退对应模式官方规则并警告。
            if not system_prompt.strip():
                print("[BSAI_Qwen_Prompt_Enhancer] 警告: 无模板/空 system prompt 下官方PE 输出不可控，"
                      "已自动回退官方 %s 规则" % ("I2I" if mode == "I2I" else "T2I"))
                system_prompt = load_official_system_prompt(mode)
                template_id = "official_i2i" if mode == "I2I" else "official_t2i"

        # 3) 构造官方 chat 消息（图片 token 前置）
        n_images = int(images.shape[0]) if has_images else 0
        chat = build_official_chat(system_prompt, prompt_text, image_count=n_images, thinking=thinking)

        # 4) tokenize -> generate -> decode
        tokens = clip.tokenize(
            chat, image=images if has_images else None,
            thinking=thinking, min_length=1, prevent_empty_text=True,
        )
        try:
            ids = clip.generate(
                tokens,
                do_sample=True,
                max_length=int(max_tokens),
                temperature=float(temperature),
                top_k=int(top_k),
                top_p=float(top_p),
                min_p=float(min_p),
                repetition_penalty=float(repeat_penalty),
                seed=int(seed),
                mtp=mtp,
            )
        except TypeError:
            # 兼容较老 CLIP.generate 签名
            ids = clip.generate(
                tokens, do_sample=True, max_length=int(max_tokens),
                temperature=float(temperature), top_k=int(top_k), top_p=float(top_p),
                repetition_penalty=float(repeat_penalty), seed=int(seed),
            )
        raw = clip.decode(ids, skip_special_tokens=False)

        return self._finalize(raw, speed_preset, f"后端=官方PE 模式={mode} 模板={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- 本地LLaMA ----------------
    def _enhance_local(self, llm_model_name, mmproj_name, chat_handler, prompt_text, system_template,
                       custom_system_prompt, user_requirement,
                       max_tokens, temperature, top_p, top_k, repeat_penalty,
                       seed, n_ctx, n_gpu_layers, load_mtp, keep_loaded, speed_preset, images,
                       n_cmoe=0, kv_cache_quant="auto (f16, no quant)", use_mmap=True, use_mlock=False,
                       flash_attn="auto", threads=0):
        resolved = _resolve_handler_label(chat_handler)
        if resolved == "__auto__":
            chat_handler = _pick_chat_handler(llm_model_name)
        else:
            chat_handler = resolved
        if mmproj_name == "" and images is not None:
            _m, mmprojs_now = _scan_gguf()
            mmproj_name = _auto_pair_mmproj(llm_model_name, mmprojs_now)
            if not mmproj_name:
                print("[BSAI_Qwen_Prompt_Enhancer] 警告: 接了图片但未选择 mmproj，视觉信息将不被使用")

        system_prompt, template_id = resolve_template(system_template, custom_system_prompt)

        llm, mmproj_actually_active = _load_llm(
            llm_model_name, mmproj_name, chat_handler, n_ctx, n_gpu_layers, load_mtp,
            n_cmoe=int(n_cmoe or 0),
            kv_cache_quant=str(kv_cache_quant).split("(")[0].strip(),
            use_mmap=bool(use_mmap),
            use_mlock=bool(use_mlock),
            flash_attn=str(flash_attn).strip(),
            threads=int(threads or 0),
        )

        user_content = []
        if images is not None and mmproj_actually_active:
            urls = image_tensor_to_data_urls(images)
            for u in urls:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
        elif images is not None and not mmproj_actually_active:
            # mmproj 选了但 handler 初始化失败（已降级为纯文本）
            print("[BSAI_Qwen_Prompt_Enhancer] 提示: 多模态被降级为纯文本，已忽略输入图片，"
                  "仅用文字提示词生成。")
        user_content.append({"type": "text", "text": prompt_text})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        params = {
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "top_k": int(top_k),
            "repeat_penalty": float(repeat_penalty),
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "seed": _normalize_seed(seed),
            "stream": False,
            "stop": ["</s>"],
        }

        # 重置 LLM 状态，避免上一次推理残留影响本次输出（移植自 BSAI_QwenNodes）
        _reset_llm_state(llm)

        try:
            # 使用签名兼容调用，自动适配不同版本 llama-cpp-python 的参数名
            resp = _call_chat_completion(llm, messages=messages, params=params)
        except RuntimeError as e:
            if "Context Shift is explicitly disabled" in str(e):
                current_n_ctx = getattr(llm, "n_ctx", "unknown")
                raise RuntimeError(
                    "Context Shift is disabled by the C++ backend (M-RoPE models do not support a sliding context window).\n"
                    f"Current n_ctx = {current_n_ctx}, which cannot hold the whole conversation.\n"
                    "Increase 'n_ctx (context length)' on the node:\n"
                    "  - text-only: 16384 recommended\n"
                    "  - with images/video: 32768 or higher recommended\n"
                    f"Original error: {e}"
                ) from e
            raise
        except ValueError as e:
            if "Media evaluation failed" in str(e):
                raise RuntimeError(
                    "Multimodal image encoding failed (Media evaluation failed).\n"
                    "Possible causes and fixes:\n"
                    "1. Input image resolution too large — try fewer input images, or downscale them.\n"
                    "2. The mmproj vision projector does not match the main model — make sure you load the matching mmproj.\n"
                    "   e.g. a Qwen3.8-VL main model must use the Qwen3.8-VL mmproj.\n"
                    "3. Out of VRAM during CLIP encoding — try fewer input images, or restart ComfyUI.\n"
                    "4. The image file is corrupted or malformed — check it opens normally.\n"
                    f"Original error: {e}"
                ) from e
            # 采样参数不兼容时降级重试
            print(f"[BSAI_Qwen_Prompt_Enhancer] 首次调用失败({e})，降级采样参数重试…")
            resp = llm.create_chat_completion(
                messages=messages, max_tokens=int(max_tokens),
                temperature=float(temperature), top_p=float(top_p),
            )
        except Exception as e:
            # 其他错误（如参数不兼容）降级重试
            print(f"[BSAI_Qwen_Prompt_Enhancer] 首次调用失败({e})，降级采样参数重试…")
            resp = llm.create_chat_completion(
                messages=messages, max_tokens=int(max_tokens),
                temperature=float(temperature), top_p=float(top_p),
            )

        raw = resp["choices"][0]["message"].get("content") or ""
        # 兼容 thinking 输出（reasoning_content）
        if not raw:
            raw = resp["choices"][0]["message"].get("reasoning_content") or ""

        # 结果清理（与 G 盘 BSAI_QwenNodes 对齐：去除前缀冒号等）
        raw = raw.lstrip().removeprefix(": ").strip()

        # 【修复 2026-09-23】keep_loaded=false：LLM 用完后再卸载。
        # 之前"加载完立即 _clear_cache"会把刚拿到/命中的 llm close 掉，
        # 导致后续 create_chat_completion 报 Invalid chat handler: None。
        if not keep_loaded:
            _clear_cache()

        return self._finalize(raw, speed_preset, f"后端=本地LLaMA 模板={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- 本地HF (Transformers) ----------------
    def _enhance_hf(self, hf_model_name, hf_task, hf_device, hf_keep_loaded,
                    prompt_text, system_template, custom_system_prompt, user_requirement,
                    max_tokens,
                    temperature, top_p, top_k, seed, speed_preset, images):
        if not hf_model_name or hf_model_name.startswith("<No "):
            raise ValueError("[BSAI_Qwen_Prompt_Enhancer] The Local HF backend requires a HuggingFace model under models/LLM (safetensors/bin)")

        model_dir_id = _hf_model_id_from_label(hf_model_name)
        # 设备选择
        import torch
        if hf_device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = hf_device

        entry = _load_hf(model_dir_id, device)
        if not hf_keep_loaded:
            _clear_hf_cache()

        system_prompt, template_id = resolve_template(system_template, custom_system_prompt)

        if entry["kind"] == "florence2":
            # 视觉 caption / prompt 反推（Florence-2 / PromptGen）
            raw = _run_florence2(entry, images, hf_task, max_tokens, temperature, top_p, device)
            tag = f"后端=本地HF(视觉) 模型={model_dir_id} 任务={hf_task}"
        else:
            # 文本 causal LLM（Llama/Gemma/Qwen 等）
            raw = _run_causal_hf(entry, system_prompt, prompt_text, max_tokens,
                                 temperature, top_p, top_k, device)
            tag = f"后端=本地HF(文本) 模型={model_dir_id} 模板={template_id}"

        return self._finalize(raw, speed_preset, tag,
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- API ----------------
    def _enhance_api(self, api_base, api_key, api_model_name, prompt_text, system_template,
                     custom_system_prompt, user_requirement,
                     max_tokens, temperature, top_p, top_k, seed,
                     timeout, speed_preset, images):
        if not api_base.strip():
            raise ValueError("[BSAI_Qwen_Prompt_Enhancer] The API backend requires api_base (OpenAI-compatible endpoint URL)")

        system_prompt, template_id = resolve_template(system_template, custom_system_prompt)

        user_content = []
        if images is not None:
            urls = image_tensor_to_data_urls(images)
            for u in urls:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
        user_content.append({"type": "text", "text": prompt_text})

        payload = {
            "model": api_model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "top_p": float(top_p),
            "top_k": int(top_k),
            "seed": int(seed),
        }
        headers = {"Content-Type": "application/json"}
        if api_key.strip():
            headers["Authorization"] = "Bearer " + api_key.strip()

        url = api_base.rstrip("/") + "/chat/completions"
        try:
            data = _api_request(url, payload, headers, timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            if e.code == 400:
                # 部分服务端不认 top_k/seed 等扩展采样参数，降级为最小 payload 重试一次
                minimal = {k: payload[k] for k in ("model", "messages", "temperature", "max_tokens")}
                print(f"[BSAI_Qwen_Prompt_Enhancer] API 400({body[:200]})，用最小 payload 重试…")
                try:
                    data = _api_request(url, minimal, headers, timeout)
                except urllib.error.HTTPError as e2:
                    body2 = e2.read().decode("utf-8", errors="replace")[:500]
                    raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] API HTTP {e2.code}: {body2}")
            else:
                raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] API HTTP {e.code}: {body}")
        except Exception as e:
            raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] API call failed: {e}")

        msg = data["choices"][0]["message"]
        raw = msg.get("content") or ""
        if not raw and msg.get("reasoning_content"):
            raw = msg["reasoning_content"]

        return self._finalize(raw, speed_preset, f"后端=API 模板={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- BSAI Strata ----------------
    def _enhance_strata(self, prompt_text, system_template, custom_system_prompt,
                        user_requirement, max_tokens, temperature, top_p, seed,
                        timeout, speed_preset, images, quant_label="Auto (auto-adapt)"):
        """Call local Strata (Qwen3.8-Flash-Next @ 127.0.0.1:8080) via blocking socket."""
        import json as _json, socket as _sk, http.client as _hc
        import sys as _sys
        # Auto-start Strata if not running (reuse StrataManager from BSAI-LLM-Strata)
        try:
            _sp = None
            for mod_name, mod in list(_sys.modules.items()):
                if mod_name.endswith("strata_manager") and hasattr(mod, "StrataManager"):
                    _sp = mod.StrataManager
                    break
            if _sp is None:
                # Load directly from plugin path
                import importlib.util as _ilu
                _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "BSAI-LLM-Strata", "strata_manager.py")
                if os.path.exists(_p):
                    _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
                    _m = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_m)
                    _sp = _m.StrataManager
            if _sp is not None:
                ok, msg = _sp.ensure_running(quant_label=quant_label)
                print(f"[BSAI_Qwen_Prompt_Enhancer] Strata 自动启动 ({quant_label}): {ok} ({msg})")
                if not ok:
                    raise RuntimeError(
                        f"[BSAI_Qwen_Prompt_Enhancer] Failed to start the Strata server: {msg}\n"
                        f"Please check that Strata is installed completely, or switch to another backend (llama.cpp / HF / API)."
                    )
        except Exception as _e:
            print(f"[BSAI_Qwen_Prompt_Enhancer] Strata 自动启动跳过: {_e}")

        system_prompt, template_id = resolve_template(system_template, custom_system_prompt)

        user_content = []
        if images is not None:
            urls = image_tensor_to_data_urls(images)
            for u in urls:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
        user_content.append({"type": "text", "text": prompt_text})

        payload = {
            "model": "qwen3.8-flash-next",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "top_p": float(top_p),
            "seed": int(seed),
        }
        body = _json.dumps(payload).encode("utf-8")
        
        # Retry loop: wait for model to be fully loaded (IQ3_S takes time)
        data = None
        for attempt in range(30):
            s = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
            s.settimeout(float(timeout) if timeout else 600.0)
            s.setblocking(True)
            try:
                s.connect(("127.0.0.1", 8080))
                conn = _hc.HTTPConnection("127.0.0.1", 8080, timeout=s.gettimeout())
                conn.sock = s
                conn.request("POST", "/v1/chat/completions", body=body,
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer strata"})
                resp = conn.getresponse()
                data = _json.loads(resp.read().decode("utf-8", "replace"))
                
                # Check if we got a valid response
                if "choices" in data and data["choices"]:
                    break
                else:
                    print(f"[BSAI Enhancer] Model still loading, retry {attempt+1}/30...")
                    time.sleep(5)
            except Exception as e:
                print(f"[BSAI Enhancer] Waiting for model to start, retry {attempt+1}/30: {e}")
                time.sleep(5)
            finally:
                s.close()
        
        if not data or "choices" not in data:
            raise RuntimeError("Strata model not ready after waiting. Please wait a bit longer and try again.")
        
        msg = data["choices"][0]["message"]
        raw = msg.get("content") or ""
        if not raw and msg.get("reasoning_content"):
            raw = msg["reasoning_content"]

        return self._finalize(raw, speed_preset, f"后端=BSAI Strata 模板={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- BSAI Nemotron (llama.cpp) ----------------
    def _enhance_nemotron(self, prompt_text, system_template, custom_system_prompt,
                          user_requirement, max_tokens, temperature, top_p, seed,
                          timeout, speed_preset, images, model_path="(Auto — first model found)"):
        """Call local Nemotron 3.5 Bolt (llama.cpp @ 127.0.0.1:8085) via NemotronManager."""
        import json as _json, socket as _sk, http.client as _hc
        import sys as _sys
        # Auto-start Nemotron if not running (reuse NemotronManager from BSAI-LLM-Strata)
        try:
            _nm = None
            for mod_name, mod in list(_sys.modules.items()):
                if mod_name.endswith("strata_manager") and hasattr(mod, "NemotronManager"):
                    _nm = mod.NemotronManager
                    break
            if _nm is None:
                import importlib.util as _ilu
                _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "BSAI-LLM-Strata", "strata_manager.py")
                if os.path.exists(_p):
                    _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
                    _m = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_m)
                    _nm = _m.NemotronManager
            if _nm is not None:
                _mp = None if str(model_path).startswith("(Auto") else str(model_path)
                ok, msg = _nm.ensure_running(model_path=_mp)
                print(f"[BSAI_Qwen_Prompt_Enhancer] Nemotron 自动启动: {ok} ({msg})")
                if not ok:
                    raise RuntimeError(
                        f"[BSAI_Qwen_Prompt_Enhancer] Failed to start the Nemotron server: {msg}\n"
                        f"请确认 llama.cpp 已放入 BSAI-LLM-Strata/Nemotron/llama.cpp/，"
                        f"且模型已下载到 models/LLM/Nemotron/。"
                    )
        except Exception as _e:
            print(f"[BSAI_Qwen_Prompt_Enhancer] Nemotron 自动启动跳过: {_e}")

        system_prompt, template_id = resolve_template(system_template, custom_system_prompt)

        user_content = []
        if images is not None:
            urls = image_tensor_to_data_urls(images)
            for u in urls:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
        user_content.append({"type": "text", "text": prompt_text})

        payload = {
            "model": "Nemotron-3.5-Bolt-74B-A9B",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "top_p": float(top_p),
            "seed": int(seed),
        }
        body = _json.dumps(payload).encode("utf-8")

        # Retry loop: wait for model to be fully loaded
        data = None
        for attempt in range(30):
            s = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
            s.settimeout(float(timeout) if timeout else 600.0)
            s.setblocking(True)
            try:
                s.connect(("127.0.0.1", 8085))
                conn = _hc.HTTPConnection("127.0.0.1", 8085, timeout=s.gettimeout())
                conn.sock = s
                conn.request("POST", "/v1/chat/completions", body=body,
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer strata"})
                resp = conn.getresponse()
                data = _json.loads(resp.read().decode("utf-8", "replace"))
                if "choices" in data and data["choices"]:
                    break
                else:
                    print(f"[BSAI Enhancer] Nemotron still loading, retry {attempt+1}/30...")
                    time.sleep(5)
            except Exception as e:
                print(f"[BSAI Enhancer] Waiting for Nemotron to start, retry {attempt+1}/30: {e}")
                time.sleep(5)
            finally:
                s.close()

        if not data or "choices" not in data:
            raise RuntimeError("Nemotron model not ready after waiting. Please wait a bit longer and try again.")

        msg = data["choices"][0]["message"]
        raw = msg.get("content") or ""
        if not raw and msg.get("reasoning_content"):
            raw = msg["reasoning_content"]

        return self._finalize(raw, speed_preset, f"后端=BSAI Nemotron 模板={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- BSAI NInfer ----------------
    def _enhance_ninfer(self, prompt_text, system_template, custom_system_prompt,
                        user_requirement, max_tokens, temperature, top_p, seed,
                        timeout, speed_preset, images, model_path="(Auto — first model found)"):
        """Call local NInfer (AI蛮子 ninfer engine, dynamic port via NInferManager)."""
        import json as _json, socket as _sk, http.client as _hc
        from urllib.parse import urlparse as _up
        import sys as _sys

        # Auto-start NInfer if not running (reuse NInferManager from BSAI-LLM-Strata)
        _nm = None
        for mod_name, mod in list(_sys.modules.items()):
            if mod_name.endswith("strata_manager") and hasattr(mod, "NInferManager"):
                _nm = mod.NInferManager
                break
        if _nm is None:
            import importlib.util as _ilu
            _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "BSAI-LLM-Strata", "strata_manager.py")
            if not os.path.exists(_p):
                raise RuntimeError("[BSAI_Qwen_Prompt_Enhancer] BSAI-LLM-Strata 插件缺失，无法启动 NInfer")
            _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
            _m = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
            _nm = _m.NInferManager
        _model_path = None if str(model_path).startswith("(Auto") else str(model_path)
        ok, msg = _nm.ensure_running(model_path=_model_path)
        print(f"[BSAI_Qwen_Prompt_Enhancer] NInfer 自动启动: {ok} ({msg})")
        if not ok:
            raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] Failed to start the NInfer engine: {msg}\n"
                               f"请确认 BSAI-FLUX3-ComfyUI/engine/ 完整、models/LLM 下有 .ninfer 模型。")

        system_prompt, template_id = resolve_template(system_template, custom_system_prompt)

        user_content = []
        if images is not None:
            urls = image_tensor_to_data_urls(images)
            for u in urls:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
        user_content.append({"type": "text", "text": prompt_text})

        payload = {
            "model": "default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "top_p": float(top_p),
            "seed": int(seed),
        }
        mids = _nm.models()
        if mids:
            payload["model"] = mids[0]
        body = _json.dumps(payload).encode("utf-8")
        u = _up(_nm.base_url())

        data = None
        for attempt in range(30):
            s = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
            s.settimeout(float(timeout) if timeout else 600.0)
            s.setblocking(True)
            try:
                s.connect((u.hostname, u.port or 80))
                conn = _hc.HTTPConnection(u.hostname, u.port or 80, timeout=s.gettimeout())
                conn.sock = s
                conn.request("POST", u.path + "/chat/completions", body=body,
                             headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                data = _json.loads(resp.read().decode("utf-8", "replace"))
                if "choices" in data and data["choices"]:
                    break
                else:
                    print(f"[BSAI Enhancer] Model still loading, retry {attempt+1}/30...")
                    time.sleep(5)
            except Exception as e:
                print(f"[BSAI Enhancer] Waiting for model to start, retry {attempt+1}/30: {e}")
                time.sleep(5)
            finally:
                s.close()

        if not data or "choices" not in data:
            raise RuntimeError("NInfer model not ready after waiting. Please wait a bit longer and try again.")

        msg = data["choices"][0]["message"]
        raw = msg.get("content") or ""
        if not raw and msg.get("reasoning_content"):
            raw = msg["reasoning_content"]

        return self._finalize(raw, speed_preset, f"后端=BSAI NInfer 模板={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- 统一收尾 ----------------
    def _finalize(self, raw, speed_preset, tag,
                  system_template=None, custom_system_prompt="", user_requirement=""):
        enhanced, wh_ratio, ratio_follow, raw, thinking_text = get_enhanced_result(raw)
        steps, cfg, sampler, scheduler, *extra = self._SPEED_PRESETS.get(speed_preset, self._SPEED_PRESETS[_DEFAULT_SPEED])

        # 【v2】MERGED_TEXT = (解析后的 system prompt) + user_requirement 拼接
        # 仅用作「下游 Show Text / 提前预览 / 直接接 KSampler」的合并版文本，
        # 不进入 LLM 内部对话；空 user_requirement 时与 SYSTEM_PROMPT 等价。
        try:
            resolved_system_prompt, _tid = resolve_template(
                system_template or "Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]",
                custom_system_prompt,
            )
        except Exception as _e:
            resolved_system_prompt = ""
            print(f"[BSAI_Qwen_Prompt_Enhancer] 解析模板失败: {_e}")
        merged_text = self._build_merged_text(resolved_system_prompt, user_requirement)

        print(f"[BSAI_Qwen_Prompt_Enhancer] {tag} wh_ratio={wh_ratio} "
              f"| 加速档={speed_preset} → steps={steps} cfg={cfg} sampler={sampler} scheduler={scheduler}")
        hint_line = f"\n⚠ 该档为蒸馏LoRA档：{extra[0]}" if extra else ""
        ui_text = [
            enhanced,
            f"\n── 加速采样建议 ──\n档位: {speed_preset}\n"
            f"KSampler → steps={steps}, cfg={cfg}, sampler={sampler}, scheduler={scheduler}\n"
            f"接线: KSampler 右键 steps/cfg → Convert to input，接入 RECOMMENDED_* 端口\n"
            f"{hint_line}"
            f"\n── Qwen Image 2.1 Acceleration Tips ──\n"
            f"1. cfg=1.0 is correct (2.1 is CFG-distilled architecture; negative prompts have no effect at cfg=1)\n"
            f"2. Official int8 model: qwen_image_2.1_int8_convrot.safetensors (halves VRAM usage)\n"
            f"3. Edit workflow: add a 'Qwen Image 2.1 Cache' node (device=auto, dtype=int8) to reuse prefix KV\n"
            f"4. General speedup: model -> EasyCache node -> KSampler (built-in, ~1.2-1.5x)\n"
            f"5. Attention acceleration: add --use-sage-attention to launch args (20-40% faster sampling)\n"
            f"6. Distilled LoRAs (released 2026-09~10): Viggle Turbo 6-step official node / Pruna 5-8 steps (community) / Alibaba PAI Fun-Acc 4 steps (experimental),"
            f"all require fixed sigma; see ACCELERATION_GUIDE.md for details\n"
            f"7. lightx2v 2.1-specific Lightning LoRA not yet released (do not select Lightning preset); do not use TeaCache (frozen, incompatible with 2.1);"
            f"do not use old 20B Lightning LoRA (different architecture)",
            f"\n── Merged text preview (MERGED_TEXT output) ──\n{merged_text}",
        ]
        return {"ui": {"text": ui_text, "merged_text": [merged_text]},
                "result": (enhanced, wh_ratio, ratio_follow, raw, thinking_text,
                           int(steps), float(cfg), sampler, scheduler, merged_text)}

    @staticmethod
    def _build_preview_merged(system_template, custom_system_prompt, user_requirement):
        """纯预览模式：解析模板 + 拼用户要求。不调用任何模型。
        与 _finalize 内的逻辑同源；用于海报墙选模板时让下游立即拿到 MERGED_TEXT。
        """
        # 与 _enhance_official 完全一致的解析优先级
        csp = (custom_system_prompt or "").strip()
        if csp:
            resolved = csp
        else:
            try:
                resolved, _ = resolve_template(
                    system_template or "Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]",
                    "",
                )
            except Exception as e:
                print(f"[BSAI_Qwen_Prompt_Enhancer] 预览模式解析模板失败: {e}")
                resolved = ""
        print(f"[BSAI_Qwen_Prompt_Enhancer] [preview-build] csp_len={len(csp)} resolved_head={resolved[:60]!r}")
        return BSAI_Qwen_Prompt_Enhancer._build_merged_text(resolved, user_requirement)

    @staticmethod
    def _build_merged_text(template_text, user_requirement):
        """模板原文 + 用户要求拼接（与模板节点 QwenImage21_Prompt_Template 同源逻辑）
        - 空 user_requirement: merged_text == template_text（不破坏现有工作流）
        - 非空: 在尾部追加「【用户要求】\n<要求>\n（请务必在生成时满足以上用户要求。）」
        """
        if not template_text:
            template_text = ""
        if not user_requirement or not str(user_requirement).strip():
            return template_text
        body = str(user_requirement).strip()
        return (
            template_text.rstrip()
            + "\n\n【用户要求】\n"
            + "用户对当前任务的额外要求：\n"
            + body
            + "\n（请务必在生成时满足以上用户要求。）"
        )


def _api_request(url, payload, headers, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=int(timeout)) as resp:
        return json.loads(resp.read().decode("utf-8"))


class BSAI_Qwen_Image21_Sampler:
    """
    BSAI Qwen image 2.1 采样器 — KSampler 参数 + 可选 guider / sigmas 输入端口。

    · 保留 KSampler 全部参数：seed / steps / cfg / sampler_name / scheduler / denoise
    · 新增可选输入端口：
        guider (GUIDER)  — 直连 BasicGuider / CFGGuider 等上游节点；不接时内置 CFGGuider(model, positive, negative, cfg)
        sigmas (SIGMAS)  — 直连 ViggleTurboSigmas / ManualSigmas 等上游节点；不接时按 scheduler+steps+denoise 生成
    · 语义对齐：
        - 接 sigmas 时以 sigmas 为准（如 Viggle Turbo 固定 6 步 sigma），steps 参数仅作 UI 显示
        - 接 guider 时 cfg 参数被 guider 内部配置覆盖（BasicGuider 无 CFG）
        - 未接 guider/sigmas 时行为与 KSampler 完全一致（含 denoise 截断）
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (_BSAI_SAMPLER_NAMES, {"default": "euler"}),
                "scheduler": (_BSAI_SCHEDULER_NAMES, {"default": "simple"}),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "guider": ("GUIDER",),
                "sigmas": ("SIGMAS",),
            },
        }

    RETURN_TYPES = ("LATENT", "LATENT")
    RETURN_NAMES = ("LATENT", "denoised_output")
    FUNCTION = "sample"
    CATEGORY = "sampling/custom_sampling"

    DESCRIPTION = (
        "BSAI Qwen image 2.1 sampler: all KSampler parameters (seed/steps/CFG/sampler/scheduler/denoise) are kept as widgets, "
        "and each can be right-clicked 'Convert widget to input' to wire an upstream node (e.g. the enhancer's RECOMMENDED_STEPS/CFG). "
        "Adds optional guider / sigmas input ports to wire distilled-sampling upstreams such as BasicGuider / ViggleTurboSigmas directly.\n"
        "Steps rule: steps always wins — external sigmas only apply when their step count matches steps; "
        "when they mismatch, external sigmas are ignored and regenerated from steps (for a distilled LoRA keep steps equal to the LoRA/sigma sequence length)."
    )

    def sample(self, model, positive, negative, latent_image,
               seed=0, steps=20, cfg=1.0, sampler_name="euler", scheduler="simple",
               denoise=1.0, guider=None, sigmas=None):
        if _comfy_samplers is None:
            raise RuntimeError("[BSAI_Qwen_Image21_Sampler] ComfyUI sampling module is unavailable")
        # 1) guider：优先外部 guider（BasicGuider / CFGGuider），否则内置 CFGGuider
        if guider is None:
            guider = _comfy_samplers.CFGGuider(model)
            guider.set_conds(positive, negative)
            guider.set_cfg(cfg)
        # 2) sigmas：steps 为主控。外部 sigmas（ViggleTurboSigmas / ManualSigmas）仅在
        #    其步数与 steps 一致时生效；不一致时视为用户主动改步数，按 scheduler+steps+denoise
        #    重新生成并提示（保证「改 steps 必生效」）。
        if sigmas is not None:
            sigma_steps = int(sigmas.shape[-1]) - 1
            if sigma_steps != int(steps):
                print(
                    f"[BSAI_Qwen_Image21_Sampler] Warning: steps={int(steps)} does not match the external sigmas step count "
                    f"({sigma_steps}); external sigmas ignored and regenerated from steps. "
                    f"For a distilled LoRA keep steps equal to the LoRA/sigma sequence length, otherwise quality is not guaranteed."
                )
                sigmas = None
        if sigmas is None:
            if denoise is None or denoise > 0.9999:
                sigmas = _comfy_samplers.calculate_sigmas(
                    model.get_model_object("model_sampling"), scheduler, steps).cpu()
            else:
                new_steps = int(steps // denoise) if denoise > 0.0 else steps
                sigmas = _comfy_samplers.calculate_sigmas(
                    model.get_model_object("model_sampling"), scheduler, new_steps).cpu()
                sigmas = sigmas[-(steps + 1):]
        # 3) 采样器
        sampler = _comfy_samplers.sampler_object(sampler_name)

        # 4) 采样主循环（与官方 SamplerCustomAdvanced 一致）
        latent = latent_image
        latent_image_t = latent["samples"]
        latent = latent.copy()
        latent_image_t = _comfy_sample.fix_empty_latent_channels(
            guider.model_patcher, latent_image_t,
            latent.get("downscale_ratio_spacial", None),
            latent.get("downscale_ratio_temporal", None))
        latent["samples"] = latent_image_t

        noise_mask = latent.get("noise_mask")
        x0_output = {}
        callback = _latent_preview.prepare_callback(
            guider.model_patcher, sigmas.shape[-1] - 1, x0_output)
        disable_pbar = not _comfy_utils.PROGRESS_BAR_ENABLED
        samples = guider.sample(
            _BSAI_RandomNoise(seed).generate_noise(latent),
            latent_image_t, sampler, sigmas,
            denoise_mask=noise_mask, callback=callback,
            disable_pbar=disable_pbar, seed=seed)
        samples = samples.to(mm.intermediate_device())

        out = latent.copy()
        out.pop("downscale_ratio_spacial", None)
        out.pop("downscale_ratio_temporal", None)
        out["samples"] = samples
        if "x0" in x0_output:
            x0 = x0_output["x0"]
            if samples.is_nested and not x0.is_nested:
                latent_shapes = [x.shape for x in samples.unbind()]
                x0 = _comfy_nested_tensor.NestedTensor(_comfy_utils.unpack_latents(x0, latent_shapes))
            x0_out = guider.model_patcher.model.process_latent_out(x0.cpu())
            out_denoised = latent.copy()
            out_denoised["samples"] = x0_out
        else:
            out_denoised = out
        return out, out_denoised


class _BSAI_RandomNoise:
    """与官方 Noise_RandomNoise 等价的最小噪声实现（避免跨模块导入）"""

    def __init__(self, seed):
        self.seed = seed

    def generate_noise(self, input_latent):
        latent_image = input_latent["samples"]
        batch_inds = input_latent.get("batch_index")
        return _comfy_sample.prepare_noise(latent_image, self.seed, batch_inds)


# 供 __init__.py 注册
NODE_CLASS_MAPPINGS = {
    "BSAI_Qwen_Prompt_Enhancer": BSAI_Qwen_Prompt_Enhancer,
    "BSAI_Qwen_Image21_Sampler": BSAI_Qwen_Image21_Sampler,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Qwen_Prompt_Enhancer": "BSAI Qwen Prompt Enhancer",
    "BSAI_Qwen_Image21_Sampler": "BSAI Qwen image 2.1 Sampler",
}
