# BSAI Qwen Prompt Enhancer

> A ComfyUI plugin for **prompt enhancement and image interrogation** powered by the Qwen family of large language models.
> Enhance plain-language prompts into high-quality image generation prompts using official rules, or interrogate images with multimodal models.
> Three backends in one node: **Official PE / Local LLaMA / API**.

[中文版](README.md) | **English**

## 🚀 Latest Updates

### v1.04.0 (2026-09-24) — One-click fix for template wall ERR_INVALID_RESPONSE

> **Getting `ERR_INVALID_RESPONSE` when clicking "🖼 Open Template Wall" on another PC?**
> This happens because the `/extensions/` frontend static route returns an invalid response on some ComfyUI builds or when a system proxy hijacks loopback addresses. v1.04.0 fixes it for good:

**What's fixed:**

1. **Direct wall route**: the plugin now serves the wall at `GET /bsai_templates_wall` directly from the plugin — fully bypassing the `/extensions/` static route. Works on **any ComfyUI version, any network environment**.
2. **Button auto-upgrade**: after updating the plugin, the "🖼 Open Template Wall" button uses the direct route automatically — **zero manual steps**.
3. **One-click repair `fix_wall.bat`**: double-click to detect the ComfyUI port → test the direct route → if a system proxy is hijacking 127.0.0.1/localhost, add them to the bypass list automatically (original value backed up as `fix_wall_proxy_backup.reg`) → open the wall in your browser.
4. **Manual URL** (use your actual port): `http://127.0.0.1:8188/bsai_templates_wall`

**One-click resolution on another PC:**
```bash
# Option 1 (recommended): update the plugin and restart ComfyUI — the button just works
cd ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer && git pull
# Option 2: double-click fix_wall.bat in the plugin folder — it diagnoses, self-heals and opens the wall
fix_wall.bat
```

---



### v1.03.0 (2026-09-24) — Template Library Upgrades: 16 Typography + 16 Art Styles + User Template Area

> **Built-in template library grows from 102 to 134 (11 categories), plus a new User Template Area — drop your custom template JSON into `user_templates/`, and it merges automatically as a shared template for every workflow and the template wall.**

**What's new:**

1. **Typography templates (16, new `typography` category)**: global classic & cutting-edge typography styles — Swiss International / Bauhaus / Constructivist / New Ugly / Memphis / Vintage Victorian / Minimal Bold / Editorial / Newspaper / Japanese / Chinese Calligraphy / Glitch / Neon / 3D Extruded / Pixel / Hand-drawn.
2. **Art styles (15 → 31)**: added Impressionism / Post-Impressionism (Van Gogh) / Cubism / Surrealism / Pop Art / Expressionism / Abstract Expressionism / Art Deco / Art Nouveau / Baroque / Rococo / Pointillism / Fauvism / Futurism / Vaporwave / Acid Graphics.
3. **User Template Area (new `user` category)**: `user_templates/` folder under the plugin root. Accepts three JSON layouts (single object / object + external file / list), supports `{{KEY}}` variable placeholders, and auto-prefixes `user_` on id conflicts. **Other machines get all shared templates after `git pull`.**
4. **Dynamic template API `GET /api/bsai/templates`**: the template wall fetches this endpoint first (built-in + user templates merged live, including full text); static files remain the fallback — no static edits needed for new templates.
5. **Thumbnails**: all 32 new templates ship with unified thumbnails (dark gradient + category label + BSAI circular logo).

**How to use the User Template Area:** open `custom_nodes/BSAI_Qwen_Prompt_Enhancer/user_templates/README.md` (format docs), drop your template JSON into that folder → **fully restart ComfyUI** → the template dropdown and the wall's "User Templates" category show it. See `示例模板.json` in the same folder for examples.

---



### v1.02.0 (2026-09-24) — One-click install of all missing nodes for example workflows

> **Another PC shows red frames `node type not found / undefined` when opening BSAI example workflows (e.g. `SetNode`, `GetNode`, `Image Comparer (rgthree)`, `QwenImage21_T2IPromptRewrite`, `DLSS5Settings`, `DLSS5EnhanceImages`)?**
> Those are NOT missing parts of the BSAI plugin — they come from **5 third-party node packages** that the example workflows depend on. v1.02.0 **bundles the latent-upscale example workflow** into the plugin and ships a **one-click dependency installer**:
>
> ```bash
> # double-click (or run) inside the plugin folder:
> ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer/install_example_deps.bat
> ```
>
> The script auto-`git clone`s the 5 dependency plugins (skips existing ones); after a **full ComfyUI restart** every node lights up:
>
> | Node in the workflow | Provided by |
> |---|---|
> | `SetNode` / `GetNode` (wireless tunnels) | [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) (frontend virtual connections) |
> | `Image Comparer (rgthree)` | [rgthree-comfy](https://github.com/rgthree/rgthree-comfy) |
> | `QwenImage21_T2IPromptRewrite` | [ComfyUI-Qwen-Image-2.1-Prompt-Enhancer](https://github.com/benjiyaya/ComfyUI-Qwen-Image-2.1-Prompt-Enhancer) (download the official PE-T2I weights into `models/text_encoders/`) |
> | `DLSS5Settings` / `DLSS5EnhanceImages` (latent upscale) | [ComfyUI-DLSS5-Enhancer](https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer) (NVIDIA DLSS5 neural rendering; optionally run `install_runtime.py` to fetch the runtime) |
> | `easy cleanGpuUsed` / `easy clearCacheAll` | [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use) |
> | `PathchSageAttentionKJ` / `GetImageSizeAndCount` | [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) |
>
> Everything else you commonly see (`ResolutionSelector`, `ComfyMathExpression`, `SaveImageAdvanced`, `QwenImage21Cache`, `TextEncodeQwenImage21`) is **built into ComfyUI** — no install needed.
>
> v1.02.0 also bundles a **`MarkdownNote`-compatible node** (removed from new rgthree builds), so BSAI example workflows load cleanly on any machine.

---

### v1.01.2 (2026-09-24) — Compatible with old & new ComfyUI validation semantics

> **Newer ComfyUI shows `Custom validation failed for node: backend - None` (for every input)?** New builds call `VALIDATE_INPUTS(**all_inputs)` and **require `True`** (None/False both count as failure); legacy builds call `VALIDATE_INPUTS(input_name, input_value)` and treat None as pass.
> **v1.01.2 detects the calling convention and returns the right value** (True for kwargs form, None for two-positional form), so both old and new ComfyUI pass validation cleanly on load. Update to v1.01.2.

---

### v1.01.1 (2026-09-24) — Fix VALIDATE_INPUTS signature across ComfyUI versions

> **v1.01 could fail on some ComfyUI builds with: `Exception when validating inner node: BSAI_Qwen_Prompt_Enhancer.VALIDATE_INPUTS() missing 2 required positional arguments: 'input_name' and 'input_value'`** — those builds call `VALIDATE_INPUTS()` with **no arguments**, while v1.01's fixed signature `(input_name, input_value)` then throws.
> **v1.01.1 switches to a variadic signature `VALIDATE_INPUTS(*args, **kwargs)` that accepts any calling convention (no args / two args / kwargs), so every ComfyUI version loads cleanly with no red frame and no blocked graph.** Update the plugin to v1.01.1 (`git pull` or re-download).

---

### v1.01 (2026-09-24) — One-click fix: validation errors when opening workflows saved on another PC

> **Hit `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`, a red "Invalid input" frame, or `Output will be ignored` spam?** This means a dropdown value stored in the saved workflow does not exist on this machine (e.g. Florence-2 was selected on another PC, but this PC's `models/LLM` has no such model).
> **Upgrading to v1.01 resolves it automatically — no manual steps needed**: backend `VALIDATE_INPUTS` pass-through (no red frame / no blocked graph) + frontend auto-reset of invalid combo values on load. Manual root-cause fix in "Troubleshooting" at the end of this README.

---

### v0.9 (2026-09-23) — Backend Stability + Template Output Fixes

**Fixes the "Invalid chat handler: None" error on first local-LLaMA call, stale output after clearing the template, and ENHANCED_PROMPT not following the selected template in preview mode.**

- **`keep_loaded` now defaults off with post-use cleanup** — the LLM is closed only after the call finishes, so the chat handler stays valid (fixes `Invalid chat handler: None`)
- **Cleanup timing fixed** so it never interrupts the current call; all backends (Official PE / Local LLaMA / Local HF / API) are stable on first call
- **ENHANCED_PROMPT template-first**: in preview mode, ENHANCED_PROMPT correctly shows the merged template (template if set, raw text otherwise) — no more "selected Official PE but got the raw text"
- **New "Clear Template" button**: preview and output ports are fully cleared — no more repeated stale template output
- **Character-sheet templates upgraded (57 templates)**: the full reference sheet now follows the GPT Image 2 character-board methodology (free layout / psychology 4-element / multi-outfit layering / reference-first), plus 2 new templates — psychology profile and multi-outfit wardrobe
- **Character-sheet templates re-upgraded (59 templates)**: the full reference sheet now adds **silhouette / pose-action / detail-closeup zones** (Krea2 all-in-one dynamic sheet methodology), plus 2 new templates — single-reference to multi-view, and silhouette design
- **Art-style template library (74 templates)**: new **Art Styles** category with 15 style templates modeled on the ComfyUI EasyUse style-library format — modern anime / Ghibli healing / B&W manga / US comic / pencil sketch / charcoal sketch / photorealistic / cinematic film still / classical oil painting / watercolor / Chinese ink wash / ukiyo-e / cyberpunk neon / 16-bit pixel art / 3D Pixar animation; the poster wall now has the Art Styles filter and live category stats

---

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

### 📚 Built-in Template Library (134 templates, 11 categories + User Templates)

The `Qwen Image 2.1 Official Prompt Enhancement Template` node includes **134 enhancement templates**:

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

#### ⑤ Character Sheets (16 templates, custom variables supported)
- Complete Character Sheet (3-view + expressions + outfit breakdown + color palette) [upgraded: GPT Image 2 character-board + Krea2 all-in-one dynamic sheet methodology]
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
- Psychology Profile (traits / inner conflict / behavior patterns / emotional baseline) [NEW]
- Multi-Outfit Wardrobe + Layering (16:9 two outfits / 21:9 three outfits) [NEW]
- Single-Reference to Multi-View Sheet (reference-driven completion) [NEW]
- Silhouette Design (contour / body proportion / outline recognition) [NEW]

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

#### ⑦ Art Styles (15 style-conversion templates) [NEW]
- Modern Japanese Anime (cel shading / clean lineart)
- Ghibli Healing Style (Miyazaki)
- B&W Manga (ink lineart + screentone)
- US Comic (superhero comic)
- Pencil Sketch (hatching shading)
- Charcoal Sketch (dark atmosphere)
- Photorealistic
- Cinematic Film Still
- Classical Oil Painting (impasto canvas)
- Watercolor Illustration (transparent paper grain)
- Chinese Ink Wash (negative-space composition)
- Ukiyo-e (woodblock print)
- Cyberpunk Neon (future city)
- 16-bit Pixel Art (retro)
- 3D Pixar Animation (rendered)

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
| **Large previews** | All 102 templates have thumbnails so you can see the layout at a glance |
| **Category filter** | 10 categories: All / Official Rules / Official Docs / Community / Design / Cinema / Character / Posters / Art Styles / Character Poses / Web Inspiration |
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


---

## ❓ Troubleshooting

### Q: Opening a workflow shows `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`, the node turns red with "Invalid input", and the console logs `Output will be ignored`?

**Cause**: The workflow was saved on **another PC**. Its `hf_model_name` (Local HF backend) was set to `Florence-2-base [Florence2ForConditionalGeneration]`, but **that model is not present** under this machine's `ComfyUI/models/LLM` (not downloaded / different layout). The dropdown only contains `<未发现 HF 模型>`, so ComfyUI's combo validation fails → red frame + the whole graph gets ignored.

**✅ One-click fix (v1.01.1+, zero manual steps)**: Upgrade to **v1.01.1** — the plugin ships two layers of self-healing:

1. **Backend pass-through**: `VALIDATE_INPUTS` skips the combo value-in-list check → no red frame on load, graph is no longer blocked;
2. **Frontend auto-reset**: on workflow load, invalid combo values are automatically reset to the first item of the current list, and the node tooltip says "dropdown options were auto-reset".

After upgrading, open the workflow as usual and simply re-pick the model that actually exists on this machine from the `hf_model_name` dropdown.

**Manual fix (root cause)**: put the Florence-2 model into `ComfyUI/models/LLM/` (Transformers folder layout: `models/LLM/<model-dir>/model.safetensors` + `config.json` etc.). Download example:

```
pip install -U huggingface_hub
hf download microsoft/Florence-2-base --local-dir ComfyUI/models/LLM/Florence-2-base
```

### Q: Other dropdowns also report `Value not in list`?

Same cause (stored value not in the current option list — e.g. `system_template` after template-library updates, `llm_model_name` after model-folder changes). v1.01.1 applies the same self-healing to **all** dropdowns; restart ComfyUI and open the workflow — values are auto-reset, no manual node editing needed.

---

## v1.01 (2026-09-24) — One-click compatibility for saved workflows

- **Fix: red-frame errors when opening workflows saved on another PC** — combo values stored in the workflow that are missing from the current option list (e.g. Florence-2 selected on another machine but not downloaded here) no longer trigger "Invalid input" / `Value not in list` / `Output will be ignored`. Backend VALIDATE_INPUTS pass-through + frontend auto-reset of invalid combo values on load.
- **Bilingual troubleshooting added to README**.


## 🔄 Update & self-check (for other PCs)

> **Symptom**: another PC still shows `Custom validation failed for node: X - None` or `Value not in list` when opening the workflow.
> **99% of the time the plugin is not updated to v1.01.2 (or ComfyUI wasn't fully restarted after updating).** Confirm with these two steps:

**Step 1 — Update to v1.01.2** (inside the plugin folder `ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer`):

```bash
git pull origin main
# or re-download the latest repo zip and overwrite (ComfyUI Manager users: click UPDATE ALL and select this plugin)
```

**Step 2 — Fully restart ComfyUI** (not just refresh the browser page): close the ComfyUI process and start it again.

**Verify it took effect**: after restart, the first screen of the ComfyUI console should show the banner:

```
[BSAI_Qwen_Prompt_Enhancer] 插件已加载 | 版本 v1.01.2 (2026-09-24) | ...
```

- You see `v1.01.2` → updated; reopen the workflow and it works.
- No such line / version is v1.01.1 or older → the update didn't land: check whether `git pull` succeeded, whether ComfyUI was fully restarted, or whether files were copied from an old G-drive/zip.

**Check version from the command line**:

```bash
git -C ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer log --oneline -1
# should show 5ea6300 or a newer commit
```
