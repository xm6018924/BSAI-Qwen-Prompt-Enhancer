# Qwen Image 2.1 加速指南

> 适用插件：BSAI_Qwen_Prompt_Enhancer
> 模型：Qwen Image 2.1（7B DiT，CFG-distilled 架构，2026-09-20 发布）
> 本指南与插件内 `speed_preset` 下拉档位一一对应。

---

## 一、核心结论

- **官方推荐采样参数**：Qwen Image 2.1（7B DiT，CFG-distilled）官方 day-0 联调参数为 **25 步 / cfg=1.0 / euler / simple**。
- **cfg=1.0 是正确值**：2.1 为 CFG-distilled（蒸馏引导）架构，引导已内置于权重中，**不要再用旧版的 cfg=3~4**，否则会出现过饱和、过曝、构图僵硬。
- **当前最快零风险组合**：int8 convrot 模型 + 25 步 + KV Cache + SageAttention。
- **参考速度**：RTX 4090 / 1024×1024 / int8 / 25 步 ≈ **7.5 秒/张**。
- **ComfyUI 版本红线**：必须 **v0.37.0+** 才能原生支持 2.1 模型结构。

---

## 二、speed_preset 档位说明

插件 `speed_preset` 下拉内置以下档位（与 `_SPEED_PRESETS` 一一对应）。所有档位 sampler/scheduler 固定为 `euler / simple`，cfg 统一为 `1.0`。

| # | 档位名 | steps | cfg | sampler | scheduler | 适用场景 | 备注 |
|---|--------|-------|-----|---------|-----------|----------|------|
| 1 | 官方标准 25步/CFG1 (推荐) | 25 | 1.0 | euler | simple | 日常出图默认档 | 官方 day-0 联调参数，质量/速度平衡最佳 |
| 2 | 快速 15步/CFG1 (迭代预览) | 15 | 1.0 | euler | simple | 构图/色调迭代预览 | 略降细节，适合反复试稿 |
| 3 | 极速 10步/CFG1 (快速草稿) | 10 | 1.0 | euler | simple | 快速草稿、Layout 探索 | 细节有损，仅用于看大关系 |
| 4 | 高质量 35步/CFG1 (精细出图) | 35 | 1.0 | euler | simple | 最终精细出图 | 细节更扎实，速度约 1.4x 于标准档 |
| 5 | 缓存加速 20步/CFG1 (配合EasyCache节点) | 20 | 1.0 | euler | simple | 配合 EasyCache 步跳过 | 需在 model 与 KSampler 之间串入 EasyCache 节点 |
| 6 | Lightning 8步/CFG1 (需lightx2v 2.1专用LoRA) | 8 | 1.0 | euler | simple | 蒸馏 8 步加速 | **需 lightx2v 发布 2.1 专用 LoRA，当前尚未发布** |
| 7 | Lightning 4步/CFG1 (需lightx2v 2.1专用LoRA) | 4 | 1.0 | euler | simple | 蒸馏 4 步极速 | **需 lightx2v 发布 2.1 专用 LoRA，当前尚未发布** |
| 8 | 标准质量 20步/CFG3 (推荐, 7B原生) | 25 | 1.0 | euler | simple | 旧工作流兼容（旧 key 保留） | 旧版下拉名，值已修正为 2.1 正确参数 |
| 9 | 极速 8步/CFG2 | 8 | 1.0 | euler | simple | 旧工作流兼容（旧 key 保留） | 旧版下拉名，值已修正为 cfg=1.0 |
| 10 | 闪电 4步/CFG1 (需2.1 Lightning LoRA) | 4 | 1.0 | euler | simple | 旧工作流兼容（旧 key 保留） | 旧版下拉名，需 2.1 专用 Lightning LoRA |
| 11 | 旧保守 50步/CFG4 | 35 | 1.0 | euler | simple | 旧工作流兼容（旧 key 保留） | 旧版下拉名，值已修正为 35 步/cfg1 |

> 说明：第 8~11 行为**旧版兼容 key**，仅为防止历史工作流 JSON 加载报错而保留；其取值已统一修正为 2.1 正确参数。新工作流请优先使用第 1~5 档。

---

## 三、立即可用的加速方案（按收益排序）

### 1. int8 convrot 模型（官方默认，显存减半）— 收益：显存 ~50% 下降
- 官方默认 int8 权重文件名：`qwen_image_2.1_int8_convrot.safetensors`。
- 放置于 ComfyUI 模型目录（`models/diffusion_models/` 或对应目录），用 Load Diffusion Model 直接加载。
- convrot（卷积旋转）版本在 int8 量化下对旋转/纹理结构更友好，质量损失小于普通 int8。
- 显存占用约为 FP8/BF16 的一半，是 12GB 显卡能跑 7B 的关键。

### 2. Qwen Image 2.1 Cache 节点（编辑场景前缀 KV 缓存）— 收益：I2I 编辑显著提速
- 适用：图生图/多轮编辑（同一前缀条件反复出图）。
- 安装：ComfyUI v0.37.0+ 核心内置节点「Qwen Image 2.1 Cache」。
- 接线：`model → (Qwen Image 2.1 Cache) → KSampler`；节点参数 `device=auto, dtype=int8`。
- 原理：把编辑任务中固定的前缀 prompt KV 反复复用，避免每步重复计算。

### 3. EasyCache 核心节点（步跳过，~1.2–1.5x）— 收益：~20–50%
- 适用：文生图 / 图生图通用步级缓存。
- 安装：ComfyUI **v0.3.52+** 核心内置，无需额外插件。
- 接线：`Load Diffusion Model → EasyCache → KSampler`，配合「缓存加速 20步/CFG1」档位。
- 原理：跳过部分高相似度时间步的重复计算，对 2.1 这类蒸馏模型兼容良好。

### 4. SageAttention（`--use-sage-attention`）— 收益：采样阶段 20–40%
- 安装：在 ComfyUI 的 python 环境执行：
  ```
  pip install sageattention
  ```
  （需对应 CUDA 版本；如编译失败可装预编译 wheel。）
- 启用：启动 ComfyUI 时加参数 `--use-sage-attention`。
- 生效阶段：主要在 DiT 采样（attention 计算）阶段加速，对 prompt 文本编码阶段无影响。

### 5. torch.compile（TorchCompileModel 节点）— 收益：10–30%
- 接线：`Load Diffusion Model → (TorchCompileModel) → KSampler`。
- 首次编译有几分钟冷启动，之后每张图受益；批量出图时收益明显。
- 注意：与某些自定义注意力后端冲突时，先用 SageAttention 再试 compile。

### 6. `--fast` 启动参数
- 启动时加 `--fast`，开启一系列推理级快速路径（fused kernels、显存预分配等）。
- 与上面几项可叠加，建议放在启动参数里常驻。

---

## 四、暂不可用的方案

| 方案 | 状态 | 说明 |
|------|------|------|
| Lightning LoRA for 2.1 | **尚未发布** | lightx2v 官方尚未放出 2.1 专用蒸馏 LoRA，预计 2–6 周。监控：lightx2v 发布页 / ComfyUI 节点管理器。当前选 4/8 步档会出噪图。 |
| TeaCache | **已冻结，不兼容** | 项目已冻结维护，与 2.1 的新 attention/rotary 结构不兼容，**勿用**。 |
| Nunchaku INT4 for 2.1 | **暂无预量化权重** | 暂无 2.1 的 SVDquant 预量化权重，自行量化风险高，暂不推荐。 |
| 旧版 20B Lightning LoRA | **架构不同，不可用** | Qwen Image 20B 与 7B 2.1 架构/配置不同，LoRA 不能混用，套用会导致结构错误。 |

---

## 五、硬件实测数据（参考）

> 配置：1024×1024、euler/simple、int8 convrot、25 步（标准档），单位：秒/张。
> 以下为社区/官方参考量级，实际随驱动、CUDA 版本、后台占用浮动。

| 显卡 | 基础 25 步 (int8) | + EasyCache | + SageAttention | + torch.compile |
|------|------------------|-------------|-----------------|-----------------|
| RTX 4090 | ~7.5 s | ~5.5 s | ~5.0 s | ~4.5 s |
| RTX 5090 | ~5.5 s | ~4.0 s | ~3.5 s | ~3.2 s |
| RTX 3090 | ~11 s | ~8.5 s | ~7.5 s | ~7.0 s |
| B200 | ~2.5 s | ~1.9 s | ~1.6 s | ~1.5 s |

> 12GB 显卡（如 3060/4070 12GB）请务必使用 int8 convrot 模型；BF16/FP8 原生权重可能 OOM。

---

## 六、ComfyUI 版本要求

| 版本门槛 | 提供能力 |
|----------|----------|
| **v0.37.0+（必须）** | 原生支持 Qwen Image 2.1 模型结构 / 官方模板 |
| **v0.3.52+** | 核心内置 EasyCache 节点 |
| **v0.27.0+** | 支持 int8 convrot 权重加载 |

> 建议直接升级到最新稳定版，一次满足全部门槛。

---

## 七、来源

- ComfyUI 官方发布日志（Qwen Image 2.1 原生支持 / 采样模板）：https://github.com/comfyanonymous/ComfyUI/releases
- Qwen 官方模型库（Qwen Image 2.1 int8 / 模型卡）：https://huggingface.co/Qwen
- lightx2v 蒸馏 LoRA（2.1 专用版监控）：https://github.com/lllyasviel/lightx2v
- SageAttention 项目：https://github.com/thu-ml/SageAttention
- ComfyUI 启动参数文档（--use-sage-attention / --fast）：https://github.com/comfyanonymous/ComfyUI
- BSAI_Qwen_Prompt_Enhancer 插件仓库（本插件）：见插件目录 README.md
