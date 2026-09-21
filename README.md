# BSAI Qwen Prompt Enhancer

把**大白话提示词**按 **Qwen Image 2.1 官方 PE 规则**增强为高质量中文/英文提示词的 ComfyUI 插件。
一个增强节点（三种后端一键切换）+ 官方增强提示词模板库。

## 节点清单

| 节点 | 说明 |
|---|---|
| `BSAI Qwen Prompt Enhancer` | **三合一增强通道**：`backend` 下拉切换 官方PE / 本地LLaMA / API，公共参数共用，后端专属参数自动显隐，输出统一 9 路 |
| `Qwen Image 2.1 官方增强提示词模板` | 模板库：官方 PE-T2I/I2I 系统规则（逐字原文）+ 官方文档与社区搜集的增强模板，输出 system prompt |

### 合并说明（2026-09-21，v2）

原 **3 个节点**（官方PE / 本地LLaMA / API）已合并为 **1 个节点** `BSAI Qwen Prompt Enhancer`，
三个后端由 `backend` 下拉切换，前端 JS 按后端自动显隐对应参数，不再需要分别拖 3 个节点。

| 合并后参数 | 原官方PE | 原本地LLaMA | 原 API |
|---|---|---|---|
| `prompt_text` / `system_template` / `custom_system_prompt` | 同 | 同 | 同 |
| `temperature` / `top_p` / `top_k` / `seed` | 同（`top_k` 默认 20→40 统一） | 同 | 原无，新增（随请求发送，服务端不认时自动降级） |
| `max_tokens` | 原 `max_length`（8192） | 原 `max_tokens`（2048） | 原 `max_tokens`（4096）→ 统一默认 4096 |
| `repeat_penalty` | 原 `repetition_penalty`（1.0） | 原 `repeat_penalty`（1.1）→ 统一默认 1.1 | 原无 |
| `speed_preset` + `RECOMMENDED_*` 输出 | 同 | 同 | 原无，新增（增强后端无关，照常输出采样建议） |
| 后端专属 | `clip` 输入、`pe_mode`、`min_p`、`thinking`、`mtp` | `llm_model_name`、`mmproj_name`、`chat_handler`、`n_ctx`、`n_gpu_layers`、`load_mtp`、`keep_loaded` | `api_base`、`api_key`、`api_model_name`、`timeout` |

> ⚠️ **旧工作流兼容**：旧节点类名（`BSAI_Qwen_Prompt_Enhancer_OfficialPE` / `_LocalLlama` / `_API`）已移除。
> 引用旧节点的已存工作流打开后会出现"未知节点"，需删除旧节点、重新添加 `BSAI Qwen Prompt Enhancer`
> 并选择对应 backend 后重连（官方PE 的 clip/image 端口顺序不变，替换后可直接接线；
> 本地LLaMA 旧工作流的 image 端口因新增了 clip 端口会错位，需重连 image 线）。

## 官方增强方式（调研结论）

| 方式 | 模型/资源 | 本地化 |
|---|---|---|
| ① 本地官方 PE | `Qwen/Qwen-Image-2.1-PE-T2I`（文生图）、`Qwen/Qwen-Image-2.1-PE-I2I`（图生图编辑），均为 Qwen3.5-VL 9B 微调 | ✅ 本插件支持 |
| ② 本地 LLaMA | 本地 Qwen 视觉大模型 + mmproj | ✅ 本插件支持 |
| ③ API | 在线大模型（如阿里云百炼） | ✅ 本插件支持 |
| ④ 云端 prompt_extend | 阿里云/千问 Cloud API 服务端能力（`prompt_extend` 默认开启），**无本地权重** | ⚠️ 仅服务端，本插件 API 通道可间接复用其在线模型 |

> 官方开源仅上述 T2I / I2I 两个 PE 权重（外加云端 prompt_extend）。无其他官方增强方式。

## 官方 PE 后端用法（backend = 官方PE）

1. 将 PE 权重放入 `ComfyUI/models/text_encoders/`（相对路径，任意盘符均可）：
   - `Qwen image 2.1 PE/qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors`（文生图）
   - `Qwen image 2.1 PE/qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors`（图生图）
2. 添加 `CLIPLoader`，选择上述 PE 文件（type 选 `qwen_image` 或任意值均可，ComfyUI 0.37 自动检测为 `QWEN35_9B` 生成式 LLM）。
3. 把 CLIPLoader 的 `CLIP` 接到 `BSAI Qwen Prompt Enhancer` 的 `clip` 输入（backend 保持"官方PE"）。
4. 填大白话 → 运行 → 得到 `ENHANCED_PROMPT`（可直接接 KSampler positive）。

**重要**：需要 ComfyUI **0.37.0 及以上**（磁盘代码 v0.37.0-4 已具备，重启 ComfyUI 生效）。

### I2I（图生图/编辑）

- `pe_mode` 选 `I2I`（或 `auto` 并接入 images），把参考图接入 `image_1`~`image_16`（可多张）。
- 提示词中用 `图1`、`图2`… 指代各图（官方规则要求），例如：`把图1的女孩放进图2的场景，换成图3的服装`。
- 官方规则要求：只描述要改的属性，未点名属性一律保真不保强度。

### 采样参数（官方建议值）

| 参数 | 官方建议 |
|---|---|
| max_tokens | T2I 建议 16256，I2I 建议 24000（插件默认 4096 可生成完整 JSON） |
| temperature | 1.0 |
| top_p | 0.95 |
| top_k | 20 |
| thinking | True（官方 enable_thinking=True，模型先思考再输出 JSON） |

## 本地 LLaMA 后端（backend = 本地LLaMA）

- 自动扫描 `ComfyUI/models/LLM` 与 `ComfyUI/models/text_encoders` 下的 `*.gguf`（相对路径）。
- `llm_model_name` 选 Qwen 视觉模型（如 `Qwen3VL-8B-...-Q8_0.gguf`），`mmproj_name` 自动配对同名 mmproj。
- **chat_handler 自动识别全系列最新模型**（auto）：
  - Qwen 系：Qwen 3.8 / 3.6 → `Qwen35ChatHandler`；Qwen 3.5 → `Qwen35ChatHandler`；Qwen 3 → `Qwen3VLChatHandler`；Qwen 2.5/2 VL → `Qwen25VLChatHandler`
  - Gemma 系：Gemma 4 → `Gemma4ChatHandler`；Gemma 3 → `Gemma3ChatHandler`
  - 其他：GLM-4.6V / GLM-4.1V、MiniCPM-V4.5/V2.6、LFM2.5V / LFM2V、Step3V 等
  - 下拉框动态列出 llama.cpp 当前实际可用的全部 ChatHandler，可手动覆盖
- 接入 `image_1`~`image_16`（最多 16 张，与官方 TextEncodeQwenImage21 一致）可多图识别（base64 内联）。

## API 后端（backend = API）

- `api_base`：OpenAI 兼容地址，例如 `https://dashscope.aliyuncs.com/compatible-mode/v1` 或本地 `http://127.0.0.1:8000/v1`。
- `api_key`：在线服务必填。
- `api_model_name`：如 `qwen3.5-vl-9b` / `qwen-plus` 等。
- 请求会带上 `top_p` / `top_k` / `seed`；若服务端不认这些扩展采样参数（HTTP 400），节点自动降级为
  `model + messages + temperature + max_tokens` 的最小 payload 重试一次。
- 接入 `image_1`~`image_16`（最多 16 张，与官方 TextEncodeQwenImage21 一致）支持多图（base64 内联）。

## 模板库

`Qwen Image 2.1 官方增强提示词模板` 节点内置 **18 个模板**：

- **官方权威**：PE-T2I 系统规则（10KB 原文）、PE-I2I 系统规则（18KB 原文）
- **官方文档**：API prompt_extend 改写风格（含 orig→actual 示例）、官方 Prompt 公式（主体+场景+风格+镜头+氛围+细节）、官方海报/幻灯片布局模板
- **社区最佳实践**：Tensor.Art 六要素模板、Qwen-Image-Lightning 中文技巧、风格混合模板、细节控制模板
- **设计模板（9 类，支持自定义变量）**：
  - 短视频封面（9:16）、杂志封面（2:3）、书籍封面（2:3）、桌面壁纸（16:9）
  - 海报设计（2:3）、杂志内页跨页（3:2）、宣传册封面（3:2）、宣传册内页（3:2）、户外广告看板（21:9）
- **电影资产模板（13 类，支持自定义变量）**：
  - 分镜类：电影剧照（16:9 单帧）、电影分镜板（3x2 带标注）、4/6/9/12 宫格分镜
  - 角色资产：三视图（正/侧/背）、四视图（正/3-4/侧/背）、六视图（全身+头部特写）
  - 道具资产：三视图、四视图、六视图（含细节特写）
  - 场景资产：场景概念图（空间结构+透视+时间天气+光线）

### 设计模板用法（自定义变量替换）

设计模板内置 `{{TITLE}}` `{{SUBTITLE}}` `{{BRAND}}` `{{MAIN_SUBJECT}}` `{{COLOR}}` `{{STYLE}}` 等占位符。
在节点的 **variables** 输入框按 `KEY: value` 逐行填写自己的内容，节点自动替换并输出完整 SYSTEM_PROMPT：

```
TITLE: 夏日新品发布会
SUBTITLE: 2026 秋季系列
BRAND: BSAI
MAIN_SUBJECT: 一个穿红裙的女孩站在樱花树下
COLOR: 深蓝+橙金
STYLE: 商业摄影
```

- 变量 key 不区分大小写，支持中文冒号 `：`
- 第 4 个输出 `USED_VARS` 报告实际替换了哪些 key、哪些未填
- 输出的 SYSTEM_PROMPT 接入增强节点的 `system_template`，按模板规则把变量写成完整出图描述 → 接 TextEncodeQwenImage21 → 出图
- 若需用自己的照片作主视觉，把图片接到增强节点的 `image_1` 输入，模板规则已内置"图1作为主视觉"说明

模板输出可直接接入增强节点的 `system_template`，或单独查看复制。

## 目录结构

```
BSAI_Qwen_Prompt_Enhancer/
├── __init__.py                  # 注册 2 个节点（合并增强节点 + 模板库节点）
├── common.py                    # 官方规则加载/消息构造/输出解析/图片转换
├── nodes_enhancer.py            # 三合一增强节点（官方PE / 本地LLaMA / API）
├── nodes_template.py            # 模板库节点
├── system_prompts/              # 官方 PE-T2I/I2I system_prompt.txt（逐字原文）
├── templates/templates.json     # 模板库
├── e2e_test*.py / verify_import.py  # 验证脚本（可删除）
└── README.md
```

## 验证记录（2026-09-21 v2）

- 三合一节点 `verify_import.py` 全部通过：backend 下拉、9 路输出、API payload（含 top_k/seed）、API 400 自动降级最小 payload、未知 backend 报错 ✅
- 旧版验证（v1，合并前）：`detect_te_model` 对两个 PE 文件均返回 `TEModel.QWEN35_9B` ✅
- 端到端 T2I 真实生成：模型按官方 8 步规则思考，输出完整 JSON `{"rewritten_prompt": ..., "wh_ratio": ...}` ✅

