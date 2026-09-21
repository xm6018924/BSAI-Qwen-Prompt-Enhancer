# BSAI Qwen Prompt Enhancer

> A ComfyUI plugin for **prompt enhancement and image interrogation** powered by the Qwen family of large language models.
> Enhance plain-language prompts into high-quality image generation prompts using official rules, or interrogate images with multimodal models.
> Three backends in one node: **Official PE / Local LLaMA / API**.

[中文版](README.md) | **English**

## ✨ Features

### 🔥 Full Qwen Family Model Support

The **Local LLaMA backend** supports the entire Qwen family of multimodal models for local inference and image interrogation:

| Model Series | Chat Handler | Notes |
|---|---|---|
| **Qwen 3.8-VL** | `Qwen35ChatHandler` | Latest flagship multimodal, 27B / 7B variants |
| **Qwen 3.6-VL** | `Qwen35ChatHandler` | High-efficiency multimodal with MTP acceleration |
| **Qwen 3.5-VL** | `Qwen35ChatHandler` | 9B / 72B variants, base of Official PE |
| **Qwen 3-VL** | `Qwen3VLChatHandler` | 3rd gen multimodal |
| **Qwen 2.5-VL** / **Qwen 2-VL** | `Qwen25VLChatHandler` | Classic multimodal series |

Also compatible with other popular multimodal models:
- **Gemma 4** / **Gemma 3** — `Gemma4ChatHandler`
- **GLM-4.6V / 4.1V** — generic mtmd handler
- **MiniCPM-V4.5 / V2.6** — dedicated handler
- **LFM 2.5V / 2V** — generic mtmd handler
- **Step 3V** — generic mtmd handler
- **LLaVA 1.5 / 1.6** — dedicated handler
- And more models supported by llama-cpp-python

> 💡 **Auto-detection**: set `chat_handler` to `auto` and the plugin automatically matches the correct handler based on model name — works out of the box.

### 🎯 Three Backends

| Backend | Highlights | Use Case |
|---|---|---|
| **Official PE** | Local Qwen Image 2.1 PE weights, 8-step official enhancement rules | Best official quality, GPU capable of running PE |
| **Local LLaMA** | Local GGUF + mmproj, full Qwen multimodal family support | Offline use, image interrogation, custom models |
| **API** | OpenAI-compatible interface (e.g. Alibaba DashScope) | Online service, no local VRAM needed |

### 📚 Built-in Template Library

18 enhancement templates ready to use:
- **Official Authoritative**: PE-T2I / PE-I2I system rules (verbatim original)
- **Official Formulas**: Prompt formula, poster layout templates, prompt_extend rewrite style
- **Community Best Practices**: Six-element template, Lightning Chinese tips, style mixing, detail control
- **Design Templates (9 types)**: Short video cover, magazine/book cover, desktop wallpaper, poster, brochure, outdoor billboard
- **Cinema Asset Templates (13 types)**: Film stills, storyboards, character 3-view/4-view/6-view, prop 3-view, scene concept art

## 📦 Installation

1. Place this plugin in `ComfyUI/custom_nodes/`:
   ```
   ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer/
   ```

2. **Dependencies**:
   - **Official PE backend**: ComfyUI 0.37.0+ (built-in Qwen Image 2.1 PE support)
   - **Local LLaMA backend**: requires `llama-cpp-python` (recommend 0.3.36+ for full Qwen 3.5/3.6/3.8 support)
     ```bash
     pip install llama-cpp-python
     ```
   - **API backend**: no extra dependencies

3. Restart ComfyUI

## 🚀 Usage

### Method 1: Official PE Backend (T2I / I2I Enhancement)

1. Place PE weights in `ComfyUI/models/text_encoders/`:
   - `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` (text-to-image)
   - `qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors` (image-to-image)

2. Load PE weights with `CLIPLoader`, connect to the node's `clip` input
3. Set `backend` to `Official PE`, enter your prompt → run

### Method 2: Local LLaMA Backend (Full Qwen Family Interrogation / Enhancement)

1. Place GGUF model and mmproj projector in `ComfyUI/models/LLM/` (**relative path**):
   ```
   ComfyUI/models/LLM/
   ├── Qwen3.8-27B-Instruct-Q6_K_L.gguf
   └── Qwen3.8/
       └── Qwen3.8-27B-f16_mmproj.gguf
   ```

2. Add the `BSAI Qwen Prompt Enhancer` node:
   - Set `backend` to `Local LLaMA (GGUF + mmproj)`
   - Select main model GGUF from `llm_model_name` dropdown
   - Select corresponding mmproj from `mmproj_name` (required for multimodal interrogation)
   - Set `chat_handler` to `auto` (auto-matches Qwen series dedicated handler)
   - Connect `image_1` ~ `image_16` for image interrogation (up to 16 images)

3. Run to get enhanced prompts or image interrogation descriptions

> 💡 **Automatic MTP handling**: Models with MTP/NextN prediction layers (e.g. Qwen 3.6/3.8 CRACK versions) are automatically detected and stripped (`-noMTP.gguf`), compatible with all versions of llama-cpp-python.

### Method 3: API Backend

1. Set `backend` to `API`
2. Fill in `api_base`, `api_key`, `api_model_name`
3. Supports OpenAI-compatible interfaces (Alibaba DashScope, local vLLM/Ollama, etc.)
4. Supports multi-image input

## 📁 Directory Structure

```
BSAI_Qwen_Prompt_Enhancer/
├── __init__.py                  # Node registration
├── common.py                    # Utilities: rule loading / message building / output parsing / image conversion
├── nodes_enhancer.py            # 3-in-1 enhancer node (Official PE / Local LLaMA / API)
├── nodes_template.py            # Template library node
├── system_prompts/              # Official PE-T2I/I2I system_prompt verbatim
├── templates/                   # Template library (cinema / design / official formulas)
├── web/                         # Frontend JS + thumbnails
├── examples/                    # Example workflows
└── README.md
```

## 🔧 Node Outputs

The enhancer node outputs 9 channels uniformly:

| Output | Description |
|---|---|
| `ENHANCED_PROMPT` | Enhanced prompt (can connect directly to KSampler positive) |
| `SYSTEM_PROMPT` | Actual system prompt used |
| `REASONING_TEXT` | Model reasoning process (returned in thinking mode) |
| `RECOMMENDED_SEED` | Recommended seed value |
| `RECOMMENDED_STEPS` | Recommended sampling steps |
| `RECOMMENDED_CFG` | Recommended CFG value |
| `RECOMMENDED_SAMPLER` | Recommended sampler |
| `RECOMMENDED_SCHEDULER` | Recommended scheduler |
| `WH_RATIO` | Output width-height ratio (in text-to-image mode) |

## 📝 Notes

- All model directories use **relative paths** (`models/LLM/`, `models/text_encoders/`), works regardless of where the plugin is moved
- Fully aligned with the Qwen interrogation logic from other BSAI series plugins, consistent loading parameters
- Supports `keep_loaded` to keep model in VRAM, no repeated loading during batch processing
