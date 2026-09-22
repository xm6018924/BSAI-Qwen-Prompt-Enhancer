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

### 📚 Built-in Template Library (55 templates, 6 categories)

The `Qwen Image 2.1 Official Prompt Enhancement Template` node includes **55 enhancement templates**:

#### ① Official Authoritative (5 templates)
- Qwen-Image-2.1 Official PE-T2I System Rules (10KB verbatim)
- Qwen-Image-2.1 Official PE-I2I System Rules (18KB verbatim)
- Official API prompt_extend Rewriting Style (with examples)
- Official Prompt Formula: Subject + Scene + Style + Shot + Mood + Details
- Official Poster / Slide Layout Template

#### ② Community Best Practices (4 templates)
- Universal Six-Element Template (Tensor.Art best practice)
- Chinese High-Quality Description Tips (Qwen-Image-Lightning)
- Style Mixing Template (community)
- Detail Control Template (community)

#### ③ Design Templates (9 templates, custom variables supported)
- Short Video Cover (9:16 portrait)
- Magazine Cover (2:3 portrait)
- Book Cover (2:3 portrait)
- Desktop Wallpaper (16:9 landscape)
- Poster Design (2:3 portrait)
- Magazine Inner Spread (3:2 landscape)
- Brochure Cover (3:2 landscape)
- Brochure Inner Page (3:2 landscape)
- Outdoor Billboard (21:9 ultra-wide)

#### ④ Cinema Assets (13 templates, custom variables supported)
- Film Still (16:9 single frame)
- Film Storyboard (3x2 with annotations)
- 4-grid Storyboard (2x2)
- 6-grid Storyboard (3x2)
- 9-grid Storyboard (3x3)
- 12-grid Storyboard (4x3)
- Character 3-View (front/side/back)
- Character 4-View (front/3-4/side/back)
- Character 6-View (full body + head close-ups)
- Prop 3-View (front/side/back)
- Prop 4-View (front/3-4/side/back)
- Prop 6-View (front/side/back + detail close-ups)
- Scene Asset Concept Art

#### ⑤ Character Sheets (12 templates, custom variables supported)
- Complete Character Sheet (3-view + expressions + outfit breakdown + color palette)
- Turnaround 4-View (front/3-4/side/back)
- Expression Sheet (6/8 grid)
- Outfit & Accessory Detail Breakdown
- Character Color Palette (with color swatches)
- Consistency Anchor (50+ fixed descriptor phrases, reusable)
- Single Full-Body Illustration
- Bust / Headshot Close-Up
- Game Splash Art Card
- Mobile UI Character Card (with info panel)
- Pose Sheet (6-grid action variations)
- Ancient / Chinese Style Character Design

#### ⑥ Movie Posters (12 styles, custom variables supported)
- Standard One-Sheet (portrait)
- Ensemble Cast
- Minimalist
- Split-Screen Comparison
- Environment Focus
- Oscar Drama
- Vintage Noir
- Summer Blockbuster
- Horror
- Romance
- Sci-Fi
- Anime Film

### Template Variable Replacement

Design / cinema / character templates include placeholders like `{{TITLE}}` `{{SUBTITLE}}` `{{BRAND}}` `{{MAIN_SUBJECT}}` `{{COLOR}}` `{{STYLE}}`.
Fill them in the node's **variables** input box, one per line as `KEY: value`. The node auto-replaces and outputs the full SYSTEM_PROMPT:

```
TITLE: Summer New Product Launch
SUBTITLE: 2026 Autumn Collection
BRAND: BSAI
MAIN_SUBJECT: A girl in a red dress standing under cherry blossoms
COLOR: Deep blue + orange gold
STYLE: Commercial photography
```

- Variable keys are case-insensitive
- The 4th output `USED_VARS` reports which keys were actually replaced
- Output SYSTEM_PROMPT connects directly to the enhancer node's `system_template`
- To use your own photo as main visual, connect the image to the enhancer node's `image_1` input

> 💡 Want to modify template content (override / append requirements / edit library files / add new templates)? See [TEMPLATE_GUIDE.en.md](TEMPLATE_GUIDE.en.md).

### 🖼 Template Wall (Visual Picker)

The template node includes a **visual template wall** — click the "🖼 Open Template Wall" button on the node to open it:

| Feature | Description |
|---|---|
| **Large previews** | All 55 templates have thumbnails so you can see the layout at a glance |
| **Category filter** | 7 categories: All / Official Rules / Official Docs / Community / Design / Cinema / Character / Posters |
| **Click to use** | Click any card to auto-fill the node — no manual dropdown selection needed |
| **Bilingual UI** | 🌐 toggle in top-right corner switches usage guide language |
| **Variable hints** | Each card shows all variable names supported by that template |

Template wall path: `web/templates_wall.html`

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

The enhancer node outputs 10 channels uniformly:

| Output | Description |
|---|---|
| `ENHANCED_PROMPT` | Enhanced prompt (can connect directly to KSampler positive) |
| `WH_RATIO` | Output width-height ratio (in text-to-image mode) |
| `RATIO_FOLLOW` | Whether to follow reference image aspect ratio |
| `RAW_OUTPUT` | Raw model output JSON |
| `THINKING` | Model reasoning process (returned in thinking mode) |
| `RECOMMENDED_STEPS` | Recommended sampling steps (follows speed_preset) |
| `RECOMMENDED_CFG` | Recommended CFG value (1.0 for Qwen Image 2.1) |
| `RECOMMENDED_SAMPLER` | Recommended sampler (euler) |
| `RECOMMENDED_SCHEDULER` | Recommended scheduler (simple) |
| `MERGED_TEXT` | Template text + user requirement (connect to downstream text nodes) |

> Right-click `steps` / `cfg` on KSampler → Convert to input, connect `RECOMMENDED_STEPS` / `RECOMMENDED_CFG`, and switching speed_preset tiers auto-updates the sampling parameters.


## ⚠️ Preview-only (preview_only) Mode

When `preview_only` is ON, **no backend model is called** — the node outputs a text preview without any enhancement:

- `ENHANCED_PROMPT` = your raw `prompt_text` (passed through as-is, no enhancement)
- `MERGED_TEXT` = template + user requirement concatenation (empty when no template)
- The node turns **red** with a tooltip warning "not enhanced", to prevent misuse

**Use case**: instant preview when picking templates in the Template Wall, or inspecting template concatenation.
**Turn it OFF for real generation** — otherwise Official PE / Local LLaMA is skipped and images are generated from your raw text.

> Note: selecting a template in the Template Wall auto-checks "preview only" for instant preview; remember to uncheck it before generating.

## 📝 Notes

- All model directories use **relative paths** (`models/LLM/`, `models/text_encoders/`), works regardless of where the plugin is moved
- Fully aligned with the Qwen interrogation logic from other BSAI series plugins, consistent loading parameters
- Supports `keep_loaded` to keep model in VRAM, no repeated loading during batch processing

## ⚡ Acceleration Guide (Qwen Image 2.1 Latest Upgrade)

Qwen Image 2.1 (7B DiT) is a **CFG-distilled model**; the official day-0 recommendation is **25 steps / cfg=1.0 / euler / simple**.
**Do NOT reuse the old 20B cfg=3~4 values** — that causes oversaturation, overexposure and stiff composition, and doubles the model forward passes per step.

### 11 Built-in Speed Presets (speed_preset)

Pick a tier and `RECOMMENDED_STEPS` / `RECOMMENDED_CFG` output the matching values; wire them to KSampler to auto-link:

| Tier | steps | Use case |
|---|---|---|
| Official Standard 25/CFG1 (default) | 25 | Daily generation (official recommendation, best quality) |
| Fast 15/CFG1 | 15 | Iteration preview, faster |
| Ultra 10/CFG1 | 10 | Quick drafts (slightly lower quality) |
| High Quality 35/CFG1 | 35 | Fine generation |
| Cache Boost 20/CFG1 | 20 | With EasyCache / Cache nodes |
| Lightning 8/4/CFG1 | 8/4 | For after the 2.1-specific Lightning LoRA ships |
| Legacy tiers ×4 | corrected | Keep old keys so old workflows never break |

### Recommended Model & Stackable Speed-ups (by ROI)

1. **Use the official int8 convrot model**: `qwen_image_2.1_int8_convrot.safetensors` (half VRAM, faster)
2. **Launch flags**: `--fast --use-sage-attention` (fused kernels + SageAttention, 20-40% faster sampling)
3. **TE-Speed QwenImage21 node** (third-party, output-prediction cache): wire `UNETLoader → QwenImage21Cache → TE-Speed → KSampler`, 30-40% faster
4. **EasyCache / KV Cache**: built-in `QwenImage21Cache` node, biggest win for editing workflows
5. **torch.compile**: `TorchCompileModel` node, 10-30% (one-time compile warm-up)

### Reference Speed

RTX 4090 / 1024×1024 / int8 / 25 steps ≈ **7.5 s/image**; with SageAttention + EasyCache ≈ **4-5 s**.

### ⚠️ Notes

- **The 2.1-specific Lightning LoRA is not released yet** (expected in 2-6 weeks); picking 8/4-step tiers now produces noisy images
- **Do NOT use the old 20B Lightning LoRA** (e.g. `Qwen-Image-Lightning-8steps-V2.0` — different architecture, weight shape mismatch)
- **Do NOT use TeaCache** (frozen for 14 months, incompatible with 2.1)
- ComfyUI **v0.37.0+** is required for native 2.1 support

Full acceleration playbook & hardware benchmarks: [ACCELERATION_GUIDE.md](ACCELERATION_GUIDE.md). Research: [RESEARCH_REPORT.md](RESEARCH_REPORT.md). Template mechanism & modification: [TEMPLATE_GUIDE.en.md](TEMPLATE_GUIDE.en.md).
