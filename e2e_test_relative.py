# -*- coding: utf-8 -*-
"""
复现验证脚本（相对路径读取，无硬编码盘符）：
用 ComfyUI 0.37 CLIPLoader 体系加载本地 PE 模型（text_encoders 目录，相对路径），
走 BSAI_Qwen_Prompt_Enhancer 合并节点（backend=官方PE）做真实提示词增强。
用法: <ComfyUI-python> e2e_test_relative.py <T2I|I2I>
"""
import sys
import os
import time

sys.path.insert(0, r'C:\BSAI\ComfyUI-BSAI_pro_v40\ComfyUI')

import folder_paths
import comfy.sd as sd
from comfy.sd import CLIPType

from custom_nodes.BSAI_Qwen_Prompt_Enhancer.nodes_enhancer import (
    BSAI_Qwen_Prompt_Enhancer, BACKEND_PE,
)

def find_pe(name):
    """在 text_encoders 目录树中按文件名定位（相对路径）"""
    for d in folder_paths.get_folder_paths("text_encoders"):
        for root, _, files in os.walk(d):
            if name in files:
                return os.path.join(root, name)
    raise RuntimeError("未找到 PE 模型: %s" % name)

def main():
    mode = sys.argv[1].upper() if len(sys.argv) > 1 else "T2I"
    pe_file = ("qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors" if mode == "T2I"
               else "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors")
    path = find_pe(pe_file)
    print(">>> PE 模型:", path, flush=True)

    t0 = time.time()
    clip = sd.load_clip(
        ckpt_paths=[path],
        embedding_directory=folder_paths.get_folder_paths("embeddings"),
        clip_type=CLIPType.QWEN_IMAGE,
    )
    print(">>> 加载完成 %.1fs" % (time.time() - t0), flush=True)

    node = BSAI_Qwen_Prompt_Enhancer()
    t1 = time.time()
    out = node.enhance(
        backend=BACKEND_PE,
        clip=clip,
        prompt_text="一个穿红裙的女孩站在樱花树下，手里拿着奶茶，傍晚阳光",
        pe_mode="auto",
        system_template=("Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]" if mode == "T2I"
                         else "Qwen-Image-2.1 官方 PE-I2I 系统规则 [official_i2i]"),
        custom_system_prompt="",
        max_tokens=4096, temperature=1.0, top_p=0.95, top_k=20,
        repeat_penalty=1.0, min_p=0.0, seed=42, thinking=True, mtp="auto",
    )
    enhanced, wh_ratio, ratio_follow, raw, thinking = out["result"][:5]
    print()
    print("=" * 70)
    print("模式: %s  耗时: %.1fs" % (mode, time.time() - t1))
    print("WH_RATIO:", repr(wh_ratio))
    print("ENHANCED_PROMPT 长度:", len(enhanced))
    print("ENHANCED_PROMPT:", enhanced[:400], "...")
    print("=" * 70)
    print("PASS" if wh_ratio else "FAIL")

if __name__ == "__main__":
    main()
