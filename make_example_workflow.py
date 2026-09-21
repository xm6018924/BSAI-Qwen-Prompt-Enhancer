# -*- coding: utf-8 -*-
"""生成示例工作流: BSAI Qwen Prompt Enhancer + Qwen-Image-2.1 文生图"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "examples", "BSAI-Qwen-Image-2.1-Prompt-Enhancer-示例工作流.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# 用 0.37 磁盘上的 TextEncodeQwenImage21 真实定义（prompt 为 widget，不可连线）
N = 0
LINKS = []


def nid():
    global N
    N += 1
    return N


def loader_node(ntype, x, y, title, widgets, ctype=None, wtype=None):
    node = {
        "id": nid(), "type": ntype, "pos": [x, y], "size": [420, 118],
        "flags": {}, "order": 0, "mode": 0,
        "inputs": [
            {"name": "unet_name", "type": "COMBO", "widget": {"name": "unet_name"}, "link": None},
        ] if ntype == "UNETLoader" else (
            [{"name": "clip_name", "type": "COMBO", "widget": {"name": "clip_name"}, "link": None},
             {"name": "type", "type": "COMBO", "widget": {"name": "type"}, "link": None},
             {"name": "device", "shape": 7, "type": "COMBO", "widget": {"name": "device"}, "link": None}]
            if ntype == "CLIPLoader" else
            [{"name": "vae_name", "type": "COMBO", "widget": {"name": "vae_name"}, "link": None}]
        ),
        "outputs": [
            {"name": "MODEL", "type": "MODEL", "slot_index": 0, "links": []}
        ] if ntype == "UNETLoader" else (
            [{"name": "CLIP", "type": "CLIP", "slot_index": 0, "links": []}]
            if ntype == "CLIPLoader" else
            [{"name": "VAE", "type": "VAE", "slot_index": 0, "links": []}]
        ),
        "title": title, "properties": {"Node name for S&R": ntype},
        "widgets_values": widgets,
    }
    return node


nodes = []

# ---------- Group A: 官方 PE 增强（合并节点，backend=官方PE）----------
pe_clip = loader_node("CLIPLoader", -1400, -120, "加载官方 PE 模型 (T2I)",
                      ["qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors", "qwen_image", "default"])
# BSAI 三合一增强节点（官方PE/本地LLaMA/API 由 backend 切换）
pe_node = {
    "id": nid(), "type": "BSAI_Qwen_Prompt_Enhancer",
    "pos": [-900, -160], "size": [500, 560], "flags": {}, "order": 1, "mode": 0,
    "inputs": [
        {"name": "clip", "type": "CLIP", "link": None},
    ],
    "outputs": [
        {"name": "ENHANCED_PROMPT", "type": "STRING", "slot_index": 0, "links": []},
        {"name": "WH_RATIO", "type": "STRING", "slot_index": 1, "links": []},
        {"name": "RATIO_FOLLOW", "type": "STRING", "slot_index": 2, "links": []},
        {"name": "RAW_OUTPUT", "type": "STRING", "slot_index": 3, "links": []},
        {"name": "THINKING", "type": "STRING", "slot_index": 4, "links": []},
        {"name": "RECOMMENDED_STEPS", "type": "INT", "slot_index": 5, "links": []},
        {"name": "RECOMMENDED_CFG", "type": "FLOAT", "slot_index": 6, "links": []},
        {"name": "RECOMMENDED_SAMPLER", "type": "STRING", "slot_index": 7, "links": []},
        {"name": "RECOMMENDED_SCHEDULER", "type": "STRING", "slot_index": 8, "links": []},
    ],
    "title": "BSAI Qwen Prompt Enhancer",
    "properties": {"Node name for S&R": "BSAI_Qwen_Prompt_Enhancer"},
    # widgets 顺序与 nodes_enhancer.py INPUT_TYPES 完全一致
    "widgets_values": [
        "官方PE (本地 Qwen3.5-9B)",
        "一个穿红裙的女孩站在樱花树下，手里拿着奶茶，傍晚阳光",
        "Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]", "",
        1.0, 0.95, 20, 1.0, 42, 8192,
        "标准质量 20步/CFG3 (推荐, 7B原生)",
        "auto", 0.0, True, "auto",
        "<未发现 GGUF>", "",
        "auto（按模型名自动识别 Qwen3.8/Gemma4/GLM4.6 等全部支持模型）",
        8192, -1, False, True,
        "https://dashscope.aliyuncs.com/compatible-mode/v1", "",
        "qwen3.5-vl-9b", 120,
    ],
}
tpl_node = {
    "id": nid(), "type": "QwenImage21_Prompt_Template",
    "pos": [-900, 520], "size": [420, 110], "flags": {}, "order": 2, "mode": 0,
    "inputs": [], "outputs": [
        {"name": "SYSTEM_PROMPT", "type": "STRING", "slot_index": 0, "links": []},
        {"name": "TEMPLATE_ID", "type": "STRING", "slot_index": 1, "links": []},
        {"name": "DESCRIPTION", "type": "STRING", "slot_index": 2, "links": []},
    ],
    "title": "Qwen Image 2.1 官方增强提示词模板",
    "properties": {"Node name for S&R": "QwenImage21_Prompt_Template"},
    "widgets_values": ["Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]", ""],
}
nodes += [pe_clip, pe_node, tpl_node]

# ---------- Group B: Qwen-Image-2.1 文生图 ----------
unet = loader_node("UNETLoader", 0, -160, "加载 Qwen-Image-2.1 扩散模型",
                   ["BSAI-Qwen-Image-2.1-bf16.safetensors", "default"])
te = loader_node("CLIPLoader", 0, 40, "加载文本编码器 (Qwen3-VL-8B)",
                 ["BSAI-Qwen-Image-2.1-TE.safetensors", "qwen_image", "default"])
vae = loader_node("VAELoader", 0, 240, "加载 VAE",
                  ["BSAI-Qwen-Image-2.1-VAE.safetensors"])
cache = {
    "id": nid(), "type": "QwenImage21Cache", "pos": [480, -160], "size": [420, 150],
    "flags": {}, "order": 3, "mode": 0,
    "inputs": [{"name": "model", "type": "MODEL", "link": None},
               {"name": "device", "type": "COMBO", "widget": {"name": "device"}, "link": None},
               {"name": "dtype", "type": "COMBO", "widget": {"name": "dtype"}, "link": None}],
    "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0, "links": []}],
    "title": "KV 缓存优化 (Qwen Image 2.1 Cache)",
    "properties": {"Node name for S&R": "QwenImage21Cache"},
    "widgets_values": ["auto", "default"],
}
# 增强结果作为示例预填（来自真实生成的 wh_ratio=2:3 输出）
EXAMPLE_ENHANCED = (
    "A vertical, realistic portrait photograph shows a young adult woman of East Asian appearance "
    "standing beneath a mature cherry blossom tree during golden-hour sunset. The upper portion of the "
    "image is filled with dense clusters of pale pink and soft white cherry blossoms, their thin dark "
    "branches spreading diagonally across the frame from the thick, rough-barked tree trunk on the right. "
    "The blossoms form a luminous canopy, with warm sunlight filtering through them and creating glowing "
    "highlights, soft bokeh, and gentle lens flare against a peach, amber, and lavender evening sky. The "
    "tree trunk occupies much of the upper-right and right-center area, with rugged dark brown bark "
    "catching orange rim light along its ridges. In the left and central foreground, the woman is shown "
    "from roughly mid-thigh upward in a three-quarter back view, leaning close to the tree trunk with her "
    "body turned slightly away and her head turned back toward the camera. She has dark wavy hair, wears a "
    "sleeveless red dress with thin straps, a fitted bodice, and a light skirt moving in the breeze, plus "
    "small silver jewelry that catches the sunset highlights. In her right hand near her shoulder she holds "
    "a clear cup of milk tea with a visible straw, beige drink, and simple label. Around her, a wooden "
    "railing runs along the lower left, a river and a bridge appear behind the park, park trees and "
    "streetlamps stand in the distance, and scattered petals cover the ground. Near the lower right, a "
    "small chalkboard-style sign reads, in white handwritten-style lettering, \"Cherry Blossom\" on the "
    "upper line and \"Sunset\" on the lower line, with a small pink blossom drawing below the text. A low "
    "evening sun from the right backlights the woman, blossoms, railing, and tree bark, casting gentle "
    "shadows across the path while hair, shoulders, petals, and cup edges catch golden highlights, with "
    "soft haze in the distance. Cinematic and romantic, with deep red fabric against pale blossoms, dark "
    "bark, warm gold sky, and muted greenery, warm color grading, natural backlighting, and a "
    "lifestyle-fashion portrait composition centered on the contrast between the red dress, the dark tree "
    "trunk, the pale blossoms, and the glowing sunset."
)
encode = {
    "id": nid(), "type": "TextEncodeQwenImage21", "pos": [960, -120], "size": [560, 460],
    "flags": {}, "order": 4, "mode": 0,
    "inputs": [
        {"name": "clip", "type": "CLIP", "link": None},
        {"name": "vae", "shape": 7, "type": "VAE", "link": None},
    ],
    "outputs": [
        {"name": "positive", "type": "CONDITIONING", "slot_index": 0, "links": []},
        {"name": "negative", "type": "CONDITIONING", "slot_index": 1, "links": []},
        {"name": "latent", "type": "LATENT", "slot_index": 2, "links": []},
    ],
    "title": "Qwen Image 2.1 提示词编码",
    "properties": {"Node name for S&R": "TextEncodeQwenImage21"},
    "widgets_values": [
        EXAMPLE_ENHANCED,
        "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，文字模糊扭曲，构图混乱",
        1024,
    ],
}
sampler = {
    "id": nid(), "type": "KSampler", "pos": [1580, -120], "size": [320, 474],
    "flags": {}, "order": 5, "mode": 0,
    "inputs": [
        {"name": "model", "type": "MODEL", "link": None},
        {"name": "positive", "type": "CONDITIONING", "link": None},
        {"name": "negative", "type": "CONDITIONING", "link": None},
        {"name": "latent_image", "type": "LATENT", "link": None},
    ],
    "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0, "links": []}],
    "properties": {"Node name for S&R": "KSampler"},
    "widgets_values": [921885725034473, "randomize", 50, 4, "euler", "simple", 1],
}
decode = {
    "id": nid(), "type": "VAEDecode", "pos": [1960, -120], "size": [210, 60],
    "flags": {"collapsed": False}, "order": 6, "mode": 0,
    "inputs": [{"name": "samples", "type": "LATENT", "link": None},
               {"name": "vae", "type": "VAE", "link": None}],
    "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0, "links": []}],
    "properties": {"Node name for S&R": "VAEDecode"},
    "widgets_values": [],
}
save = {
    "id": nid(), "type": "SaveImage", "pos": [2200, -120], "size": [480, 440],
    "flags": {}, "order": 7, "mode": 0,
    "inputs": [{"name": "images", "type": "IMAGE", "link": None},
               {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}, "link": None}],
    "outputs": [],
    "properties": {"Node name for S&R": "SaveImage"},
    "widgets_values": ["Qwen-Image-2.1-PE增强"],
}
empty = {
    "id": nid(), "type": "EmptySD3LatentImage", "pos": [1960, 400], "size": [300, 106],
    "flags": {}, "order": 8, "mode": 0, "inputs": [], "outputs": [],
    "properties": {"Node name for S&R": "EmptySD3LatentImage"},
    "widgets_values": [1024, 1024, 1],
}
nodes += [unet, te, vae, cache, encode, sampler, decode, save, empty]

# 连线
def link(lnk_id, src_id, src_out, dst_id, dst_in, dtype):
    LINKS.append([lnk_id, src_id, src_out, dst_id, dst_in, dtype])
    nodes[src_id - 1]["outputs"][src_out]["links"].append(lnk_id)
    nodes[dst_id - 1]["inputs"][dst_in]["link"] = lnk_id


L = 0
# A: PE CLIP -> 增强节点
L += 1; link(L, pe_clip["id"], 0, pe_node["id"], 0, "CLIP")
# B: 生成链
L += 1; link(L, unet["id"], 0, cache["id"], 0, "MODEL")
L += 1; link(L, cache["id"], 0, sampler["id"], 0, "MODEL")
L += 1; link(L, te["id"], 0, encode["id"], 0, "CLIP")
L += 1; link(L, vae["id"], 0, encode["id"], 1, "VAE")
L += 1; link(L, vae["id"], 0, decode["id"], 1, "VAE")
L += 1; link(L, encode["id"], 0, sampler["id"], 1, "CONDITIONING")
L += 1; link(L, encode["id"], 1, sampler["id"], 2, "CONDITIONING")
L += 1; link(L, encode["id"], 2, sampler["id"], 3, "LATENT")
L += 1; link(L, sampler["id"], 0, decode["id"], 0, "LATENT")
L += 1; link(L, decode["id"], 0, save["id"], 0, "IMAGE")

# 节点排序（按依赖）
order_map = {}
for i, nd in enumerate(nodes):
    order_map[nd["id"]] = i
nodes.sort(key=lambda nd: order_map[nd["id"]])

workflow = {
    "id": "bsai-qwen-2.1-prompt-enhancer-example",
    "revision": 0,
    "last_node_id": N,
    "last_link_id": L,
    "nodes": nodes,
    "links": LINKS,
    "groups": [
        {"id": 1, "title": "① 提示词增强（合并节点 backend=官方PE，输出 ENHANCED_PROMPT，可复制到生成链或右键 TextEncode 的 prompt 转为输入后接线）",
         "bounding": [-1480, -260, 1100, 900], "color": "#7a9e3f", "flags": {}},
        {"id": 2, "title": "② Qwen-Image-2.1 文生图（加载增强后的提示词）",
         "bounding": [-80, -280, 2730, 880], "color": "#3f789e", "flags": {}},
    ],
    "config": {},
    "extra": {"ds": {"scale": 0.8, "offset": [300, 120]}},
    "version": 0.4,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=1)
print("工作流已生成:", OUT)
print("节点数:", len(nodes), "连线数:", L)
