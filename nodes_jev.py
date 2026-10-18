# -*- coding: utf-8 -*-
"""
BSAI_Qwen_Prompt_Enhancer — Jev 结构化并行决策节点 (新增)

把 ComfyUI-llama-cpp_vlm 的 Jev 模式 (结构化并行决策: 不写 JSON、只读 logits、
一次前向遍历返回全部字段的值+置信度, 不可能产生幻觉) 以独立副本形式接入本插件。

- Jev 引擎 (jev_mode.py) 与本插件解耦: 复用本插件 `_load_llm` 本地 LLaMA 加载通道
  (含 MTP 自动剥离 / handler 自动识别 / 模型缓存), 因此与主节点 "本地LLaMA" 后端
  使用完全一致的模型选择体验。
- 用法:
    1. BSAI_Jev_Schema:  定义字段与合法选项, 每行 `字段名: 选项1|选项2|选项3`
    2. BSAI_Jev_Decision: 选模型 + 填 context, 一次遍历返回所有字段的值与置信度
- 输出:
    result_json       {"字段": "值", ...}
    confidence_json   {"字段": {"value":..., "confidence":..., "scores":{...}}}
    text              人类可读摘要
"""
import folder_paths  # noqa: F401  (确保 ComfyUI 环境已初始化)

from .jev_mode import (
    parse_schema, JevRunner, build_prefix,
    results_to_json, results_to_confidence_json, results_to_text,
)
from .nodes_enhancer import (
    _scan_gguf, _auto_pair_mmproj, _chat_handler_labels,
    _load_llm, _clear_cache, _AUTO_LABEL,
)

NO_MODEL = "<No GGUF model found>"


class BSAI_Jev_Schema:
    """Jev 结构化决策 Schema 构建器。
    每行一个字段: 字段名: 选项1|选项2|选项3
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "schema_text": ("STRING", {
                    "multiline": True,
                    "default": "department: tech|billing|shipping\npriority: low|medium|high\nsentiment: positive|negative|neutral",
                    "placeholder": "One field per line:\nfield_name: option1|option2|option3",
                }),
                "instruction": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "Optional: field-selection rules for the model.\ne.g.: You are a support ticket router. Classify each field strictly based on the context. Only output valid options, never invent values.",
                }),
            },
        }

    RETURN_TYPES = ("JEVSCHEMA",)
    RETURN_NAMES = ("jev_schema",)
    FUNCTION = "build"
    CATEGORY = "BSAI/Qwen Image 2.1"

    def build(self, schema_text, instruction):
        fields = parse_schema(schema_text)
        return ({"fields": fields, "instruction": instruction, "schema_text": schema_text},)


class BSAI_Jev_Decision:
    """Jev 并行结构化决策: 一次遍历返回全部字段的值与置信度分数。
    模型只能从 Schema 的合法选项中取值, 不可能产生幻觉。
    """
    @staticmethod
    def VALIDATE_INPUTS(*args, **kwargs):
        # 与主节点一致: 新旧两代 ComfyUI 校验语义兼容, 放行 combo 校验
        if not kwargs and len(args) == 2:
            return None
        return True

    @classmethod
    def INPUT_TYPES(cls):
        models, mmprojs = _scan_gguf()
        return {
            "required": {
                "jev_schema": ("JEVSCHEMA",),
                "context": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "Context / customer info / email body\n(when batch_mode is on, each line is an independent record; one forward pass decides all fields for each record)",
                }),
                "batch_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "True: split context by line into multiple records; one forward pass decides all fields per record\n(records processed in order; fields are decided in parallel within a single forward pass)",
                }),
                # ---- model selection (identical to the main node's Local LLaMA backend) ----
                "llm_model_name": ((models if models else [NO_MODEL]), {
                    "default": models[0] if models else NO_MODEL,
                }),
                "mmproj_name": ([""] + mmprojs, {
                    "default": _auto_pair_mmproj(models[0], mmprojs) if models else "",
                }),
                "chat_handler": (_chat_handler_labels(), {"default": _AUTO_LABEL}),
                "n_ctx": ("INT", {"default": 8192, "min": 512, "max": 65536}),
                "n_gpu_layers": ("INT", {"default": -1, "min": -1, "max": 200}),
                "load_mtp": ("BOOLEAN", {"default": False}),
                # ---- 极限提速参数（视频同款 llama.cpp：显存+内存混合模式）----
                "n_cmoe": ("INT", {
                    "default": 0, "min": 0, "max": 256, "step": 1,
                    "tooltip": "Split MoE experts across CPU/RAM layers (-ncmoe). Only effective for MoE models, not dense.\\nQwen-35B-A3B is most stable around 24; 0 = off. Current 0.3.36 does not support it yet; it applies automatically after upgrading.",
                }),
                "kv_cache_quant": (["auto (f16, no quant)", "q8_0", "q4_0"], {
                    "default": "auto (f16, no quant)",
                    "tooltip": "KV cache quantization (-ctk/-ctv). Jev reads logits and is quality-sensitive, so it defaults to no quantization; pick q8_0/q4_0 only if you need the speedup.",
                }),
                "use_mmap": ("BOOLEAN", {"default": True, "tooltip": "use_mmap; can disable when RAM is tight / swapping (--no-mmap)."}),
                "use_mlock": ("BOOLEAN", {"default": False, "tooltip": "use_mlock (--mlock) locks the model in RAM to avoid page-out."}),
                "flash_attn": (["auto", "on", "off"], {"default": "auto", "tooltip": "-fa. auto = enable when the model supports it."}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1, "tooltip": "-t thread count (video example: 14); 0 = auto."}),
                "system_prompt": ("STRING", {"multiline": True, "default": ""}),
                "force_offload": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Unload all cached local LLMs after inference.",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("result_json", "confidence_json", "text")
    FUNCTION = "process"
    CATEGORY = "BSAI/Qwen Image 2.1"

    def process(self, jev_schema, context, batch_mode, llm_model_name, mmproj_name,
                chat_handler, n_ctx, n_gpu_layers, load_mtp,
                n_cmoe=0, kv_cache_quant="auto (f16, no quant)", use_mmap=True, use_mlock=False,
                flash_attn="auto", threads=0,
                system_prompt="", force_offload=False):
        if llm_model_name == NO_MODEL:
            raise RuntimeError(
                "[BSAI_Jev] No GGUF model found. Please put a .gguf model into ComfyUI/models/LLM first."
            )

        llm, _ = _load_llm(
            llm_model_name, mmproj_name or None, chat_handler,
            n_ctx, n_gpu_layers, load_mtp,
            n_cmoe=int(n_cmoe or 0),
            kv_cache_quant=str(kv_cache_quant).split("(")[0].strip(),
            use_mmap=bool(use_mmap),
            use_mlock=bool(use_mlock),
            flash_attn=str(flash_attn).strip(),
            threads=int(threads or 0),
        )

        # Jev 是独立会话: 从干净 KV 缓存开始
        llm.reset()
        try:
            if llm._ctx is not None:
                llm._ctx.memory_clear(True)
        except Exception:
            pass

        fields = jev_schema["fields"]
        instruction = jev_schema.get("instruction", "")
        prefix = build_prefix(system_prompt, instruction, fields)

        if batch_mode:
            records = [f"Context:\n{ln.strip()}\n" for ln in context.splitlines() if ln.strip()]
        else:
            records = [f"Context:\n{context.strip()}\n"]

        runner = JevRunner(llm)
        results = runner.run(prefix, fields, records)

        # 恢复干净状态: 不污染后续会话
        try:
            llm.reset()
            if llm._ctx is not None:
                llm._ctx.memory_clear(True)
        except Exception:
            pass

        if force_offload:
            _clear_cache()

        return (
            results_to_json(results),
            results_to_confidence_json(results),
            results_to_text(results, fields),
        )


NODE_CLASS_MAPPINGS = {
    "BSAI_Jev_Schema": BSAI_Jev_Schema,
    "BSAI_Jev_Decision": BSAI_Jev_Decision,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_Jev_Schema": "BSAI Jev Schema Builder",
    "BSAI_Jev_Decision": "BSAI Jev Structured Decision",
}
