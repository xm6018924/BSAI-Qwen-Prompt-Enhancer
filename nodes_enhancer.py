# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer 鈥?鍥涘悎涓€澧炲己閫氶亾鑺傜偣
鑺傜偣: BSAI_Qwen_Prompt_Enhancer

涓€涓妭鐐广€佸洓绉嶅寮哄悗绔紝鐢?backend 涓嬫媺涓€閿垏鎹細
  1. 瀹樻柟PE (鏈湴 Qwen3.5-9B)  鈥?CLIPLoader 鍔犺浇瀹樻柟 PE 妯″瀷锛宑lip.tokenize/generate/decode
     锛堜笌 ComfyUI 0.37 瀹樻柟 TextGenerate 鍚屼竴浣撶郴锛屽畼鏂?chat_template.jinja 鏋勯€犳秷鎭級
  2. 鏈湴LLaMA (GGUF+mmproj)   鈥?llama.cpp 鍔犺浇鏈湴瑙嗚澶фā鍨嬶紝create_chat_completion
     锛堣嚜鍔ㄦ壂鎻?models/LLM 涓?models/text_encoders 涓嬬殑 *.gguf锛岃嚜鍔ㄩ厤瀵?mmproj锛岃嚜鍔ㄨ瘑鍒?chat_handler锛?
     [绉绘鑷?G 鐩?BSAI_QwenNodes] MTP 灞傝嚜鍔ㄦ娴嬩笌鍓ョ / LLM 鐘舵€侀噸缃?/ 绛惧悕鍏煎璋冪敤
  3. 鏈湴HF (Transformers)      鈥?鍔犺浇 models/LLM 涓?HuggingFace safetensors 妯″瀷锛團lorence-2 / Llama 绛夛級
  4. API (OpenAI鍏煎)          鈥?鍦ㄧ嚎/鏈湴 OpenAI 鍏煎 Chat Completions 鎺ュ彛

鍙傛暟鍒嗗眰锛堝墠绔?JS 鎸?backend 鑷姩鏄鹃殣鍚庣涓撳睘 widget锛夛細
  路 鍏叡鍙傛暟锛堝洓鍚庣鍏辩敤锛夛細prompt_text / system_template / custom_system_prompt /
    temperature / top_p / top_k / repeat_penalty / seed / max_tokens / speed_preset / image_1~16
  路 瀹樻柟PE 涓撳睘锛歝lip(杈撳叆) / pe_mode / min_p / thinking / mtp
  路 鏈湴LLaMA 涓撳睘锛歭lm_model_name / mmproj_name / chat_handler / n_ctx / n_gpu_layers / load_mtp / keep_loaded
  路 鏈湴HF 涓撳睘锛歨f_model_name / hf_task / hf_device / hf_keep_loaded
  路 API 涓撳睘锛歛pi_base / api_key / api_model_name / timeout

杈撳嚭缁熶竴 10 璺紙鍥涗釜鍚庣涓€鑷达級锛?
  ENHANCED_PROMPT / WH_RATIO / RATIO_FOLLOW / RAW_OUTPUT / THINKING /
  RECOMMENDED_STEPS / RECOMMENDED_CFG / RECOMMENDED_SAMPLER / RECOMMENDED_SCHEDULER /
  MERGED_TEXT

妯″瀷鐩綍锛堢浉瀵硅矾寰勶級锛欳omfyUI/models/LLM  鈥? 鏀剧疆鎵€鏈?GGUF / HF 妯″瀷鏂囦欢
"""
import gc
import inspect
import json
import os
import re
import struct as _struct
import urllib.request

import folder_paths

try:
    import comfy.model_management as mm
except Exception:
    mm = None

# BSAI Qwen image 2.1 閲囨牱鍣ㄤ緷璧栵紙鑰佸紡鑺傜偣锛屽弬鐓у畼鏂?SamplerCustomAdvanced / KSampler 璇箟锛?
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

# llama-cpp-python锛堟湰鍦?GGUF 妯″瀷鎺ㄧ悊锛夛紝鏈畨瑁呮椂涓嶅奖鍝嶅叾浠栧悗绔?
try:
    from llama_cpp import Llama
except Exception:
    Llama = None

# 涓撶敤 chat handler锛堜笌 BSAI_ComfyUI_Nodes 瀵归綈锛屼紭鍏堢敤涓撶敤 handler 鑰岄潪 MTMDChatHandler锛?
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

# ---- 鍚庣閫夐」锛堝墠绔?JS 鎸夎繖浜涙爣绛剧簿纭尮閰嶆樉闅愬垎缁勶紝鍕块殢鎰忔敼鍚嶏級----
BACKEND_PE = "瀹樻柟PE (鏈湴 Qwen3.5-9B)"
BACKEND_LLAMA = "鏈湴LLaMA (GGUF+mmproj)"
BACKEND_HF = "鏈湴HF (Transformers)"
BACKEND_API = "API (OpenAI鍏煎)"
BACKEND_STRATA = "BSAI Strata (Qwen3.8-Flash-Next @127.0.0.1:8080)"
BACKEND_LABELS = [BACKEND_PE, BACKEND_LLAMA, BACKEND_HF, BACKEND_API, BACKEND_STRATA]

_DEFAULT_SPEED = "瀹樻柟鏍囧噯 25姝?CFG1 (鎺ㄨ崘)"


# ============================================================
# 鏈湴 LLaMA 閫氶亾杈呭姪锛堟壂鎻?閰嶅/鍔犺浇锛岄€昏緫涓庡師 nodes_local_llama.py 涓€鑷达級
# ============================================================
def _scan_gguf():
    """閫掑綊鎵弿鏈湴 GGUF锛坢odel 涓?mmproj锛夛紝杩斿洖 ([model 鍒楄〃], [mmproj 鍒楄〃])
    閫掑綊鎵€鏈夊瓙鐩綍锛屾枃浠跺悕甯︾浉瀵瑰瓙璺緞锛屼究浜庡尯鍒嗗悓鍚嶆ā鍨嬨€?
    妯″瀷鐩綍锛欳omfyUI/models/LLM 涓?ComfyUI/models/text_encoders锛堢浉瀵硅矾寰勶級銆?""
    # 纭繚 LLM 鏂囦欢澶瑰湪 folder_paths 涓敞鍐岋紙涓?G 鐩?BSAI_QwenNodes 瀵归綈锛?
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
    # 鍏滃簳锛氬缁堝姞鍏?models/LLM 涓?models/text_encoders锛堢浉瀵?ComfyUI 鏍圭洰褰曪級
    dirs.append(os.path.join(folder_paths.models_dir, "LLM"))
    dirs.append(os.path.join(folder_paths.models_dir, "text_encoders"))
    seen = set()
    for d in dirs:
        if not os.path.isdir(d):
            continue
        # 閫掑綊閬嶅巻鎵€鏈夊瓙鐩綍
        for root, _subdirs, files in os.walk(d):
            for f in sorted(files):
                if not f.lower().endswith(".gguf"):
                    continue
                # 鐢ㄧ浉瀵硅矾寰勫仛鍘婚噸閿紙涓嶅悓瀛愮洰褰曞悓鍚嶆枃浠惰涓轰笉鍚岋級
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
    """鎸夊悕绉板墠缂€鑷姩閰嶅 mmproj"""
    stem = os.path.splitext(model_name)[0].lower()
    # 灏濊瘯: 鍘绘帀鐗堟湰/閲忓寲鍚庣紑鍚庢寜鍓嶇紑鍖归厤
    for m in mmprojs:
        mstem = os.path.splitext(m)[0].lower()
        common = os.path.commonprefix([stem, mstem])
        if len(common) >= 8:
            return m
    # 鍏滃簳: 棣栧瓧姣嶇郴鍒楀尮閰?
    for m in mmprojs:
        if model_name[:10].lower() in m.lower() or m[:10].lower() in model_name.lower():
            return m
    return ""


def _pick_chat_handler(model_name):
    """鏍规嵁妯″瀷鍚嶈嚜鍔ㄩ€夋嫨 llama.cpp chat handler 绫诲悕銆?
    杩斿洖鐨勪紭鍏堟槸 llama-cpp-python 褰撳墠鐗堟湰閲?*纭疄瀛樺湪**鐨?handler锛?
    濡傛灉妯″瀷瀵瑰簲鐨勬柊鐗?handler锛堝 Qwen35/GLM46V/LFM25VL/Step3VL锛夊湪浣犺鐨?
    llama-cpp-python 閲屾病鏈夛紝鑷姩闄嶇骇鍒?MTMDChatHandler锛坙lama.cpp 0.3.x
    瀹樻柟鎺ㄨ崘鐨?GGUF + mtmd 鎶曞奖鍣?閫氱敤鏂规锛孮wen3.5+/Gemma4/GLM/Step 绛?
    甯?mtmd-mmproj 鐨勬ā鍨嬮兘鑳界敤锛夈€傚疄鍦ㄦ病娉曡瘑鍒椂杩斿洖绌轰覆锛岀敱璋冪敤鏂规姤閿欍€?""
    n = model_name.lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
    # ----- 绗竴浼樺厛绾э細鏈増鏈?llama-cpp-python 閲岀湡瀹炲瓨鍦ㄧ殑涓撶敤 handler -----
    if "qwen2vl" in n or "qwen25vl" in n or "qwen2.5vl" in n:
        return "Qwen25VLChatHandler"
    if "gemma4" in n:
        return "Gemma4ChatHandler"
    if "gemma3" in n:
        return "Gemma3ChatHandler"
    if "minicpmv45" in n or "minicpm45" in n or "minicpmv26" in n or "minicpm26" in n:
        # 浼樺厛 v4.5锛堣嫢 llama-cpp-python 宸插悎鍏ワ級锛屽惁鍒?v2.6
        return "MiniCPMv45ChatHandler" if "45" in n else "MiniCPMv26ChatHandler"

    # ----- 绗簩浼樺厛绾э細妯″瀷瀹舵棌鍚?鈫?鏈熸湜鐨?handler 绫诲悕 -----
    # 杩欎簺 handler 鍦ㄦ柊鐗?llama-cpp-python锛堚墺0.3.36/nightly锛夋墠瀛樺湪锛?
    # 0.3.35锛圥yPI 褰撳墠鏈€鏂帮級閲屾病鏈夛紝鎵€浠ヤ笅闈㈢敤 _resolve_handler_cls() 鑷姩闄嶇骇
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

    # ----- 绗笁浼樺厛绾э細鍏滃簳 mtmd锛堝甫 mmproj-BF16 鐨勬ā鍨嬪熀鏈兘鏄?mtmd 鎶曞奖锛?-----
    return "MTMDChatHandler"


def _resolve_handler_cls(preferred_name):
    """鎶婃湡鏈涚殑 handler 绫诲悕瑙ｆ瀽鎴?*褰撳墠 llama-cpp-python 閲岀湡瀹炲彲鐢?*鐨勭被銆?
    椤哄簭锛歱referred锛堣嫢瀛樺湪锛夆啋 MTMDChatHandler锛堣嫢瀛樺湪锛夆啋 None銆?
    杩斿洖 None 鏃朵笂灞傛姤閿欙紝骞堕檮涓婂綋鍓嶅彲鐢?handler 娓呭崟渚夸簬鎺掗敊銆?""
    # 1) 棣栭€変笓鐢?handler
    cls = _get_handler_cls(preferred_name)
    if cls is not None:
        return cls
    # 2) mtmd 閫氱敤鍏滃簳
    if preferred_name != "MTMDChatHandler":
        cls = _get_handler_cls("MTMDChatHandler")
        if cls is not None:
            print(f"[BSAI_Qwen_Prompt_Enhancer] 鎻愮ず锛氫綘瑁呯殑 llama-cpp-python 娌℃湁 {preferred_name}锛?
                  f"宸茶嚜鍔ㄦ敼鐢?MTMDChatHandler锛堥€氱敤澶氭ā鎬侊紝mtmd-mmproj 鎶曞奖鍣ㄥ潎鍙級銆?)
            return cls
    return None


def _list_available_handlers():
    """鍔ㄦ€佹灇涓?llama_cpp.llama_chat_format 閲屽疄闄呭彲鐢ㄧ殑 *ChatHandler锛堣瑙夌被浼樺厛锛?""
    try:
        from llama_cpp import llama_chat_format as lcf
        handlers = [n for n in dir(lcf) if n.endswith("ChatHandler")]
        # 瑙嗚/澶氭ā鎬佷紭鍏堟帓搴忥紙鍚?V/vision/VL 瀛楁牱鎴栫煡鍚嶈瑙夋ā鍨嬶級
        vision_kw = ("VL", "Vision", "GLM", "Gemma", "MiniCPM", "Moondream", "Llava",
                     "Step", "LFM", "Qwen", "Obsidian")
        vision = sorted([h for h in handlers if any(k in h for k in vision_kw)],
                        key=lambda x: (0, x))
        other = sorted([h for h in handlers if h not in vision], key=lambda x: (1, x))
        return vision + other
    except Exception:
        return ["Qwen3VLChatHandler", "Qwen25VLChatHandler", "Qwen35ChatHandler",
                "Gemma3ChatHandler", "Gemma4ChatHandler"]


# 鍙嬪ソ妯″瀷鍚嶆爣绛?-> 瀹為檯 handler 绫诲悕锛堢敤鎴风洿瑙傚彲瑙佺殑"鏈€鏂版ā鍨?鍒楄〃锛?
_FRIENDLY_HANDLERS = [
    # 鎶?mtmd 閫氱敤澶氭ā鎬佹斁鍒扮涓€浣嶏細鍏煎鏈€骞匡紙浠讳綍甯?mtmd-mmproj 鐨?GGUF 閮借兘璺戯級
    ("MTMD 閫氱敤澶氭ā鎬?(鎺ㄨ崘: Qwen3.5+/Gemma4/GLM 绛夊甫 mtmd-mmproj 鐨勬ā鍨?", "MTMDChatHandler"),
    ("Qwen 3.8 / 3.6 / 3.5 瑙嗚 (闇€鏇存柊 llama-cpp-python)", "Qwen35ChatHandler"),
    ("Qwen 3 / 3-VL 瑙嗚 (闇€鏇存柊 llama-cpp-python)", "Qwen3VLChatHandler"),
    ("Qwen 2.5-VL / 2-VL 瑙嗚", "Qwen25VLChatHandler"),
    ("Gemma 4 瑙嗚", "Gemma4ChatHandler"),
    ("Gemma 3 瑙嗚 (闇€鏇存柊 llama-cpp-python)", "Gemma3ChatHandler"),
    ("GLM 4.6V 瑙嗚 (闇€鏇存柊 llama-cpp-python)", "GLM46VChatHandler"),
    ("GLM 4.1V 瑙嗚 (闇€鏇存柊 llama-cpp-python)", "GLM41VChatHandler"),
    ("MiniCPM-V4.5 (闇€鏇存柊 llama-cpp-python)", "MiniCPMv45ChatHandler"),
    ("MiniCPM-V2.6", "MiniCPMv26ChatHandler"),
    ("LFM 2.5-VL (闇€鏇存柊 llama-cpp-python)", "LFM25VLChatHandler"),
    ("LFM 2-VL (闇€鏇存柊 llama-cpp-python)", "LFM2VLChatHandler"),
    ("Step 3-VL (闇€鏇存柊 llama-cpp-python)", "Step3VLChatHandler"),
]
_AUTO_LABEL = "auto锛堟寜妯″瀷鍚嶈嚜鍔ㄨ瘑鍒?Qwen3.8/Gemma4/GLM4.6 绛夊叏閮ㄦ敮鎸佹ā鍨嬶級"


def _chat_handler_labels():
    """chat_handler 涓嬫媺锛歛uto + 鍙嬪ソ妯″瀷鍚?+ 鍏朵粬瀹為檯鍙敤 handler 绫诲悕 + None"""
    friendly_labels = [lbl for lbl, _ in _FRIENDLY_HANDLERS]
    available = set(_list_available_handlers())
    mapped_cls = {cls for _, cls in _FRIENDLY_HANDLERS}
    extra = sorted([h for h in available if h not in mapped_cls])
    return [_AUTO_LABEL] + friendly_labels + extra + ["None"]


def _resolve_handler_label(label):
    """鍙嬪ソ鏍囩 -> 瀹為檯 handler 绫诲悕锛沘uto 璧拌嚜鍔ㄨ瘑鍒紱绾被鍚嶅師鏍疯繑鍥炪€?
    杩斿洖 '__auto__' 琛ㄧず璁?_pick_chat_handler(model_name) 鑷姩鍒ゆ柇銆?""
    if not label or label == "None":
        return ""
    if label.startswith("auto"):
        return "__auto__"
    for friendly, cls in _FRIENDLY_HANDLERS:
        if label == friendly:
            return cls
    return label  # 绾被鍚嶏紙Llava/Moondream/Obsidian 绛夛級鍏滃簳


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
        print(f"[BSAI_Qwen_Prompt_Enhancer] 鍔犺浇 chat handler {handler_name} 澶辫触: {e}")
        _CHAT_HANDLER_CACHE[handler_name] = None
        return None


# ============================================================
# 鏈湴 HF (HuggingFace Transformers) 閫氶亾杈呭姪
# 鎵弿 models/LLM 涓?safetensors/bin 鐨?HF 妯″瀷锛團lorence-2 / Llama / 鈥︼級锛?
# 鐢?transformers 鍔犺浇锛岃鐩栭潪 GGUF 鐨勬湰鍦版ā鍨嬶紝瀹炵幇"璋冪敤 LLM 鐩綍鍏ㄩ儴妯″瀷"銆?
# ============================================================
def _scan_hf_models():
    """鎵弿 models/LLM 涓嬬殑 HuggingFace 妯″瀷鐩綍 -> [{id, path, arch, kind}]
    kind: 'florence2'锛堣瑙?caption/prompt 鐢熸垚锛岄渶瑕佸浘鐗囷級 | 'causal'锛堟枃鏈?LLM锛?
    鍒ゅ畾渚濇嵁 config.json 鐨?architectures銆?""
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
                    # 鏈煡鏋舵瀯锛氶粯璁ゆ寜鏂囨湰 causal 灏濊瘯
                    kind = "causal"
            except Exception as e:
                print(f"[BSAI_Qwen_Prompt_Enhancer] 璇诲彇 HF config 澶辫触 {cfg_path}: {e}")
            found.append({"id": rel, "path": root, "arch": arch, "kind": kind})
    return found


def _hf_model_display_list():
    """HF 妯″瀷涓嬫媺锛?鐩綍鍚?[arch]'"""
    items = []
    for m in _scan_hf_models():
        label = m["id"] if m["arch"] else m["id"]
        if m["arch"]:
            label = f"{m['id']} [{m['arch']}]"
        items.append(label)
    return items


def _hf_model_id_from_label(label):
    """浠庝笅鎷夋爣绛惧弽鏌ユā鍨嬬洰褰?id锛堝幓鎺夊熬閮?[arch]锛?""
    if not label:
        return ""
    m = re.search(r"\[([^\[\]]+)\]\s*$", label.strip())
    if m:
        return label.strip()[:m.start()].strip()
    return label.strip()


_HF_CACHE = {}


def _load_hf(model_dir_id, device):
    """鍔犺浇 HF 妯″瀷 -> dict {model, processor/tokenizer, kind, arch}"""
    key = (model_dir_id, device)
    if key in _HF_CACHE and _HF_CACHE[key] is not None:
        return _HF_CACHE[key]
    try:
        import torch
        from transformers import AutoProcessor, AutoTokenizer, AutoModelForCausalLM
    except ImportError as e:
        raise RuntimeError(
            f"[BSAI_Qwen_Prompt_Enhancer] 缂哄皯 transformers/torch: {e}\n"
            "璇峰湪鏈?ComfyUI 鐨?python 鐜鎵ц: pip install transformers torch")

    # 瀹氫綅妯″瀷鐩綍
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
        raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] 鎵句笉鍒?HF 妯″瀷鐩綍: {model_dir_id}")

    # 鍒ゅ畾鏋舵瀯
    arch = ""
    with open(os.path.join(model_dir, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    archs = cfg.get("architectures", [])
    if archs:
        arch = archs[0]

    dtype = torch.float16 if device != "cpu" else torch.float32
    torch_dtype = dtype

    if arch == "Florence2ForConditionalGeneration":
        # Florence-2 闇€瑕?trust_remote_code=True锛堣嚜甯?modeling/configuration 鑴氭湰锛?
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
    print(f"[BSAI_Qwen_Prompt_Enhancer] 鍔犺浇鏈湴 HF 妯″瀷: {model_dir_id} arch={arch} device={device}")
    return entry


def _clear_hf_cache():
    _HF_CACHE.clear()


def _run_florence2(entry, images, task, max_tokens, temperature, top_p, device):
    """Florence-2 瑙嗚鐢熸垚锛氭敮鎸?<CAPTION> / <DETAILED_CAPTION> / <MORE_DETAILED_CAPTION>
    浠ュ強 PromptGen 寰皟妯″瀷甯哥敤浠诲姟銆傝繑鍥炴枃鏈€?""
    import torch
    model = entry["model"]
    processor = entry["processor"]
    if images is None or len(images.shape) < 3 or images.shape[0] == 0:
        raise RuntimeError("[BSAI_Qwen_Prompt_Enhancer] Florence-2 闇€瑕佹帴鍏?image_1 杈撳叆锛堣瑙夋ā鍨嬶級")
    # 鍙栫涓€寮犲浘
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
    """鏂囨湰 causal LLM锛圠lama/Gemma/Qwen 绛夛級鐢?chat_template 鐢熸垚銆?""
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
        # 鍏滃簳锛氱畝鍗曟嫾鎺?
        text = system_prompt + "\n\n" + prompt_text
    inputs = tokenizer(text, return_tensors="pt").to(device)
    gen_kwargs = {"max_new_tokens": int(max_tokens), "do_sample": True,
                  "temperature": float(temperature), "top_p": float(top_p)}
    if int(top_k) > 0:
        gen_kwargs["top_k"] = int(top_k)
    with torch.no_grad():
        out = model.generate(**inputs, **gen_kwargs)
    full = tokenizer.decode(out[0], skip_special_tokens=True)
    # 鍘绘帀杈撳叆閮ㄥ垎锛屽彧淇濈暀鐢熸垚娈?
    if has_template:
        inp_text = tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)
        if full.startswith(inp_text):
            full = full[len(inp_text):].strip()
    return full


# ============================================================
# MTP / NextN 棰勬祴灞傛娴嬩笌鑷姩鍓ョ锛堢Щ妞嶈嚜 BSAI_QwenNodes锛?
# Qwen3.5/3.6/3.8 绛夋ā鍨嬪父甯?MTP 灞傦紝鏃х増 llama-cpp-python 涓嶆敮鎸侊紝
# 杩欓噷鑷姩妫€娴嬪苟鐢熸垚鍘?MTP 鐗堟湰鐨?GGUF锛屼繚璇佹ā鍨嬭兘姝ｅ父鍔犺浇銆?
# ============================================================
def _check_mtp_layer(model_path):
    """妫€鏌?GGUF 鏂囦欢鏄惁鍖呭惈 MTP/NextN 棰勬祴灞傚厓鏁版嵁銆?""
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
    """浠?GGUF 鏂囦欢涓墺绂?MTP/NextN 灞傦紝杩斿洖鍓ョ鍚庢枃浠惰矾寰勶紝澶辫触杩斿洖 None銆?""
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

        print(f"[BSAI_Qwen_Prompt_Enhancer] 宸茶嚜鍔ㄧ敓鎴愬幓 MTP 鐗堟湰: {os.path.basename(no_mtp_path)}")
        return no_mtp_path
    except Exception as e:
        print(f"[BSAI_Qwen_Prompt_Enhancer] MTP 鍓ョ澶辫触: {e}")
        return None


def _reset_llm_state(llm):
    """閲嶇疆 LLM 涓婁笅鏂囩姸鎬侊紝閬垮厤澶氭鎺ㄧ悊闂翠笂涓嬫枃娈嬬暀姹℃煋杈撳嚭銆?""
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
    """绛惧悕鍏煎鐨?create_chat_completion 璋冪敤锛岃嚜鍔ㄩ€傞厤涓嶅悓鐗堟湰 llama-cpp-python 鐨勫弬鏁板悕銆?""
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
        # 鍏煎 presence_penalty -> present_penalty 鐨勬嫾鍐欏樊寮?
        if "presence_penalty" in kwargs and "presence_penalty" not in allowed and "present_penalty" in allowed:
            kwargs["present_penalty"] = kwargs.pop("presence_penalty")
        kwargs = {k: v for k, v in kwargs.items() if k in allowed}
    return llm.create_chat_completion(**kwargs)


def _normalize_seed(seed_value):
    """瑙勮寖鍖?seed 鍊硷紝澶辫触杩斿洖 None锛堣 llama.cpp 鑷繁闅忔満锛夈€?""
    try:
        seed_value = int(seed_value)
    except Exception:
        return None
    if seed_value < 0:
        return None
    return seed_value


_LLM_CACHE = {}


def _detect_family_from_name(model_name):
    """浠庢ā鍨嬪悕鎺ㄦ柇妯″瀷绯诲垪锛堜笌 BSAI_ComfyUI_Nodes 鐨?family 涓嬫媺瀵瑰簲锛夈€?""
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
    """llama.cpp 鏋侀檺鎻愰€熷弬鏁版槧灏勶紙-ncmoe / -ctk/-ctv / --no-mmap / --mlock / -fa / -t锛夈€?
    浠?MoE 妯″瀷鐨?n_cmoe 鏈夋敹鐩婏紙涓撳鎷嗗垎鏄惧瓨/鍐呭瓨锛夛紝绋犲瘑妯″瀷鏃犳晥銆?
    llama-cpp-python 0.3.36锛歯_cmoe 鏆傛湭鏆撮湶锛屾娴嬪埌鏀寔浼氳嚜鍔ㄩ€忎紶锛堝崌绾у悗鍗崇敓鏁堬級銆?
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
    # auto: 涓嶄紶 鈫?榛樿 AUTO(-1)
    if int(threads) > 0:
        out["n_threads"] = int(threads)
    if int(n_cmoe) > 0:
        try:
            sig = inspect.signature(Llama.__init__)
            if "n_cmoe" in sig.parameters:
                out["n_cmoe"] = int(n_cmoe)
                print(f"[BSAI_Qwen_Prompt_Enhancer] 宸插惎鐢?MoE 涓撳鎷嗗垎鍔犻€?n_cmoe={n_cmoe}")
            else:
                print("[BSAI_Qwen_Prompt_Enhancer] 褰撳墠 llama-cpp-python 涓嶆敮鎸?n_cmoe锛堥渶鏀寔 -ncmoe 鐨勬柊鏋勫缓锛夛紝"
                      "宸茶烦杩囦笓瀹舵媶鍒嗭紱鍗囩骇 llama-cpp-python 鍚庢鍙傛暟鑷姩鐢熸晥銆?)
        except Exception:
            pass
    return out


def _load_llm(model_name, mmproj_name, chat_handler_name, n_ctx, n_gpu_layers, load_mtp,
              n_cmoe=0, kv_cache_quant="auto", use_mmap=True, use_mlock=False,
              flash_attn="auto", threads=0):
    """鍔犺浇鏈湴 GGUF 妯″瀷 鈥?绮剧‘瀵归綈 BSAI_ComfyUI_Nodes 鐨?BSAI_QwenNodes.py 鍔犺浇閫昏緫銆?
    浼樺厛浣跨敤 Qwen35ChatHandler / Qwen3VLChatHandler / Gemma4ChatHandler 绛変笓鐢?handler锛?
    涓嶇敤 MTMDChatHandler锛堥儴鍒嗙増鏈己绗﹀彿锛屼細瀵艰嚧宕╂簝锛夈€?""
    if Llama is None:
        raise RuntimeError(
            "鏈娴嬪埌 llama-cpp-python锛坙lama_cpp锛夈€傝鍏堝畨瑁呰渚濊禆銆俓n"
            "瀹夎鏂规硶锛氬湪 ComfyUI 鐨?python 鐜涓墽琛?pip install llama-cpp-python"
        )

    key = (model_name, mmproj_name, chat_handler_name, n_ctx, n_gpu_layers, load_mtp,
           int(n_cmoe or 0), str(kv_cache_quant).lower(), bool(use_mmap), bool(use_mlock),
           str(flash_attn).lower(), int(threads or 0))
    if key in _LLM_CACHE and _LLM_CACHE[key] is not None:
        cached_llm, cached_active = _LLM_CACHE[key]
        return cached_llm, cached_active

    # ---- 妯″瀷鐩綍锛氫娇鐢?ComfyUI 鍐呯疆鐨?models/LLM 鐩稿璺緞 ----
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
        raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] 鎵句笉鍒版ā鍨嬫枃浠? {name}锛堝凡鎵弿 {dirs}锛?)

    model_path = find(model_name)

    # ---- MTP 灞傝嚜鍔ㄦ娴嬩笌棰勫墺绂伙紙涓?BSAI_QwenNodes 瀹屽叏涓€鑷达級----
    has_mtp = _check_mtp_layer(model_path)
    if has_mtp and not load_mtp:
        no_mtp_path = _strip_mtp_layer(model_path)
        if no_mtp_path and os.path.exists(no_mtp_path):
            model_path = no_mtp_path
            print(f"[BSAI_Qwen_Prompt_Enhancer] 妫€娴嬪埌 MTP 灞傦紝宸插垏鎹㈠埌鍘?MTP 鐗堟湰: "
                  f"{os.path.basename(no_mtp_path)}")

    # ---- chat handler锛氫紭鍏堢敤涓撶敤 handler锛堜笌 BSAI_QwenNodes 涓€鑷达級----
    mmproj_path = None
    if mmproj_name:
        mmproj_path = find(mmproj_name)

    chat_handler = None
    mmproj_actually_active = False
    if mmproj_path:
        # 1) 鍏堟寜妯″瀷鍚嶆帹鏂鏃忥紝灏濊瘯涓撶敤 handler锛堟渶鍙潬锛?
        family = _detect_family_from_name(model_name)

        # 2) 鑻ョ敤鎴峰湪涓嬫媺閲岄€変簡鐗瑰畾 handler 鍚嶏紙闈?auto / 闈?None锛夛紝鐢ㄩ偅涓鐩?
        resolved = _resolve_handler_label(chat_handler_name)
        if resolved and resolved != "__auto__":
            # 鐢ㄦ埛鏄庣‘鎸囧畾浜?handler 绫诲悕锛岀洿鎺ョ敤
            handler_cls = _resolve_handler_cls(resolved)
            if handler_cls is not None:
                # 涓撶敤 handler锛氭寜 BSAI_QwenNodes 鐨勫弬鏁扮粍鍚堟瀯閫?
                try:
                    chat_handler = handler_cls(
                        clip_model_path=mmproj_path,
                        enable_thinking=False,
                        verbose=False,
                        use_gpu=False,
                        image_min_tokens=1024,
                    )
                except TypeError:
                    # 鑰佺増鏈?handler 鍙傛暟涓嶅悓锛岄檷绾у皾璇?
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

        # 3) 鑷姩妯″紡 / 鎸囧畾 handler 澶辫触 鈫?鎸夊鏃忕敤涓撶敤 handler锛圔SAI_QwenNodes 鍚屾锛?
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

        # 4) 涓撶敤 handler 閮芥病鏈?鈫?灏濊瘯閫氱敤 MTMDChatHandler锛堟敞鎰忥細鏃х増鍙兘缂虹鍙凤級
        if chat_handler is None:
            mtmd_cls = _resolve_handler_cls("MTMDChatHandler")
            if mtmd_cls is not None:
                try:
                    chat_handler = mtmd_cls(clip_model_path=mmproj_path, verbose=False)
                except Exception as e:
                    print(
                        f"[BSAI_Qwen_Prompt_Enhancer] [WARN] MTMDChatHandler 鍒濆鍖栧け璐? {e}\n"
                        "    宸查檷绾т负绾枃鏈ā寮忥紙鍥剧墖灏嗕笉浼氳鍙戦€佺粰妯″瀷锛夈€俓n"
                        "    寤鸿锛氭洿鏂?llama-cpp-python 鍒版敮鎸?Qwen35ChatHandler 鐨勭増鏈€?
                    )
                    chat_handler = None

        mmproj_actually_active = chat_handler is not None

    # ---- 鍔犺浇妯″瀷锛氫笌 BSAI_QwenNodes 瀹屽叏涓€鑷寸殑鍙傛暟缁勫悎 ----
    llama_kwargs = {
        "model_path": model_path,
        "chat_handler": chat_handler,
        "n_ctx": int(n_ctx),
        "n_gpu_layers": int(n_gpu_layers),
        "verbose": False,
    }

    # 鈹€鈹€ 瑙嗛鍚屾鏋侀檺鎻愰€熷弬鏁帮紙n_cmoe / KV閲忓寲 / mmap / mlock / flash-attn / 绾跨▼锛夆攢鈹€
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
    print(f"[BSAI_Qwen_Prompt_Enhancer] 鍔犺浇鏈湴 LLaMA: {display_name} "
          f"+ {mmproj_name or '鏃?} handler={handler_label} "
          f"(active={mmproj_actually_active}) n_ctx={n_ctx} n_gpu_layers={n_gpu_layers}")

    try:
        llm = Llama(**llama_kwargs)
    except ValueError as e:
        err_str = str(e)
        if "Failed to load model from file" in err_str:
            # MTP 鐩稿叧澶辫触锛氳嚜鍔ㄥ皾璇曞幓 MTP 鐗堟湰
            if has_mtp and not load_mtp:
                no_mtp_path = _strip_mtp_layer(model_path)
                if no_mtp_path and no_mtp_path != model_path:
                    print(f"[BSAI_Qwen_Prompt_Enhancer] 妯″瀷鍔犺浇澶辫触锛屽皾璇曞幓 MTP 鐗堟湰: "
                          f"{os.path.basename(no_mtp_path)}")
                    llama_kwargs["model_path"] = no_mtp_path
                    try:
                        llm = Llama(**llama_kwargs)
                        _LLM_CACHE[key] = (llm, mmproj_actually_active)
                        return llm, mmproj_actually_active
                    except Exception:
                        pass
                raise RuntimeError(
                    "妯″瀷鍔犺浇澶辫触锛氳 GGUF 鏂囦欢鍖呭惈 MTP/NextN 棰勬祴灞傦紙nextn_predict_layers锛夛紝\n"
                    "褰撳墠 llama-cpp-python 鐗堟湰涓嶆敮鎸佹鐗规€с€俓n\n"
                    "瑙ｅ喅鏂规锛歕n"
                    "1. 宸插皾璇曡嚜鍔ㄧ敓鎴愬幓 MTP 鐗堟湰锛岃妫€鏌ュ悓鐩綍涓嬫槸鍚︽湁 -noMTP.gguf 鏂囦欢\n"
                    "2. 鎵嬪姩浣跨敤鍘?MTP 鐗堟湰鐨?GGUF 鏂囦欢\n"
                    "3. 鎴栦娇鐢ㄤ笉鍚?MTP 灞傜殑 Qwen3.5/3.6/3.8 妯″瀷浣滀负鏇夸唬\n"
                    f"鍘熷閿欒锛歿e}"
                )
            raise RuntimeError(
                "妯″瀷鍔犺浇澶辫触锛欶ailed to load model from file\n"
                "鍙兘鐨勫師鍥狅細\n"
                "1. 妯″瀷鏂囦欢鎹熷潖鎴栨牸寮忎笉鍏煎\n"
                "2. llama-cpp-python 鐗堟湰涓嶆敮鎸佽妯″瀷鏋舵瀯\n"
                "3. 妯″瀷鏂囦欢璺緞閿欒\n"
                "寤鸿锛歕n"
                "- 妫€鏌ユā鍨嬫枃浠跺畬鏁存€n"
                "- 鏇存柊 llama-cpp-python 鍒版渶鏂扮増鏈琝n"
                "- 纭繚妯″瀷璺緞姝ｇ‘"
            )
        if "Failed to create context with model" in err_str:
            raise RuntimeError(
                "妯″瀷鍔犺浇澶辫触锛欶ailed to create context with model\n"
                "鍙兘鐨勫師鍥狅細\n"
                "1. 妯″瀷鏂囦欢鎹熷潖鎴栨牸寮忎笉鍏煎\n"
                "2. llama-cpp-python 鐗堟湰涓嶆敮鎸佽妯″瀷\n"
                "3. 鏄惧瓨涓嶈冻\n"
                "4. 妯″瀷鏂囦欢璺緞閿欒\n"
                "寤鸿锛歕n"
                "- 妫€鏌ユā鍨嬫枃浠跺畬鏁存€n"
                "- 鏇存柊 llama-cpp-python 鍒版渶鏂扮増鏈琝n"
                "- 鍑忓皯 GPU 灞傛暟鎴栦娇鐢ㄦ洿灏忕殑妯″瀷\n"
                "- 纭繚妯″瀷璺緞姝ｇ‘"
            )
        raise

    _LLM_CACHE[key] = (llm, mmproj_actually_active)
    return llm, mmproj_actually_active


def _clear_cache():
    """娓呯┖鏈湴 LLaMA 缂撳瓨骞堕噴鏀炬樉瀛橈紙涓?G 鐩?BSAI_QwenNodes 瀵归綈锛夈€?""
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
# 涓夊悎涓€澧炲己鑺傜偣
# ============================================================
class BSAI_Qwen_Prompt_Enhancer:
    # 銆恦1.01銆戜竴閿吋瀹规棫宸ヤ綔娴佸瓨妗ｏ細hf_model_name / llm_model_name / system_template 绛?combo
    # 鍦ㄣ€屾ā鍨嬫湭涓嬭浇 / 妯″瀷鐩綍鍙樺寲 / 妯℃澘搴撶増鏈笉鍚屻€嶆椂锛屽瓨妗ｅ€煎彲鑳戒笉鍦ㄥ綋鍓嶄笅鎷夊垪琛?
    # 锛堝吀鍨嬫姤閿欙細Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<鏈彂鐜?HF 妯″瀷>']锛夈€?
    # ComfyUI 榛樿浼氬 combo 鍋?value-in-list 鏍￠獙骞剁孩妗嗘姤閿欍€侀樆濉炴暣鍥撅紙Output will be ignored锛夈€?
    # 杩欓噷鏀捐鎵€鏈?combo 鏍￠獙锛氬紑鍥句笉绾㈡銆佷笉闃诲锛涜繍琛屾椂鍚庣閫昏緫浼氱粰鍑哄弸濂戒腑鏂囨彁绀猴紝
    # 鍓嶇 JS锛坧rompt_enhancer.js锛夎繕浼氬湪鍔犺浇宸ヤ綔娴佹椂鑷姩鎶婇潪娉?combo 鍊奸噸缃负褰撳墠鍒楄〃棣栭」銆?
    @staticmethod
    def VALIDATE_INPUTS(*args, **kwargs):
        # v1.01.2: 杩斿洖鍊煎吋瀹规柊鏃т袱浠?ComfyUI 鏍￠獙璇箟锛?
        # - 鏃х増浠ヤ綅缃弬璋冪敤 VALIDATE_INPUTS(input_name, input_value)锛岃繑鍥?None 琛ㄧず閫氳繃锛?
        # - 鏂扮増浠?**kwargs 浼犲叆鍏ㄩ儴杈撳叆璋冪敤锛岃姹傝繑鍥?True锛堣繑鍥?None 浼氭姤
        #   "Custom validation failed for node: X - None"锛夛紝涓?kwargs 褰㈡€佽嚜鍔ㄨ烦杩?combo 鏍￠獙銆?
        # 鍒ゅ埆锛氭敹鍒?kwargs锛堟柊鐗堝舰鎬侊級=> True锛涗粎涓や釜浣嶇疆鍙傦紙鏃х増褰㈡€侊級=> None銆?
        if not kwargs and len(args) == 2:
            return None
        return True

    @classmethod
    def INPUT_TYPES(cls):
        # 姣忔鎵撳紑鑺傜偣閮介噸鏂伴€掑綊鎵弿锛屾柊澧炴ā鍨嬫棤闇€閲嶅惎 ComfyUI
        models, mmprojs = _scan_gguf()
        no_model = "<鏈彂鐜?GGUF>"
        return {
            "required": {
                # ---- 鍚庣鍒囨崲 ----
                "backend": (BACKEND_LABELS, {"default": BACKEND_PE}),
                # ---- 鍏叡鍙傛暟锛堜笁涓悗绔叡鐢級----
                "prompt_text": ("STRING", {
                    "multiline": True,
                    "default": "涓€涓┛绾㈣鐨勫コ瀛╃珯鍦ㄦū鑺辨爲涓嬶紝鎵嬮噷鎷跨潃濂惰尪锛屽倣鏅氶槼鍏?,
                    "placeholder": "杈撳叆澶х櫧璇濇彁绀鸿瘝锛堜腑鏂?鑻辨枃鍧囧彲锛夈€侷2I/澶氬浘妯″紡鍙敤 鍥?/鍥?鈥?鎸囦唬鍙傝€冨浘銆?,
                }),
                "system_template": (template_display_list(), {"default": "Qwen-Image-2.1 瀹樻柟 PE-T2I 绯荤粺瑙勫垯 [official_t2i]"}),
                "custom_system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "鐣欑┖浣跨敤涓婃柟妯℃澘锛涘～鍐欏垯瑕嗙洊妯℃澘浣滀负 system prompt",
                }),
                # 銆恦2銆戠敤鎴烽澶栬姹傦紙鎷煎埌 MERGED_TEXT 杈撳嚭锛夛紝涓嶈繘鍏?LLM 鍐呴儴瀵硅瘽銆?
                # 娴锋姤澧欓€夋ā鏉挎椂涔熶細鍚屾瑙﹀彂棰勮锛岃 Show Text 绔嬪嵆鏄剧ず鍚堝苟鏂囨湰銆?
                "user_requirement": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "鐢ㄦ埛瀵瑰綋鍓嶄换鍔＄殑棰濆瑕佹眰锛堟嫾鍒?MERGED_TEXT 杈撳嚭锛屼笌涓嬫柟娴锋姤澧欓厤鍚堜娇鐢級\n渚嬶細灏侀潰鍚富鏍囬+鍓爣棰橈紱宸︿晶鏀句富瑙嗚锛屽彸渚х暀鐧芥斁鏂囨锛涢厤鑹茬敤娣辫摑+姗欓噾銆?,
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.01}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "top_k": ("INT", {"default": 40, "min": 0, "max": 1000}),
                "repeat_penalty": ("FLOAT", {"default": 1.1, "min": 0.0, "max": 5.0, "step": 0.01}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "max_tokens": ("INT", {"default": 4096, "min": 64, "max": 32768}),
                "speed_preset": (list(cls._SPEED_PRESETS.keys()), {"default": _DEFAULT_SPEED}),
                # ---- 瀹樻柟PE 涓撳睘 ----
                "pe_mode": (["auto", "T2I (鏂囩敓鍥?", "I2I (鍥剧敓鍥?缂栬緫)"], {"default": "auto"}),
                "min_p": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "thinking": ("BOOLEAN", {"default": True}),
                "mtp": (["auto", "off", "2", "3", "4", "5"], {"default": "auto"}),
                # ---- 鏈湴LLaMA 涓撳睘 ----
                "llm_model_name": ((models if models else [no_model]), {"default": models[0] if models else no_model}),
                "mmproj_name": ([""] + mmprojs, {"default": _auto_pair_mmproj(models[0], mmprojs) if models else ""}),
                "chat_handler": (_chat_handler_labels(), {"default": _AUTO_LABEL}),
                "n_ctx": ("INT", {"default": 8192, "min": 512, "max": 65536}),
                "n_gpu_layers": ("INT", {"default": -1, "min": -1, "max": 200}),
                "load_mtp": ("BOOLEAN", {"default": False}),
                # ---- 鏋侀檺鎻愰€熷弬鏁帮紙瑙嗛鍚屾 llama.cpp锛氭樉瀛?鍐呭瓨娣峰悎妯″紡锛?---
                "n_cmoe": ("INT", {
                    "default": 0, "min": 0, "max": 256, "step": 1,
                    "tooltip": "MoE涓撳鎷嗗垎鍒癈PU/鍐呭瓨灞傛暟(-ncmoe)銆備粎MoE鏈夋晥锛岀瀵嗘棤鏁堛€俓nQwen-35B-A3B瀹炴祴绾?4鏈€绋筹紱0=鍏抽棴銆傚綋鍓?.3.36鏆傛湭鏀寔锛屽崌绾у悗鑷姩鐢熸晥銆?,
                }),
                "kv_cache_quant": (["auto(f16涓嶉噺鍖?", "q8_0", "q4_0"], {
                    "default": "auto(f16涓嶉噺鍖?",
                    "tooltip": "KV缂撳瓨閲忓寲(-ctk/-ctv锛宷4_0=瑙嗛鏁堟灉)銆傞檷鏄惧瓨鎻愰€燂紝绮惧害鐣ラ檷銆?,
                }),
                "use_mmap": ("BOOLEAN", {"default": True, "tooltip": "use_mmap锛涘唴瀛樹笉瓒?鎹㈤〉鍙叧闂?--no-mmap)銆?}),
                "use_mlock": ("BOOLEAN", {"default": False, "tooltip": "use_mlock(--mlock)閿佸唴瀛橀槻鎹㈠嚭銆?}),
                "flash_attn": (["auto", "on", "off"], {"default": "auto", "tooltip": "-fa銆俛uto=妯″瀷鏀寔鍗冲惎鐢ㄣ€?}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1, "tooltip": "-t 绾跨▼鏁?瑙嗛绀轰緥14)锛?=鑷姩銆?}),
                "keep_loaded": ("BOOLEAN", {"default": False}),
                # ---- API 涓撳睘 ----
                "api_base": ("STRING", {
                    "default": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "placeholder": "OpenAI 鍏煎鎺ュ彛鍦板潃锛屼緥濡?https://dashscope.aliyuncs.com/compatible-mode/v1 鎴?http://127.0.0.1:8000/v1",
                }),
                "api_key": ("STRING", {"default": "", "placeholder": "API Key锛堝湪绾挎湇鍔″繀濉級"}),
                "api_model_name": ("STRING", {
                    "default": "qwen3.5-vl-9b",
                    "placeholder": "妯″瀷鍚嶏紝濡?qwen3.5-vl-9b / qwen-plus / 鏈湴閮ㄧ讲鐨勬ā鍨嬪悕",
                }),
                "timeout": ("INT", {"default": 120, "min": 10, "max": 600}),
                # ---- 鏈湴HF (Transformers) 涓撳睘 ----
                "hf_model_name": (_hf_model_display_list() or ["<鏈彂鐜?HF 妯″瀷>"],),
                "hf_task": (["<MORE_DETAILED_CAPTION>", "<DETAILED_CAPTION>", "<CAPTION>", "<OD>", "<REGION_CAPTION>"], {"default": "<MORE_DETAILED_CAPTION>"}),
                "hf_device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "hf_keep_loaded": ("BOOLEAN", {"default": True}),
                # 銆恦3銆戠函棰勮锛氬嬀涓婂悗璺宠繃鎵€鏈夋ā鍨嬭皟鐢紝浠呰緭鍑?MERGED_TEXT銆?
                # 娴锋姤澧欓€夋ā鏉挎椂浼氳嚜鍔ㄥ嬀涓?鈫?瑙﹀彂涓€娆?queuePrompt 鈫?涓嬫父 Show Text 绔嬪嵆鏄剧ず銆?
                # 鐢ㄦ埛鍚庣画瑕?LLM 澧炲己鏃舵墜鍔ㄥ叧鎺夊啀 Queue Prompt銆?
                "preview_only": ("BOOLEAN", {"default": False, "label": "浠呴瑙堬紙璺宠繃 LLM锛?}),
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
        "涓€涓妭鐐广€佸洓绉嶅寮哄悗绔紙backend 涓嬫媺鍒囨崲锛屽墠绔嚜鍔ㄦ樉闅愬搴斿弬鏁帮級锛歕n"
        "鈶?瀹樻柟PE锛堟湰鍦?Qwen3.5-9B锛夛細CLIPLoader 鍔犺浇 text_encoders 鐩綍涓嬬殑瀹樻柟 PE 妯″瀷锛?
        "鎸夊畼鏂?chat 妯℃澘鐢熸垚锛岃緭鍑?rewritten_prompt / wh_ratio / ratio_follow锛?
        "I2I 妯″紡鎺?image_1~image_16锛堟渶澶?16 寮狅級锛屾彁绀鸿瘝鐢?鍥?/鍥? 鎻忚堪缂栬緫闇€姹傘€俓n"
        "鈶?鏈湴LLaMA锛圙GUF+mmproj锛夛細llama.cpp 鍔犺浇鏈湴瑙嗚澶фā鍨嬶紝鑷姩鎵弿 models/LLM 涓?text_encoders锛?
        "澶氬浘璇嗗埆鍙嶆帹锛宑hat_handler 鑷姩璇嗗埆鍏ㄧ郴鍒楁渶鏂版ā鍨嬨€俓n"
        "鈶?鏈湴HF锛圱ransformers锛夛細鍔犺浇 models/LLM 涓嬬殑 HuggingFace safetensors 妯″瀷锛?
        "瑕嗙洊 Florence-2锛堣瑙?caption 鍙嶆帹鎻愮ず璇嶏紝闇€鎺?image_1锛変笌 Llama/Gemma 绛夋枃鏈?LLM锛坈hat_template 鐢熸垚锛夈€俓n"
        "鈶?API锛圤penAI鍏煎锛夛細閰嶇疆 api_base / api_key / model_name 璋冨湪绾挎垨鏈湴 API銆俓n"
        "鍏叡鍙傛暟鍥涘悗绔叡鐢紱杈撳嚭缁熶竴 10 璺€俿peed_preset 閫夋。鍚?RECOMMENDED_* 绔彛杈撳嚭瀵瑰簲 KSampler 鍙傛暟锛?
        "鍦?KSampler 涓婂彸閿?steps/cfg 鈫?Convert to input 鎺ヤ笂鍗冲彲涓€閿鐢ㄣ€?
        "Qwen Image 2.1 涓?CFG-distilled 鏋舵瀯锛屽畼鏂规帹鑽?cfg=1.0锛涘姞閫熸。鍩轰簬瀹樻柟 day-0 鍙傛暟锛?5姝?cfg1/euler/simple锛夈€?
        "v1.08.0 鏂板钂搁LoRA妗ｏ細Viggle Turbo 6姝?瀹樻柟鑺傜偣) / Pruna 5-8姝?绀惧尯杞崲) / 闃块噷PAI Fun-Acc 4姝?瀹為獙)锛?
        "钂搁妗ｅ繀椤绘惌閰嶅搴?LoRA 涓庡浐瀹?sigma锛圴iggle Turbo Sigmas / ManualSigmas / PDD锛夛紝璇﹁ ACCELERATION_GUIDE.md銆?
    )

    # 鍔犻€熸。浣?鈫?(steps, cfg, sampler, scheduler[, hint])
    # Qwen Image 2.1 鏄?CFG-distilled 鏋舵瀯锛宑fg=1.0 涓哄畼鏂规帹鑽愬€硷紙闈炴棫鐗堢殑 3~4锛?
    # 瀹樻柟 day-0 鑱旇皟锛?5姝?cfg1/euler/simple锛圕omfyUI v0.37.0+ 鍘熺敓妯℃澘锛?
    # v1.08.0 鏂板锛?026-09~10 宸插彂甯冪殑 2.1 涓撶敤钂搁 LoRA 妗ｏ紙Viggle / Pruna / 闃块噷PAI Fun-Acc锛夈€?
    # 钂搁妗ｅ繀椤绘惌閰嶅搴?LoRA + 鍥哄畾 sigma锛圴iggle Turbo Sigmas / ManualSigmas / PDD锛夛紝
    # 涓嶈兘鐩存帴鐢ㄦ櫘閫?KSampler 鐨?scheduler 鐢熸垚 sigma锛屽惁鍒欏嚭鍣浘锛涜瑙?ACCELERATION_GUIDE.md銆?
    _SPEED_PRESETS = {
        # ===== 2.1 鍘熺敓姝ｇ‘鍙傛暟锛堝熀浜庡畼鏂?day-0 鑱旇皟锛?====
        _DEFAULT_SPEED: (25, 1.0, "euler", "simple"),
        "蹇€?15姝?CFG1 (杩唬棰勮)": (15, 1.0, "euler", "simple"),
        "鏋侀€?10姝?CFG1 (蹇€熻崏绋?": (10, 1.0, "euler", "simple"),
        "楂樿川閲?35姝?CFG1 (绮剧粏鍑哄浘)": (35, 1.0, "euler", "simple"),
        # ===== 閰嶅悎澶栭儴鍔犻€熻妭鐐癸紙鏃燣oRA锛?====
        "缂撳瓨鍔犻€?20姝?CFG1 (閰嶅悎EasyCache鑺傜偣)": (20, 1.0, "euler", "simple"),
        # ===== 钂搁 LoRA 鍔犻€熸。锛?.1 涓撶敤钂搁閫傞厤鍣紝2026-09~10 宸插彂甯冿級=====
        "Viggle Turbo 6姝?CFG1 (瀹樻柟鑺傜偣,鎺ㄨ崘)": (
            6, 1.0, "euler", "simple",
            "Viggle v0.3锛氭ā鍨嬩粨搴?comfyui/viggle_turbo.py 鎻愪緵 Viggle Turbo Sigmas + Viggle Turbo LoRA(unmerged) 涓よ妭鐐癸紝"
            "鎺?BasicGuider + SamplerCustomAdvanced锛孋FG=1.0銆佽礋鍚戠暀绌猴紱鍕跨敤 KSampler 鑷甫 scheduler銆?
            "鍘熷6姝igma=1.0,0.9375,0.875,0.75,0.5,0.25锛堣妭鐐规寜鍒嗚鲸鐜噑hift锛夈€?
            "ComfyUI宸ヤ綔娴佺敤 r128 鐗堬紙宸蹭笅杞借嚦 models/loras锛夛紱鏈満鍙︽湁 v0.1 4姝?r64 鏃х増銆?,
        ),
        "Viggle Turbo 9姝?CFG1 (浠卍iffusers)": (
            9, 1.0, "euler", "simple",
            "v0.3 鐨?姝ユā寮?鍓?姝urbo+鍚?姝ュ垏鍥瀊ase妯″瀷锛岀粏鑺?灏忓瓧鏇村ソ锛堢害3.5x浜?0姝ワ級锛?
            "鐩墠浠?diffusers 涓庢紨绀篠pace 鍙敤锛孋omfyUI 鏆傛湭鎻愪緵銆?,
        ),
        "Pruna 8姝?CFG1 (璐ㄩ噺浼樺厛,鎺ㄨ崘)": (
            8, 1.0, "euler", "simple",
            "Pruna 8姝ワ紙瀹樻柟鎺ㄨ崘榛樿锛夛細sigma=1.0,0.933333333,0.857142857,0.769230769,0.666666667,"
            "0.545454545,0.4,0.222222222锛堟湯灏?鐢辫皟搴﹀櫒琛ワ級銆傞渶鐢ㄧぞ鍖鸿浆鎹㈢増LoRA锛圢idAll/pruna-image-2.1-comfyui-loras锛?
            "鑷甫alpha鏍囬噺锛? ManualSigmas + SamplerCustom锛汣FG=1.0銆佽礋鍚戠暀绌恒€?,
        ),
        "Pruna 5姝?CFG1 (鏋侀€?": (
            5, 1.0, "euler", "simple",
            "Pruna 5姝ワ細sigma=1.0,0.94,0.857142857,0.666666667,0.4锛汬100@1024 绾?.06s锛堟彁閫?.7x锛夛紝"
            "鐢昏川鏄庢樉浣庝簬8姝ョ増锛涚敤娉曞悓涓婏紙杞崲鐗圠oRA + ManualSigmas + SamplerCustom锛夈€?,
        ),
        "瀹樻柟Fun-Acc 4姝?CFG1 (PAI,瀹為獙)": (
            4, 1.0, "euler", "simple",
            "闃块噷PAI瀹樻柟4姝ヨ捀棣忥紙PDD锛夛細sigma=1.0,0.9169867,0.7861579,0.549491,0.0锛涢粯璁?048閲囨牱銆?
            "ComfyUI鏃犲畼鏂规敮鎸侊細闇€Kijai鐨?Qwen-Image-2.1-PDD 鍒嗘敮 + LoRA杞崲锛坣orm_q/norm_k/text_norm涓哄叏鍙傦級锛?
            "灞炵ぞ鍖哄疄楠岃矾寰勩€?,
        ),
        # ===== 鏃х増鍏煎锛堜繚鐣檏ey闃叉棫宸ヤ綔娴佸け鏁堬紝鍊煎凡淇涓?.1姝ｇ‘鍙傛暟锛?====
        "鏍囧噯璐ㄩ噺 20姝?CFG3 (鎺ㄨ崘, 7B鍘熺敓)": (25, 1.0, "euler", "simple"),
        "鏋侀€?8姝?CFG2": (8, 1.0, "euler", "simple"),
        "闂數 4姝?CFG1 (闇€2.1 Lightning LoRA)": (4, 1.0, "euler", "simple"),
        "鏃т繚瀹?50姝?CFG4": (35, 1.0, "euler", "simple"),
    }

    def enhance(self, backend, prompt_text, system_template, custom_system_prompt="",
                user_requirement="",
                temperature=0.7, top_p=0.95, top_k=40, repeat_penalty=1.1, seed=0,
                max_tokens=4096, speed_preset=_DEFAULT_SPEED,
                pe_mode="auto", min_p=0.0, thinking=True, mtp="auto",
                llm_model_name="", mmproj_name="", chat_handler="", n_ctx=8192,
                n_gpu_layers=-1, load_mtp=False, keep_loaded=False,
                n_cmoe=0, kv_cache_quant="auto(f16涓嶉噺鍖?", use_mmap=True, use_mlock=False,
                flash_attn="auto", threads=0,
                api_base="", api_key="", api_model_name="", timeout=120,
                hf_model_name="", hf_task="<MORE_DETAILED_CAPTION>", hf_device="auto", hf_keep_loaded=True,
                preview_only=False,
                clip=None,
                image_1=None, image_2=None, image_3=None, image_4=None, image_5=None, image_6=None,
                image_7=None, image_8=None, image_9=None, image_10=None, image_11=None, image_12=None,
                image_13=None, image_14=None, image_15=None, image_16=None):
        # 銆恦3銆戠函棰勮锛氬嬀涓婂悗璺宠繃鎵€鏈夋ā鍨嬭皟鐢紝浠呰緭鍑?MERGED_TEXT銆?
        # 鐢ㄤ簬娴锋姤澧欓€夋ā鏉挎椂璁╀笅娓?Show Text 绔嬪埢鏄剧ず锛屾棤闇€鍔犺浇 LLM銆?
        if preview_only:
            print(f"[BSAI_Qwen_Prompt_Enhancer] [preview] custom_system_prompt={custom_system_prompt!r} len={len(custom_system_prompt or '')} system_template={system_template!r}")
            merged_text = self._build_preview_merged(
                system_template=system_template,
                custom_system_prompt=custom_system_prompt,
                user_requirement=user_requirement,
            )
            steps, cfg, sampler, scheduler, *extra = self._SPEED_PRESETS.get(
                speed_preset, self._SPEED_PRESETS[_DEFAULT_SPEED])
            print(f"[BSAI_Qwen_Prompt_Enhancer] 绾瑙堟ā寮?鈫?浠呰緭鍑?MERGED_TEXT锛屼笉璋冪敤浠讳綍妯″瀷")
            # 銆愪慨澶?2026-09-23銆戠函棰勮鍚屾牱閲婃斁甯搁┗ LLM锛堟鍓?keep_loaded=true 閬楃暀鐨?27B 鍗?~20GB 鏄惧瓨锛夛紝
            # 鍚﹀垯棰勮/鍚庣画鍑哄浘浠嶄細琚父椹?LLM 鎷栨銆俖clear_cache 鍙竻鏈湴 LLaMA 缂撳瓨锛屼笉褰卞搷 clip銆?
            _clear_cache()
            hint_line = f"\n鈿?{extra[0]}" if extra else ""
            ui_text = [
                merged_text,
                f"\n鈹€鈹€ 绾瑙堟ā寮?鈹€鈹€\n鏈皟鐢ㄤ换浣曟ā鍨嬨€侻ERGED_TEXT 宸茬敓鎴愶紝涓嬫父 Show Text / KSampler 鍙洿鎺ヤ娇鐢ㄣ€俓n"
                f"闇€瑕?LLM 澧炲己璇峰叧闂€屼粎棰勮銆嶅悗鍐?Queue Prompt銆俓n"
                f"\n鈹€鈹€ 褰撳墠鍔犻€熸。: {speed_preset} 鈫?steps={steps}, cfg={cfg}, sampler={sampler}, scheduler={scheduler} 鈹€鈹€"
                f"{hint_line}",
            ]
            # 銆愪慨澶?2026-09-23 v2銆戞捣鎶ュ閫夋ā鏉垮悗锛孍NHANCED_PROMPT(绗?璺? 杈撳嚭妯℃澘鎷兼帴 merged_text锛?
            # 鏃犺鍚庣妯″紡锛岄€夋ā鏉垮悗鎻愮ず璇嶇粺涓€璧?ENHANCED_PROMPT 灞曠ず妯℃澘鏁堟灉锛堢敤鎴烽渶姹傦級銆?
            # 鏃犳ā鏉夸笖鏃犵敤鎴疯姹傛椂 merged_text 涓虹┖ 鈫?鍥為€€鐢ㄦ埛鍘熸枃 prompt_text锛岄槻绌烘潯浠跺嚭娌欏湡鍥俱€?
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
        if backend == BACKEND_STRATA:
            # Reuse OpenAI-compatible path, pointed at local Strata server.
            return self._enhance_api(
                api_base="http://127.0.0.1:8080/v1",
                api_key="strata",
                api_model_name="qwen3.8-flash-next",
                prompt_text=prompt_text, system_template=system_template,
                custom_system_prompt=custom_system_prompt, user_requirement=user_requirement,
                max_tokens=max_tokens,
                temperature=temperature, top_p=top_p, top_k=top_k, seed=seed,
                timeout=timeout, speed_preset=speed_preset, images=images,
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
        raise ValueError(f"[BSAI_Qwen_Prompt_Enhancer] 鏈煡 backend: {backend!r}")

    # ---------------- 瀹樻柟PE ----------------
    def _enhance_official(self, clip, prompt_text, pe_mode, system_template, custom_system_prompt,
                          user_requirement,
                          max_tokens, temperature, top_p, top_k, repeat_penalty, min_p,
                          seed, thinking, mtp, speed_preset, images):
        if clip is None:
            raise ValueError(
                "[BSAI_Qwen_Prompt_Enhancer] 瀹樻柟PE 鍚庣闇€瑕佹帴鍏?clip锛歕n"
                "鐢?CLIPLoader 鍔犺浇 text_encoders 鐩綍涓嬬殑瀹樻柟 PE 妯″瀷锛坬wen3.5_9b_qwen_image_2.1_pe_*.safetensors锛夛紝"
                "鎶?CLIP 杈撳嚭鎺ュ埌鏈妭鐐圭殑 clip 杈撳叆銆?
            )
        # 1) 妯″紡鍒ゅ畾: auto -> 鏈夊浘鍗?I2I
        has_images = images is not None and len(images.shape) > 1 and images.shape[0] > 0
        mode = "T2I"
        if pe_mode != "auto":
            mode = "I2I" if "I2I" in pe_mode else "T2I"
        elif has_images:
            mode = "I2I"

        # 2) system prompt: 鑷畾涔変紭鍏堬紝鍚﹀垯妯℃澘锛坅uto/I2I 涓旀湭鏀规ā鏉挎椂鑷姩鍒囧畼鏂?I2I 瑙勫垯锛?
        DEFAULT_T2I = "Qwen-Image-2.1 瀹樻柟 PE-T2I 绯荤粺瑙勫垯 [official_t2i]"
        DEFAULT_I2I = "Qwen-Image-2.1 瀹樻柟 PE-I2I 绯荤粺瑙勫垯 [official_i2i]"
        system_prompt = custom_system_prompt.strip() if custom_system_prompt.strip() else None
        template_id = "custom"
        if system_prompt is None:
            if mode == "I2I" and system_template == DEFAULT_T2I:
                system_template = DEFAULT_I2I
            system_prompt, template_id = resolve_template(system_template, "")
            # 銆愪慨澶?2026-09-23銆戝畼鏂筆E 鏄笓鐢ㄥ井璋冩ā鍨嬶紝鏃犵郴缁熻鍒欐椂杈撳嚭涓嶅彲鎺э紙涔卞浘/娌欏湡锛夛細
            # 绌?system prompt 鑷姩鍥為€€瀵瑰簲妯″紡瀹樻柟瑙勫垯骞惰鍛娿€?
            if not system_prompt.strip():
                print("[BSAI_Qwen_Prompt_Enhancer] 璀﹀憡: 鏃犳ā鏉?绌?system prompt 涓嬪畼鏂筆E 杈撳嚭涓嶅彲鎺э紝"
                      "宸茶嚜鍔ㄥ洖閫€瀹樻柟 %s 瑙勫垯" % ("I2I" if mode == "I2I" else "T2I"))
                system_prompt = load_official_system_prompt(mode)
                template_id = "official_i2i" if mode == "I2I" else "official_t2i"

        # 3) 鏋勯€犲畼鏂?chat 娑堟伅锛堝浘鐗?token 鍓嶇疆锛?
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
            # 鍏煎杈冭€?CLIP.generate 绛惧悕
            ids = clip.generate(
                tokens, do_sample=True, max_length=int(max_tokens),
                temperature=float(temperature), top_k=int(top_k), top_p=float(top_p),
                repetition_penalty=float(repeat_penalty), seed=int(seed),
            )
        raw = clip.decode(ids, skip_special_tokens=False)

        return self._finalize(raw, speed_preset, f"鍚庣=瀹樻柟PE 妯″紡={mode} 妯℃澘={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- 鏈湴LLaMA ----------------
    def _enhance_local(self, llm_model_name, mmproj_name, chat_handler, prompt_text, system_template,
                       custom_system_prompt, user_requirement,
                       max_tokens, temperature, top_p, top_k, repeat_penalty,
                       seed, n_ctx, n_gpu_layers, load_mtp, keep_loaded, speed_preset, images,
                       n_cmoe=0, kv_cache_quant="auto(f16涓嶉噺鍖?", use_mmap=True, use_mlock=False,
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
                print("[BSAI_Qwen_Prompt_Enhancer] 璀﹀憡: 鎺ヤ簡鍥剧墖浣嗘湭閫夋嫨 mmproj锛岃瑙変俊鎭皢涓嶈浣跨敤")

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
            # mmproj 閫変簡浣?handler 鍒濆鍖栧け璐ワ紙宸查檷绾т负绾枃鏈級
            print("[BSAI_Qwen_Prompt_Enhancer] 鎻愮ず: 澶氭ā鎬佽闄嶇骇涓虹函鏂囨湰锛屽凡蹇界暐杈撳叆鍥剧墖锛?
                  "浠呯敤鏂囧瓧鎻愮ず璇嶇敓鎴愩€?)
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

        # 閲嶇疆 LLM 鐘舵€侊紝閬垮厤涓婁竴娆℃帹鐞嗘畫鐣欏奖鍝嶆湰娆¤緭鍑猴紙绉绘鑷?BSAI_QwenNodes锛?
        _reset_llm_state(llm)

        try:
            # 浣跨敤绛惧悕鍏煎璋冪敤锛岃嚜鍔ㄩ€傞厤涓嶅悓鐗堟湰 llama-cpp-python 鐨勫弬鏁板悕
            resp = _call_chat_completion(llm, messages=messages, params=params)
        except RuntimeError as e:
            if "Context Shift is explicitly disabled" in str(e):
                current_n_ctx = getattr(llm, "n_ctx", "鏈煡")
                raise RuntimeError(
                    "Context Shift 琚?C++ 鍚庣绂佺敤锛圡-RoPE 妯″瀷涓嶆敮鎸佷笂涓嬫枃婊戝姩绐楀彛锛夈€俓n"
                    f"褰撳墠 n_ctx = {current_n_ctx}锛屾棤娉曞绾冲畬鏁村璇濄€俓n"
                    "璇峰湪鑺傜偣涓澶с€宯_ctx 涓婁笅鏂囬暱搴︺€嶏細\n"
                    "  - 绾枃鏈缓璁?16384\n"
                    "  - 鍚浘鐗?瑙嗛寤鸿 32768 鎴栨洿楂榎n"
                    f"鍘熷閿欒锛歿e}"
                ) from e
            raise
        except ValueError as e:
            if "Media evaluation failed" in str(e):
                raise RuntimeError(
                    "澶氭ā鎬佸浘鍍忕紪鐮佸け璐ワ紙Media evaluation failed锛夈€俓n"
                    "鍙兘鐨勫師鍥犲拰瑙ｅ喅鏂规锛歕n"
                    "1. 杈撳叆鍥惧儚鍒嗚鲸鐜囪繃澶?鈥?璇峰皾璇曞噺灏戣緭鍏ュ浘鐗囨暟閲忥紝鎴栫缉灏忓師鍥俱€俓n"
                    "2. mmproj 瑙嗚鎶曞奖妯″瀷涓庝富妯″瀷涓嶅尮閰?鈥?璇风‘淇濆姞杞戒簡瀵瑰簲鐗堟湰鐨?mmproj 鏂囦欢銆俓n"
                    "   渚嬪锛歈wen3.8-VL 涓绘ā鍨嬪繀椤绘惌閰?Qwen3.8-VL 鐨?mmproj銆俓n"
                    "3. 鏄惧瓨涓嶈冻瀵艰嚧 CLIP 缂栫爜澶辫触 鈥?璇峰皾璇曞噺灏戣緭鍏ュ浘鐗囨暟閲忥紝鎴栭噸鍚?ComfyUI銆俓n"
                    "4. 鍥惧儚鏂囦欢鎹熷潖鎴栨牸寮忓紓甯?鈥?璇锋鏌ヨ緭鍏ュ浘鍍忚兘鍚︽甯告墦寮€銆俓n"
                    f"鍘熷閿欒锛歿e}"
                ) from e
            # 閲囨牱鍙傛暟涓嶅吋瀹规椂闄嶇骇閲嶈瘯
            print(f"[BSAI_Qwen_Prompt_Enhancer] 棣栨璋冪敤澶辫触({e})锛岄檷绾ч噰鏍峰弬鏁伴噸璇曗€?)
            resp = llm.create_chat_completion(
                messages=messages, max_tokens=int(max_tokens),
                temperature=float(temperature), top_p=float(top_p),
            )
        except Exception as e:
            # 鍏朵粬閿欒锛堝鍙傛暟涓嶅吋瀹癸級闄嶇骇閲嶈瘯
            print(f"[BSAI_Qwen_Prompt_Enhancer] 棣栨璋冪敤澶辫触({e})锛岄檷绾ч噰鏍峰弬鏁伴噸璇曗€?)
            resp = llm.create_chat_completion(
                messages=messages, max_tokens=int(max_tokens),
                temperature=float(temperature), top_p=float(top_p),
            )

        raw = resp["choices"][0]["message"].get("content") or ""
        # 鍏煎 thinking 杈撳嚭锛坮easoning_content锛?
        if not raw:
            raw = resp["choices"][0]["message"].get("reasoning_content") or ""

        # 缁撴灉娓呯悊锛堜笌 G 鐩?BSAI_QwenNodes 瀵归綈锛氬幓闄ゅ墠缂€鍐掑彿绛夛級
        raw = raw.lstrip().removeprefix(": ").strip()

        # 銆愪慨澶?2026-09-23銆慿eep_loaded=false锛歀LM 鐢ㄥ畬鍚庡啀鍗歌浇銆?
        # 涔嬪墠"鍔犺浇瀹岀珛鍗?_clear_cache"浼氭妸鍒氭嬁鍒?鍛戒腑鐨?llm close 鎺夛紝
        # 瀵艰嚧鍚庣画 create_chat_completion 鎶?Invalid chat handler: None銆?
        if not keep_loaded:
            _clear_cache()

        return self._finalize(raw, speed_preset, f"鍚庣=鏈湴LLaMA 妯℃澘={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- 鏈湴HF (Transformers) ----------------
    def _enhance_hf(self, hf_model_name, hf_task, hf_device, hf_keep_loaded,
                    prompt_text, system_template, custom_system_prompt, user_requirement,
                    max_tokens,
                    temperature, top_p, top_k, seed, speed_preset, images):
        if not hf_model_name or hf_model_name.startswith("<鏈彂鐜?):
            raise ValueError("[BSAI_Qwen_Prompt_Enhancer] 鏈湴HF 鍚庣闇€瑕侀€夋嫨涓€涓細models/LLM 涓嬬殑 HuggingFace 妯″瀷锛坰afetensors/bin锛?)

        model_dir_id = _hf_model_id_from_label(hf_model_name)
        # 璁惧閫夋嫨
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
            # 瑙嗚 caption / prompt 鍙嶆帹锛團lorence-2 / PromptGen锛?
            raw = _run_florence2(entry, images, hf_task, max_tokens, temperature, top_p, device)
            tag = f"鍚庣=鏈湴HF(瑙嗚) 妯″瀷={model_dir_id} 浠诲姟={hf_task}"
        else:
            # 鏂囨湰 causal LLM锛圠lama/Gemma/Qwen 绛夛級
            raw = _run_causal_hf(entry, system_prompt, prompt_text, max_tokens,
                                 temperature, top_p, top_k, device)
            tag = f"鍚庣=鏈湴HF(鏂囨湰) 妯″瀷={model_dir_id} 妯℃澘={template_id}"

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
            raise ValueError("[BSAI_Qwen_Prompt_Enhancer] API 鍚庣闇€瑕佸～鍐?api_base锛圤penAI 鍏煎鎺ュ彛鍦板潃锛?)

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

        # Auto-start Strata backend if we're pointing at the local Strata endpoint.
        if "127.0.0.1:8080" in api_base or "localhost:8080" in api_base:
            StrataManager = None
            # Strategy 1: already imported as a custom node module
            for _mod_name in list(sys.modules.keys()):
                if "strata" in _mod_name.lower() and "manager" in _mod_name.lower():
                    mod = sys.modules[_mod_name]
                    StrataManager = getattr(mod, "StrataManager", None)
                    if StrataManager:
                        break
            # Strategy 2: direct file load
            if StrataManager is None:
                _sm = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "BSAI-LLM-Strata", "strata_manager.py",
                )
                if os.path.exists(_sm):
                    try:
                        import importlib.util as _ilu
                        _spec = _ilu.spec_from_file_location("bsai_strata_manager", _sm)
                        _m = _ilu.util.module_from_spec(_spec)
                        _spec.loader.exec_module(_m)
                        StrataManager = getattr(_m, "StrataManager", None)
                    except Exception:
                        pass
            if StrataManager is not None:
                try:
                    ok, msg = StrataManager.ensure_running()
                    if not ok:
                        raise RuntimeError(f"Strata 鍚庣鏈氨缁? {msg}")
                    print(f"[BSAI_Qwen_Prompt_Enhancer] Strata 鍚庣灏辩华: {msg}")
                except Exception as _se:
                    raise RuntimeError(f"Strata 鑷姩鍚姩澶辫触: {_se}")

        try:
            data = _api_request(url, payload, headers, timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            if e.code == 400:
                # 閮ㄥ垎鏈嶅姟绔笉璁?top_k/seed 绛夋墿灞曢噰鏍峰弬鏁帮紝闄嶇骇涓烘渶灏?payload 閲嶈瘯涓€娆?
                minimal = {k: payload[k] for k in ("model", "messages", "temperature", "max_tokens")}
                print(f"[BSAI_Qwen_Prompt_Enhancer] API 400({body[:200]})锛岀敤鏈€灏?payload 閲嶈瘯鈥?)
                try:
                    data = _api_request(url, minimal, headers, timeout)
                except urllib.error.HTTPError as e2:
                    body2 = e2.read().decode("utf-8", errors="replace")[:500]
                    raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] API HTTP {e2.code}: {body2}")
            else:
                raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] API HTTP {e.code}: {body}")
        except Exception as e:
            raise RuntimeError(f"[BSAI_Qwen_Prompt_Enhancer] API 璋冪敤澶辫触: {e}")

        msg = data["choices"][0]["message"]
        raw = msg.get("content") or ""
        if not raw and msg.get("reasoning_content"):
            raw = msg["reasoning_content"]

        return self._finalize(raw, speed_preset, f"鍚庣=API 妯℃澘={template_id}",
                              system_template=system_template,
                              custom_system_prompt=custom_system_prompt,
                              user_requirement=user_requirement)

    # ---------------- 缁熶竴鏀跺熬 ----------------
    def _finalize(self, raw, speed_preset, tag,
                  system_template=None, custom_system_prompt="", user_requirement=""):
        enhanced, wh_ratio, ratio_follow, raw, thinking_text = get_enhanced_result(raw)
        steps, cfg, sampler, scheduler, *extra = self._SPEED_PRESETS.get(speed_preset, self._SPEED_PRESETS[_DEFAULT_SPEED])

        # 銆恦2銆慚ERGED_TEXT = (瑙ｆ瀽鍚庣殑 system prompt) + user_requirement 鎷兼帴
        # 浠呯敤浣溿€屼笅娓?Show Text / 鎻愬墠棰勮 / 鐩存帴鎺?KSampler銆嶇殑鍚堝苟鐗堟枃鏈紝
        # 涓嶈繘鍏?LLM 鍐呴儴瀵硅瘽锛涚┖ user_requirement 鏃朵笌 SYSTEM_PROMPT 绛変环銆?
        try:
            resolved_system_prompt, _tid = resolve_template(
                system_template or "Qwen-Image-2.1 瀹樻柟 PE-T2I 绯荤粺瑙勫垯 [official_t2i]",
                custom_system_prompt,
            )
        except Exception as _e:
            resolved_system_prompt = ""
            print(f"[BSAI_Qwen_Prompt_Enhancer] 瑙ｆ瀽妯℃澘澶辫触: {_e}")
        merged_text = self._build_merged_text(resolved_system_prompt, user_requirement)

        print(f"[BSAI_Qwen_Prompt_Enhancer] {tag} wh_ratio={wh_ratio} "
              f"| 鍔犻€熸。={speed_preset} 鈫?steps={steps} cfg={cfg} sampler={sampler} scheduler={scheduler}")
        hint_line = f"\n鈿?璇ユ。涓鸿捀棣廘oRA妗ｏ細{extra[0]}" if extra else ""
        ui_text = [
            enhanced,
            f"\n鈹€鈹€ 鍔犻€熼噰鏍峰缓璁?鈹€鈹€\n妗ｄ綅: {speed_preset}\n"
            f"KSampler 鈫?steps={steps}, cfg={cfg}, sampler={sampler}, scheduler={scheduler}\n"
            f"鎺ョ嚎: KSampler 鍙抽敭 steps/cfg 鈫?Convert to input锛屾帴鍏?RECOMMENDED_* 绔彛\n"
            f"{hint_line}"
            f"\n鈹€鈹€ Qwen Image 2.1 鍔犻€熻鐐?鈹€鈹€\n"
            f"1. cfg=1.0 鏄纭€硷紙2.1 涓?CFG-distilled 鏋舵瀯锛屾棤闇€楂楥FG锛涜礋鍚戞彁绀鸿瘝鍦╟fg=1鏃舵棤鏁堬級\n"
            f"2. 瀹樻柟榛樿 int8 妯″瀷: qwen_image_2.1_int8_convrot.safetensors锛堟樉瀛樺噺鍗婏級\n"
            f"3. 缂栬緫宸ヤ綔娴? 娣诲姞銆孮wen Image 2.1 Cache銆嶈妭鐐?device=auto,dtype=int8)澶嶇敤鍓嶇紑KV\n"
            f"4. 閫氱敤鎻愰€? model鈫扙asyCache鑺傜偣鈫扠Sampler (ComfyUI鏍稿績鍐呯疆,绾?.2-1.5x)\n"
            f"5. 娉ㄦ剰鍔涘姞閫? 鍚姩鍙傛暟鍔?--use-sage-attention (閲囨牱闃舵蹇?0-40%)\n"
            f"6. 钂搁LoRA锛?026-09~10宸插彂甯冿級: Viggle Turbo 6姝ュ畼鏂硅妭鐐?/ Pruna 5-8姝?绀惧尯杞崲) / 闃块噷PAI Fun-Acc 4姝?瀹為獙)锛?
            f"鍧囬渶鍥哄畾sigma锛岃瑙?ACCELERATION_GUIDE.md\n"
            f"7. lightx2v 鐨?2.1 涓撶敤 Lightning LoRA 灏氭湭鍙戝竷锛堝嬁閫?Lightning 妗ｏ級锛涘嬁鐢?TeaCache锛堝凡鍐荤粨涓嶅吋瀹?.1锛夛紱"
            f"鍕跨敤鏃х増20B Lightning LoRA锛堟灦鏋勪笉鍚岋級",
            f"\n鈹€鈹€ 鍚堝苟鏂囨湰棰勮锛圡ERGED_TEXT 杈撳嚭锛夆攢鈹€\n{merged_text}",
        ]
        return {"ui": {"text": ui_text, "merged_text": [merged_text]},
                "result": (enhanced, wh_ratio, ratio_follow, raw, thinking_text,
                           int(steps), float(cfg), sampler, scheduler, merged_text)}

    @staticmethod
    def _build_preview_merged(system_template, custom_system_prompt, user_requirement):
        """绾瑙堟ā寮忥細瑙ｆ瀽妯℃澘 + 鎷肩敤鎴疯姹傘€備笉璋冪敤浠讳綍妯″瀷銆?
        涓?_finalize 鍐呯殑閫昏緫鍚屾簮锛涚敤浜庢捣鎶ュ閫夋ā鏉挎椂璁╀笅娓哥珛鍗虫嬁鍒?MERGED_TEXT銆?
        """
        # 涓?_enhance_official 瀹屽叏涓€鑷寸殑瑙ｆ瀽浼樺厛绾?
        csp = (custom_system_prompt or "").strip()
        if csp:
            resolved = csp
        else:
            try:
                resolved, _ = resolve_template(
                    system_template or "Qwen-Image-2.1 瀹樻柟 PE-T2I 绯荤粺瑙勫垯 [official_t2i]",
                    "",
                )
            except Exception as e:
                print(f"[BSAI_Qwen_Prompt_Enhancer] 棰勮妯″紡瑙ｆ瀽妯℃澘澶辫触: {e}")
                resolved = ""
        print(f"[BSAI_Qwen_Prompt_Enhancer] [preview-build] csp_len={len(csp)} resolved_head={resolved[:60]!r}")
        return BSAI_Qwen_Prompt_Enhancer._build_merged_text(resolved, user_requirement)

    @staticmethod
    def _build_merged_text(template_text, user_requirement):
        """妯℃澘鍘熸枃 + 鐢ㄦ埛瑕佹眰鎷兼帴锛堜笌妯℃澘鑺傜偣 QwenImage21_Prompt_Template 鍚屾簮閫昏緫锛?
        - 绌?user_requirement: merged_text == template_text锛堜笉鐮村潖鐜版湁宸ヤ綔娴侊級
        - 闈炵┖: 鍦ㄥ熬閮ㄨ拷鍔犮€屻€愮敤鎴疯姹傘€慭n<瑕佹眰>\n锛堣鍔″繀鍦ㄧ敓鎴愭椂婊¤冻浠ヤ笂鐢ㄦ埛瑕佹眰銆傦級銆?
        """
        if not template_text:
            template_text = ""
        if not user_requirement or not str(user_requirement).strip():
            return template_text
        body = str(user_requirement).strip()
        return (
            template_text.rstrip()
            + "\n\n銆愮敤鎴疯姹傘€慭n"
            + "鐢ㄦ埛瀵瑰綋鍓嶄换鍔＄殑棰濆瑕佹眰锛歕n"
            + body
            + "\n锛堣鍔″繀鍦ㄧ敓鎴愭椂婊¤冻浠ヤ笂鐢ㄦ埛瑕佹眰銆傦級"
        )


def _api_request(url, payload, headers, timeout):
    import socket as _sock
    import http.client
    from urllib.parse import urlparse as _urlparse

    parsed = _urlparse(url)
    host = parsed.hostname
    port = parsed.port or 80
    path = parsed.path or "/"
    body = json.dumps(payload).encode("utf-8")

    # Python 3.14 Windows + asyncio: default socket inherits non-blocking mode.
    # Create socket manually in BLOCKING mode to avoid WinError 10035.
    s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    s.settimeout(int(timeout))
    s.setblocking(True)
    s.connect((host, port))

    conn = http.client.HTTPConnection(host, port, timeout=int(timeout))
    conn.sock = s
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    conn.close()
    return json.loads(raw)


class BSAI_Qwen_Image21_Sampler:
    """
    BSAI Qwen image 2.1 閲囨牱鍣?鈥?KSampler 鍙傛暟 + 鍙€?guider / sigmas 杈撳叆绔彛銆?

    路 淇濈暀 KSampler 鍏ㄩ儴鍙傛暟锛歴eed / steps / cfg / sampler_name / scheduler / denoise
    路 鏂板鍙€夎緭鍏ョ鍙ｏ細
        guider (GUIDER)  鈥?鐩磋繛 BasicGuider / CFGGuider 绛変笂娓歌妭鐐癸紱涓嶆帴鏃跺唴缃?CFGGuider(model, positive, negative, cfg)
        sigmas (SIGMAS)  鈥?鐩磋繛 ViggleTurboSigmas / ManualSigmas 绛変笂娓歌妭鐐癸紱涓嶆帴鏃舵寜 scheduler+steps+denoise 鐢熸垚
    路 璇箟瀵归綈锛?
        - 鎺?sigmas 鏃朵互 sigmas 涓哄噯锛堝 Viggle Turbo 鍥哄畾 6 姝?sigma锛夛紝steps 鍙傛暟浠呬綔 UI 鏄剧ず
        - 鎺?guider 鏃?cfg 鍙傛暟琚?guider 鍐呴儴閰嶇疆瑕嗙洊锛圔asicGuider 鏃?CFG锛?
        - 鏈帴 guider/sigmas 鏃惰涓轰笌 KSampler 瀹屽叏涓€鑷达紙鍚?denoise 鎴柇锛?
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
        "BSAI Qwen image 2.1 閲囨牱鍣細KSampler 鍏ㄩ儴鍙傛暟锛堢瀛?姝ユ暟/CFG/閲囨牱鍣?璋冨害鍣?闄嶅櫔锛夊潎淇濈暀涓?widget锛?
        "涓旀瘡涓弬鏁伴兘鍙彸閿€孋onvert widget to input銆嶈浆涓鸿緭鍏ョ鍙ｆ帴鍏ヤ笂娓革紙濡傚寮哄櫒 RECOMMENDED_STEPS/CFG 鏅鸿兘鑱斿姩锛夛紱"
        "鏂板鍙€?guider / sigmas 杈撳叆绔彛锛岀洿杩?BasicGuider / ViggleTurboSigmas 绛夎捀棣忛噰鏍蜂笂娓搞€俓n"
        "姝ユ暟瑙勫垯锛歴teps 濮嬬粓涓轰富鎺р€斺€斿閮?sigmas 浠呭湪姝ユ暟涓?steps 涓€鑷存椂鐢熸晥锛?
        "涓嶄竴鑷存椂蹇界暐澶栭儴 sigmas銆佹寜 steps 閲嶆柊鐢熸垚骞舵彁绀猴紙钂搁 LoRA 璇蜂繚鎸?steps 涓?LoRA/蟽 搴忓垪姝ユ暟涓€鑷达級銆?
    )

    def sample(self, model, positive, negative, latent_image,
               seed=0, steps=20, cfg=1.0, sampler_name="euler", scheduler="simple",
               denoise=1.0, guider=None, sigmas=None):
        if _comfy_samplers is None:
            raise RuntimeError("[BSAI_Qwen_Image21_Sampler] ComfyUI 閲囨牱妯″潡涓嶅彲鐢?)
        # 1) guider锛氫紭鍏堝閮?guider锛圔asicGuider / CFGGuider锛夛紝鍚﹀垯鍐呯疆 CFGGuider
        if guider is None:
            guider = _comfy_samplers.CFGGuider(model)
            guider.set_conds(positive, negative)
            guider.set_cfg(cfg)
        # 2) sigmas锛歴teps 涓轰富鎺с€傚閮?sigmas锛圴iggleTurboSigmas / ManualSigmas锛変粎鍦?
        #    鍏舵鏁颁笌 steps 涓€鑷存椂鐢熸晥锛涗笉涓€鑷存椂瑙嗕负鐢ㄦ埛涓诲姩鏀规鏁帮紝鎸?scheduler+steps+denoise
        #    閲嶆柊鐢熸垚骞舵彁绀猴紙淇濊瘉銆屾敼 steps 蹇呯敓鏁堛€嶏級銆?
        if sigmas is not None:
            sigma_steps = int(sigmas.shape[-1]) - 1
            if sigma_steps != int(steps):
                print(
                    f"[BSAI_Qwen_Image21_Sampler] 璀﹀憡: steps={int(steps)} 涓庡閮?sigmas 姝ユ暟 "
                    f"({sigma_steps}) 涓嶄竴鑷达紝宸插拷鐣ュ閮?sigmas 鎸?steps 閲嶆柊鐢熸垚銆?
                    f"钂搁 LoRA 璇蜂繚鎸?steps 涓?LoRA/蟽 搴忓垪姝ユ暟涓€鑷达紝鍚﹀垯鏁堟灉鏃犱繚璇併€?
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
        # 3) 閲囨牱鍣?
        sampler = _comfy_samplers.sampler_object(sampler_name)

        # 4) 閲囨牱涓诲惊鐜紙涓庡畼鏂?SamplerCustomAdvanced 涓€鑷达級
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
    """涓庡畼鏂?Noise_RandomNoise 绛変环鐨勬渶灏忓櫔澹板疄鐜帮紙閬垮厤璺ㄦā鍧楀鍏ワ級"""

    def __init__(self, seed):
        self.seed = seed

    def generate_noise(self, input_latent):
        latent_image = input_latent["samples"]
        batch_inds = input_latent.get("batch_index")
        return _comfy_sample.prepare_noise(latent_image, self.seed, batch_inds)


# 渚?__init__.py 娉ㄥ唽
NODE_CLASS_MAPPINGS = {
    "BSAI_Qwen_Prompt_Enhancer": BSAI_Qwen_Prompt_Enhancer,
    "BSAI_Qwen_Image21_Sampler": BSAI_Qwen_Image21_Sampler,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Qwen_Prompt_Enhancer": "BSAI Qwen Prompt Enhancer",
    "BSAI_Qwen_Image21_Sampler": "BSAI Qwen image 2.1 閲囨牱鍣?,
}
