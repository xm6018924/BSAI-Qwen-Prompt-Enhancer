# Qwen Image 2.1 加速与质量指南 v1.08.0

> 适用插件：BSAI_Qwen_Prompt_Enhancer
> 模型：Qwen Image 2.1（7B Single-Stream DiT，CFG-distilled 架构，2026-09-20 发布；Qwen3-VL 8B 文本/图像编码器，64通道 RGBA VAE，16x 空间压缩，原生 2K/2048²）
> 版本更新：2026-10-05 —— 全球全网检索，同步 2026-09-23 ~ 09-29 新发布的 **Viggle Turbo / Pruna / 阿里PAI Fun-Acc** 三大蒸馏 LoRA 生态与质量提升方案

---

## 一、核心结论

- **官方 day-0 联调采样参数**：Qwen Image 2.1 为 **25 步 / cfg=1.0 / euler / simple**（ComfyUI v0.37.0+ 原生模板默认，本插件默认档即此值）。
- **cfg=1.0 是正确值**：2.1 是 CFG-distilled（蒸馏引导）架构，引导已内置于权重，**不要再用旧版 cfg=3~4**。官方文档明确：`cfg=2` 更贴近复杂提示词（小字号文字/数字），代价是边缘过度锐化；`cfg=5` 严重劣化；`cfg=0.5` 直接破坏图像。
- **负向提示词在 cfg=1 时不生效**：ComfyUI 在 cfg=1 时跳过负向条件计算；想让负向提示词生效必须把 cfg 提到 1 以上（如 Fix LoRA 工作流用 cfg=3）。
- **蒸馏 LoRA 生态已上线（重要更新）**：2026-09-23 起，Viggle Turbo（6步/官方 ComfyUI 节点）、Pruna（5/8步）、阿里 PAI Fun-Acc（4步）相继发布，全部要求 **CFG=1.0 + 空负向 + 各自固定 sigma**，不能直接套用 KSampler 自带 scheduler（否则出噪图）。lightx2v 的 2.1 专用 Lightning LoRA **尚未发布**。
- **当前最快零风险组合**：int8 convrot 模型 + 25 步 + KV Cache + EasyCache + SageAttention。
- **参考速度**：H100@1024 基础 40步 6.10s → Pruna 8步 1.61s（3.8x）/ 5步 1.06s（5.7x）；Viggle v0.3 6步在 1344×1760 上约 2.9s（40步 14.0s，约 4.8x）。
- **ComfyUI 版本红线**：必须 **v0.37.0+**（原生支持 2.1 结构 + TextEncodeQwenImage21 + QwenImage21Cache）；蒸馏档所需的 `ManualSigmas` / `SamplerCustom` / `APG` / `FreSca` 均为核心内置节点。

---

## 二、speed_preset 档位说明

插件 `speed_preset` 下拉内置以下档位（与 `nodes_enhancer.py` 的 `_SPEED_PRESETS` 一一对应）。普通档 sampler/scheduler 固定 `euler / simple`，cfg 统一 `1.0`。

| # | 档位名 | steps | cfg | 类型 | 备注 |
|---|--------|-------|-----|------|------|
| 1 | 官方标准 25步/CFG1 (推荐) | 25 | 1.0 | 原生 | 官方 day-0 联调参数，质量/速度平衡最佳 |
| 2 | 快速 15步/CFG1 (迭代预览) | 15 | 1.0 | 原生 | 略降细节，适合反复试稿 |
| 3 | 极速 10步/CFG1 (快速草稿) | 10 | 1.0 | 原生 | 细节有损，仅用于看大关系 |
| 4 | 高质量 35步/CFG1 (精细出图) | 35 | 1.0 | 原生 | 细节更扎实，约 1.4x 于标准档 |
| 5 | 缓存加速 20步/CFG1 (配合EasyCache节点) | 20 | 1.0 | 缓存 | model 与 KSampler 之间串 EasyCache |
| 6 | **Viggle Turbo 6步/CFG1 (官方节点,推荐)** | 6 | 1.0 | ⚠蒸馏 | 需 Viggle 官方节点 + LoRA + 固定sigma，见第四节 |
| 7 | **Viggle Turbo 9步/CFG1 (仅diffusers)** | 9 | 1.0 | ⚠蒸馏 | 7步turbo+2步base，ComfyUI 暂无 |
| 8 | **Pruna 8步/CFG1 (质量优先,推荐)** | 8 | 1.0 | ⚠蒸馏 | 需社区转换版 LoRA + ManualSigmas，见第四节 |
| 9 | **Pruna 5步/CFG1 (极速)** | 5 | 1.0 | ⚠蒸馏 | 最快但画质明显下降 |
| 10 | **官方Fun-Acc 4步/CFG1 (PAI,实验)** | 4 | 1.0 | ⚠蒸馏 | 官方4步 PDD，ComfyUI 仅实验路径 |
| 11 | 标准质量 20步/CFG3 (推荐, 7B原生) | 25 | 1.0 | 旧key兼容 | 旧工作流 key 保留，值已修正 |
| 12 | 极速 8步/CFG2 | 8 | 1.0 | 旧key兼容 | 旧工作流 key 保留，值已修正 |
| 13 | 闪电 4步/CFG1 (需2.1 Lightning LoRA) | 4 | 1.0 | 旧key兼容 | lightx2v 2.1 LoRA 尚未发布，勿选 |
| 14 | 旧保守 50步/CFG4 | 35 | 1.0 | 旧key兼容 | 旧工作流 key 保留，值已修正 |

> ⚠ 蒸馏档（6~10 行）**不能**直接把 RECOMMENDED_STEPS 接到普通 KSampler 的 steps 上：必须使用对应 LoRA + 固定 sigma（Viggle Turbo Sigmas / ManualSigmas / PDD），接线方法见第四节。节点 UI 会对蒸馏档自动显示接线提示。
> 第 11~14 行为旧版兼容 key（防历史工作流 JSON 报错），取值已统一修正为 2.1 正确参数。

---

## 三、立即可用的加速方案（按收益排序）

### 1. 蒸馏 LoRA（2026-09 起，最大收益 3.5x~6.3x）→ 详见第四节
- Viggle Turbo 6步 / Pruna 8步 为当前最推荐的两条路线，质量接近 40 步基础模型。

### 2. int8 convrot 模型（官方默认，显存减半）— 收益：显存 ~50% 下降
- 文件名：`qwen_image_2.1_int8_convrot.safetensors`（本机已就位），放 `models/diffusion_models/` 用 Load Diffusion Model 加载。
- convrot（卷积旋转）在 int8 下对旋转/纹理更友好，质量损失小于普通 int8；12GB 卡跑 7B 的关键。

### 3. Qwen Image 2.1 Cache 节点（编辑场景前缀 KV 缓存）— 收益：I2I 编辑显著提速
- 接线：`model → (Qwen Image 2.1 Cache) → KSampler`；实验性节点两个控件：
  - `device`：`auto`（默认，先空闲VRAM再RAM）/ `gpu` / `cpu`（RAM 预取，损失很小）/ `off`（每步重算，排查用）
  - `dtype`：`default`（无损）/ `int8`（缓存减半，精度≈bf16）/ `int4`（四分之一，每步误差约翻倍）

### 4. EasyCache 核心节点（步跳过，~1.2–1.5x）
- ComfyUI **v0.3.52+** 核心内置。接线：`Load Diffusion Model → EasyCache → KSampler`，配合「缓存加速 20步/CFG1」。

### 5. SageAttention（`--use-sage-attention`）— 收益：采样阶段 20–40%
- `pip install sageattention`（需匹配 CUDA；Intel 环境请优先验证 XPU 兼容性，若不支持改用 torch.compile / --fast）。

### 6. torch.compile（TorchCompileModel 节点）— 收益：10–30%
- 首次编译有几分钟冷启动，之后每张受益；批量出图收益明显。与自定义注意力后端冲突时先 SageAttention 再 compile。

### 7. `--fast` 启动参数
- 推理级快速路径（fused kernels、显存预分配等），可与上面叠加。

---

## 四、2.1 专用蒸馏 LoRA 详情（2026-09-23 ~ 09-29 全网检索重点更新）

### 4.1 Viggle Turbo v0.3 —— 官方 ComfyUI 支持，6 步（推荐首选）
- **仓库**：https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo
- **方案**：rank-256 LoRA 蒸馏；**6 步无 CFG**（=40 步），另有 9 步模式（7步turbo+2步base，仅 diffusers/Space）。
- **ComfyUI 用法（官方打包）**：
  1. 把模型仓库 `comfyui/viggle_turbo.py` 复制到 `ComfyUI/custom_nodes/`（本机已装入 `custom_nodes/viggle_turbo/`，含 `__init__.py` 入口 + 官方 t2i/edit 工作流 JSON），重启。
  2. 得到两个节点：**Viggle Turbo Sigmas**（6步固定sigma，含分辨率相关 shift）+ **Viggle Turbo LoRA (unmerged)**（运行时应用 LoRA，不推荐标准 LoraLoader 合并：bf16 损失约 30% 更新量、int8 加噪）。
  3. 接线：`Viggle Turbo Sigmas → BasicGuider → SamplerCustomAdvanced`，`euler`，**无 CFG、负向留空**。
  4. 原始（未 shift）6步节点 = `1.0, 0.9375, 0.875, 0.75, 0.5, 0.25`；改步数只在高端加/减：5步=`1.0, 0.875, 0.75, 0.5, 0.25`，7步=`1.0, 0.9583, 0.9167, 0.875, 0.75, 0.5, 0.25`；**低端 0.875/0.75/0.5/0.25 永远保留**。
- **本机已下载**：`models/loras/Qwen-Image-2.1-viggle-turbo-v0.3-6step-lora-r128.safetensors`（0.7GB，ComfyUI 工作流默认档）+ `custom_nodes/viggle_turbo/`（viggle_turbo.py + t2i/edit 工作流）。r256 原版（1.3GB）按需再下。
- **合并单文件权重（可选，免 LoRA）**：int8 convrot 7.3GB / fp8 7.3GB / GGUF Q8_0 7.7GB 等放 `models/diffusion_models/`（GGUF 需 ComfyUI-GGUF），仍要 Viggle Turbo Sigmas 节点；仅 6 步模式。
- **质量与速度**：比 40 步稍软（小字更易糊、颜色饱和度低几个百分点）；6 步=40 步约 4.8x；9 步约 3.5x。VRAM：int8+r128 LoRA @1248×832 峰值约 26GB。
- **本机现状**：`models/loras/Qwen-Image-2.1-viggle-turbo-4step-lora-r64.safetensors` 为 v0.1 的 4 步 r64 变体（DMD2 蒸馏，4 或 8 步固定 sigma、CFG=1.0、负向留空），如需升级到 v0.3 请从上述仓库下载最新 6 步版本。

### 4.2 Pruna 5/8 步 LoRA —— 社区 ComfyUI 转换，8 步质量优先
- **仓库**：https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1（v0.1，DMD 蒸馏，需基础模型 Qwen/Qwen-Image-2.1）
- **两档**：`p_qwen_image_2.1_8step_v0.1.safetensors`（8步，推荐默认）/ `p_qwen_image_2.1_5step_v0.1.safetensors`（5步，画质明显更差）
- **固定 sigma（必须逐位一致，末尾 0 由调度器补）**：
  - 5 步：`1.0, 0.94, 0.857142857, 0.666666667, 0.4`
  - 8 步：`1.0, 0.933333333, 0.857142857, 0.769230769, 0.666666667, 0.545454545, 0.4, 0.222222222`
- **ComfyUI 用法**：官方包是 PEFT 格式且 alpha 存在 metadata（直装会比例错误），需社区转换版：`NidAll/pruna-image-2.1-comfyui-loras`（为 224 个目标各加 `.alpha` 标量张量，附 5/8 步工作流 JSON）。接线：**ManualSigmas（填上表）+ SamplerCustom + Euler + CFG 1.0 + LoRA strength 1.0 + 空负向**，基础文件用 `Comfy-Org/Qwen-Image-2.1`（消费级显存选 int8_convrot）。
- **本机已下载**：`models/loras/p_qwen_image_2.1_8step_v0.1_comfyui.safetensors`（8步，推荐）与 `models/loras/p_qwen_image_2.1_5step_v0.1_comfyui.safetensors`（5步，极速），均为社区转换版，可直接用 LoraLoader 加载。
- **覆盖范围**：仅在 1K 分辨率训练（T2I + 单/多图编辑，≤3 参考图）；2K、更多参考图、短模糊提示词属范围外，质量可能波动。
- **速度**：H100@1024 T2I 6.10s → 8步 1.61s / 5步 1.06s；2048 31.44s → 7.60s / 4.98s（6.3x）。

### 4.3 阿里 PAI Fun-Acc 4 步 LoRA —— 官方蒸馏，ComfyUI 实验性
- **仓库**：Qwen-Image-2.1-Fun-Acc-LoRAs（HuggingFace | VideoX-Fun）；`models/Qwen-Image-2.1-Fun-Acc-4Step.safetensors`（346MB，rank64/alpha64，BF16）
- **固定 sigma**：`1.0, 0.9169867, 0.7861579, 0.549491, 0.0`（pdd_config.json 固化，默认 2048×2048 采样）
- **覆盖**：T2I + 指令编辑（含多参考编辑），训练目标含全部 32 层 attention/img_mlp、timestep embedders、txt_in 等；`norm_q/norm_k/text_norm` 为全参（非 LoRA 对）。
- **ComfyUI 现状**：无官方支持。实验路径：Kijai 的 **Qwen-Image 2.1 PDD 分支**（ComfyUI 仓库）+ LoRA 转换；属社区工作，谨慎使用。
- **已知短板**：密集小字退化、部分编辑略糊/偏暗。

### 4.4 lightx2v Lightning（状态监控）
- lightx2v 目前支持 Qwen-Image / Qwen-Image-Edit(-2509/-2511) 的 Lightning LoRA，**2.1 专用版尚未发布**。监控：https://github.com/lllyasviel/lightx2v 与 ComfyUI 节点管理器。发布前请勿用 4/8 步 Lightning 档。

---

## 五、质量提升方案（2026-09~10 全网检索新增）

### 1. cfg 与 steps 的官方行为（docs.comfy.org 2.1 教程）
- `cfg=2`：更贴复杂提示词（小字号文字/数字更准），代价边缘过锐；一次只改一个变量、固定种子对比。
- steps：简单局部编辑（如换衣服颜色）**4~8 步**即可成立；整图重写编辑需完整 25 步；手/指细节约 30 步收敛；25→40 步减少细节区杂乱噪点。
- 分辨率：T2I 用「分辨率选择器」（1.0MP≈1024，4.0MP≈2048）；编辑用子图 `resolution` 控件（0=保持 image_1 原始尺寸并取 32 倍数，>0=按像素预算缩放）。**降 resolution 只是生成更小的结果来提速，不会增加细节**。

### 2. Qwen-Image 2.1 Fix LoRA（社区质量修复，112MB）
- 针对 2.1 两大被诟病缺陷：**颜色发灰褪色 + 细纹理破碎（gpt-image 式斑驳）**，并改善手部。
- 文件：`qwen-image-2.1-fix-1.0-comfy.safetensors` → `models/loras/`；配 20 节点工作流（"Qwen Edit 2.1 Optimal Settings"）。
- 关键参数：**20 步 / cfg=3 / seeds_2 / sgm_uniform / denoise=1.0 + APG(1,10,0.3) + FreSca(1,2,8)（核心内置）+ LoraLoaderModelOnly 强度 1.0**；负向提示词明确列出：
  ```
  artifacts, gpt-image, washed-out colors, low quality, low resolution, AI slop,
  deviantart, sloppy lines, rough sketch, blurry, indistinct, missing fingers,
  badly drawn hands, wrong number of fingers
  ```
- 注意：社区单作者 LoRA，口碑两极；部分提升可能来自工作流的引导/负向设置而非 LoRA 本身。

### 3. 社区细节增强 LoRA
- elusarca 的 Qwen-Image 2.1 Detail Enhancer LoRA（约 79.7MB）：提升锐度与纹理，可叠加在基础模型或蒸馏档上（以实测为准）。

### 4. 官方 PE 提示词增强（本插件官方PE后端已内置）
- 独立文本编码器：T2I 用 `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors`，编辑用 `_pe_i2i` 版（本机 `models/text_encoders/Qwen image 2.1 PE/` 已就位）。
- 节点开启 `refine_prompt` 后图像模型使用改写提示词采样；`thinking_mode` 让改写模型先推理再输出（更稳但更慢）。用 Preview Any 先看真正送入模型的提示词。

### 5. Alpha 通道 / 原生 2K
- 2.1 的 VAE 带 4 通道，可直接生成/编辑透明背景（PNG），无需后处理抠图。背景移除提示词示例：`Remove the background, and output a PNG image`。

### 6. 编辑提示技巧（官方）
- 参考图按槽位顺序接入，提示词用 `<imageN>` 索引引用（`image_1` 是被编辑图）：`Keep the character and pose in <image1> unchanged, put this light blue denim shirt from <image2> on the character...`
- 局部编辑：在 LoadImage 上用 Paint Pen 涂抹目标区域（标记成为参考图一部分），提示词指名颜色，如"把红色区域里的夹克换掉"。

---

## 六、暂不可用的方案

| 方案 | 状态 | 说明 |
|------|------|------|
| lightx2v Lightning LoRA for 2.1 | **尚未发布** | 监控 github.com/lllyasviel/lightx2v；当前选 4/8 步 Lightning 档会出噪图 |
| TeaCache | **已冻结，不兼容** | 项目冻结维护，与 2.1 的新 attention/rotary 结构不兼容，勿用 |
| Fun-Acc 官方 ComfyUI 支持 | **无** | 仅 Kijai PDD 实验分支 + LoRA 转换，非官方路径 |
| Nunchaku INT4 for 2.1 | **暂无预量化权重** | 自行量化风险高，暂不推荐 |
| 旧版 20B Lightning LoRA | **架构不同，不可用** | 20B 与 7B 2.1 架构不同，套用会结构错误 |

---

## 七、硬件实测数据（参考）

> 官方/社区公布量级，实际随驱动、CUDA 版本、后台占用浮动。

**Pruna 官方（1×H100 80GB / BF16 / batch 1，含 encode+denoise+decode，KV cache：基础开、蒸馏关）：**

| 场景 | 基础 40步 | Pruna 8步 | Pruna 5步 |
|------|-----------|-----------|-----------|
| T2I 1024×1024 | 6.10 s | 1.61 s (3.8x) | 1.06 s (5.7x) |
| T2I 2048×2048 | 31.44 s | 7.60 s (4.1x) | 4.98 s (6.3x) |
| I2I 1024×1024 | 7.05 s | 2.01 s (3.5x) | 1.43 s (4.9x) |

**Viggle demo Space（同 prompt/seed/噪声）：**

| 场景 | 分辨率 | 基础 40步 | v0.3 6步 | v0.3 9步 |
|------|--------|-----------|----------|----------|
| 参考图人像 | 1344×1760 | 14.0 s | 2.9 s | 4.0 s |
| 六参考群像 | 1248×1888 | 25.8 s | 5.9 s | 8.8 s |
| 密集 App 截图 | 1536×2720 | 26.9 s | 4.9 s | 6.8 s |
| 360° 全景 | 2176×1088 | 14.3 s | 2.9 s | 4.1 s |

**消费级估算（社区/官方量级，25 步 int8 基础档 + 叠加项）：**

| 显卡 | 基础 25 步 (int8) | + EasyCache | + SageAttention | + torch.compile |
|------|------------------|-------------|-----------------|-----------------|
| RTX 4090 | ~7.5 s | ~5.5 s | ~5.0 s | ~4.5 s |
| RTX 5090 | ~5.5 s | ~4.0 s | ~3.5 s | ~3.2 s |
| RTX 3090 | ~11 s | ~8.5 s | ~7.5 s | ~7.0 s |
| B200 | ~2.5 s | ~1.9 s | ~1.6 s | ~1.5 s |

> 12GB 显存（3060/4070 12GB 等）务必用 int8 convrot；再叠 Viggle/Pruna 蒸馏可明显提速。Intel 显卡/XPU 环境：SageAttention 需先验证兼容性，蒸馏 LoRA（模型侧）不受硬件限制。

---

## 八、ComfyUI 版本要求

| 版本门槛 | 提供能力 |
|----------|----------|
| **v0.37.0+（必须）** | 原生支持 Qwen Image 2.1 结构 / TextEncodeQwenImage21 / QwenImage21Cache / 官方模板 |
| **v0.3.52+** | 核心内置 EasyCache 节点 |
| **v0.27.0+** | 支持 int8 convrot 权重加载 |
| 核心内置（蒸馏档需要） | ManualSigmas / SamplerCustom / BasicGuider / SamplerCustomAdvanced / APG / FreSca |

> 建议直接升级到最新稳定版（或本机 2026-10-04 nightly），一次满足全部门槛。

---

## 九、来源

- ComfyUI 官方 Qwen-Image-2.1 教程（采样/分辨率/KV缓存/PE/编辑技巧）：https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-2-1
- ComfyUI 官方发布日志：https://github.com/comfyanonymous/ComfyUI/releases
- Qwen 官方模型库：https://huggingface.co/Qwen ；ComfyUI 模型：https://huggingface.co/Comfy-Org/Qwen-Image-2.1
- Viggle Turbo v0.3（官方 ComfyUI 节点 + 合并权重）：https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo
- Pruna 5/8 步 LoRA：https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1 ；社区 ComfyUI 转换：NidAll/pruna-image-2.1-comfyui-loras
- 阿里 PAI Fun-Acc 4 步（VideoX-Fun / HF）：Qwen-Image-2.1-Fun-Acc-LoRAs；Kijai PDD 实验分支见 ComfyUI 社区
- Qwen-Image 2.1 Fix LoRA（质量修复）：comfyui-wiki 2026-09-22 报道
- lightx2v（2.1 专用 Lightning 监控）：https://github.com/lllyasviel/lightx2v
- SageAttention：https://github.com/thu-ml/SageAttention
- ComfyUI 启动参数文档（--use-sage-attention / --fast）：https://github.com/comfyanonymous/ComfyUI
- BSAI_Qwen_Prompt_Enhancer 插件仓库（本插件）：见插件目录 README.md
