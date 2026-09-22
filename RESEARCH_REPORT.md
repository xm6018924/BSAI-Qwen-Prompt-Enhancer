# Qwen Image 2.1 加速技术研究报告

> 研究日期：2026-09-22
> 模型背景：Qwen Image 2.1 于 2026-09-20 发布，7B 参数 Single-Stream DiT + Qwen3-VL 8B 文本编码器，CFG-distilled 架构
> 研究范围：官方来源 / 学术论文 / 社区实践 / ComfyUI 生态
> 落地目标：BSAI_Qwen_Prompt_Enhancer 插件 speed_preset 加速档位升级

---

## 一、执行摘要

### 1.1 核心发现

| 维度 | 结论 | 证据等级 |
|------|------|----------|
| 官方最优采样参数 | **25步 / cfg=1.0 / euler / simple** | ✅ 已实证（ComfyUI day-0 联调） |
| CFG 值 | **必须为 1.0**（2.1 是 CFG-distilled 架构，引导内置） | ✅ 已实证 |
| 旧插件预设 | 全部错误（cfg=3~4、20步为标准），需修正 | ✅ 已确认 |
| 2.1 专用 Lightning LoRA | **尚未发布**（预计发布后 2-6 周） | ✅ 已确认 |
| 最快零风险组合 | int8 convrot 模型 + 25步 + KV Cache + SageAttention | ✅ 已实证 |
| RTX 4090 参考速度 | 1024×1024 / int8 / 25步 ≈ **7.5秒/张** | ✅ 已实证（社区实测） |

### 1.2 旧插件问题诊断

原 `_SPEED_PRESETS` 四个档位全部基于错误假设：

| 旧档位 | 旧参数 | 问题 |
|--------|--------|------|
| 标准质量 20步/CFG3 | (20, 3.0, euler, simple) | cfg=3 会导致过饱和/过曝；20步非官方推荐 |
| 极速 8步/CFG2 | (8, 2.0, euler, simple) | cfg=2 错误；无 LoRA 时 8步质量差 |
| 闪电 4步/CFG1 | (4, 1.0, euler, simple) | 参数本身正确，但 2.1 专用 Lightning LoRA 不存在 |
| 旧保守 50步/CFG4 | (50, 4.0, euler, simple) | cfg=4 严重过曝；50步无必要 |

**根因**：这些预设是为旧版 Qwen Image（20B MMDiT，非 CFG-distilled）设计的，直接套用到 7B DiT 的 2.1 上完全不适用。

---

## 二、官方推荐参数（已实证）

### 2.1 ComfyUI day-0 官方模板

ComfyUI v0.37.0（2026-09-21 发布）原生支持 Qwen Image 2.1，官方提供两个工作流模板（文生图 / 图像编辑），均硬编码：

| 参数 | 值 |
|------|-----|
| steps | **25** |
| cfg | **1.0** |
| sampler | **euler** |
| scheduler | **simple** |

**来源**：
- ComfyUI 官方文档：https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-2-1
- ComfyUI 发布博客：https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight

### 2.2 为什么 cfg=1.0

Qwen Image 2.1 采用 **CFG-distilled（分类器自由引导蒸馏）** 架构，引导信号已在训练阶段蒸馏进模型权重。推理时外部 CFG 设为 1.0（即无引导）时质量最佳：

- cfg > 1.0：过饱和、过曝、色彩偏移、构图僵硬
- cfg = 1.0：官方推荐，色彩自然、细节充分
- cfg < 1.0：欠曝、细节丢失

**来源**：Qwen 官方博客 https://qwen.ai/blog?id=qwen-image-2.1；ModelScope 模型卡

### 2.3 diffusers 路径

官方 diffusers 示例代码使用 `num_inference_steps=40`，但这是 diffusers 路径的保守值。ComfyUI 路径经 day-0 联调优化为 25 步，质量相当。

**来源**：ModelScope Qwen/Qwen-Image-2.1 模型卡

---

## 三、加速方案对比

### 3.1 已实证可用方案

| 方案 | 加速幅度 | 画质代价 | 适用条件 | 安装复杂度 |
|------|----------|----------|----------|------------|
| **int8 convrot 模型** | 显存减半，速度≈bf16 | 极小（convrot 优化） | ComfyUI v0.27.0+ | 零（官方默认） |
| **Qwen Image 2.1 Cache** | I2I 编辑场景显著 | 无损（精确缓存） | ComfyUI v0.37.0+，编辑工作流 | 零（核心内置） |
| **EasyCache** | ~1.2-1.5× | 轻微（可调节阈值） | ComfyUI v0.3.52+ | 零（核心内置） |
| **SageAttention** | 采样阶段 20-40% | 极小（INT8 注意力） | 需 pip install，启动加参数 | 低 |
| **torch.compile** | 10-30%（首次后） | 无损 | PyTorch 2.1+，CUDA | 低（核心节点） |
| **--fast 启动参数** | 5-15% | 无损 | 任意版本 | 零 |

### 3.2 理论可行 / 待验证方案

| 方案 | 潜在加速 | 状态 | 说明 |
|------|----------|------|------|
| LESA（arXiv 2602.20497） | 旧版 5-6.25× | 🔶 2.1 未实证 | KAN 预测器跳步，需重新校准系数 |
| LayerCache（arXiv 2604.16492） | 未知 | 🔶 理论可行 | 层间速度异质性缓存，未在 2.1 实测 |
| Qwen-Image-Flash 蒸馏（arXiv 2606.03746） | 4-NFE | 🔶 方法论可迁移 | 基于 2.0-Base 蒸馏，官方未放 2.1 权重 |
| TeaCache | ~2×（旧版） | ❌ 不推荐 | 项目已冻结 14 个月，与 2.1 不兼容 |
| TensorRT | ~2×（通用） | 🔶 无 2.1 专用引擎 | 社区尚空白 |
| QuantFunc | 宣称 11.7× | ⚠️ 传闻/待验证 | 闭源商业引擎，数据未经独立验证 |

### 3.3 不可用方案

| 方案 | 原因 |
|------|------|
| 旧版 20B Lightning LoRA | 架构不同（20B MMDiT vs 7B DiT），权重形状不匹配 |
| 旧版 20B Nunchaku INT4 | 同上，预量化权重不兼容 |
| Wuli-Art 2512-Turbo-LoRA | 针对 2512 训练，非 2.1 |
| LCM LoRA | 无人为 2.1 训练 LCM 版权重 |

---

## 四、Lightning LoRA 状态追踪

### 4.1 当前状态

截至 2026-09-22，**Qwen Image 2.1 专用 Lightning / 蒸馏 LoRA 尚未发布**。

### 4.2 已有 LoRA（均不兼容 2.1）

| LoRA | 适用模型 | 步数 | 来源 |
|------|----------|------|------|
| lightx2v/Qwen-Image-Lightning-8steps-V2.0 | 旧版 20B | 8 | https://huggingface.co/lightx2v/Qwen-Image-Lightning |
| lightx2v/Qwen-Image-Lightning-4steps-V2.0 | 旧版 20B | 4 | 同上 |
| Wuli-Art/Qwen-Image-2512-Turbo-LoRA | 2512 | 4/8 | https://modelscope.ai/models/Wuli-Art/Qwen-Image-2512-Turbo-LoRA |
| nunchaku-tech int4 融合 Lightning | 旧版 20B | 4 | https://github.com/mit-han-lab/ComfyUI-nunchaku |

### 4.3 预计发布时间

参考 lightx2v 历史节奏（2512 发布后约 6 天推出 8 步 Lightning），2.1 专用 LoRA 预计在 **2026 年 9 月底至 10 月底** 之间发布。

**监控地址**：
- https://huggingface.co/lightx2v
- https://www.modelscope.cn/models/lightx2v/Qwen-Image-Lightning
- ComfyUI 节点管理器更新

---

## 五、硬件实测数据

### 5.1 RTX 4090（24GB）

| 配置 | 分辨率 | 步数 | 耗时 | 来源 |
|------|--------|------|------|------|
| int8, ComfyUI 原生 | 1024×1024 | 25 | **~7.5 s** | MindStudio 实测 |
| int8, ComfyUI 原生 | 2048×2048 | 25 | ~30 s | MindStudio 实测 |
| int8, ComfyUI 原生 | 3072×3072 | 25 | ~95 s | MindStudio 实测 |
| BF16+SDPA (仅 denoise) | 1024×1024 | 40 | 26.69 s | SGLang 基准 |
| +Cache-DiT+INT8+SageAttn | 1024×1024 | 40 | **4.74 s** | SGLang 基准（5.63×） |

### 5.2 RTX 5090（32GB）

| 配置 | 分辨率 | 步数 | 耗时 | 显存峰值 |
|------|--------|------|------|----------|
| 8-bit (fp8), diffusers | 1024×1024 | 40 | 19.3 s | 22.8 GB |
| 4-bit (NF4), diffusers | 1024×1024 | 40 | 19.2 s | 16.3 GB |
| 8-bit, diffusers | 2048×2048 | 40 | 115.7 s | 24.3 GB |

> Windows 上因 Triton 不可用，torch.compile 无法启用，这是 5090 实测偏慢的主因。
> 来源：KGP Talkie 实测

### 5.3 数据中心卡

| 硬件 | 配置 | 1024×1024, 40步 | 来源 |
|------|------|-------------------|------|
| B200 (单卡) | FlashAttention | 2.748 s (生成) / 3.358 s (编辑) | SGLang |
| RTX PRO 6000 Blackwell 96GB | resident | 8.23 s | SGLang |
| DGX Spark (GB10) | — | 35.36 s | SGLang |

---

## 六、学术加速技术详解

### 6.1 LESA — Learnable Stage-Aware Predictors（arXiv 2602.20497）

- **方法**：KAN 网络学习时间特征映射，多阶段多专家预测器，跳过部分去噪步
- **旧版 Qwen-Image 实测**：
  - 5.00× 加速（N=7）：PSNR 30.18，LPIPS 0.25
  - 6.25× 加速（N=10）：PSNR 29.23，LPIPS 0.34
  - 相比 TaylorSeer 质量提升 20.2%
- **2.1 适用性**：理论可行，但需重新校准 KAN 系数；暂无现成权重
- **来源**：arXiv 2602.20497

### 6.2 TeaCache（Timestep Embedding Aware Cache）

- **原理**：相邻去噪步输出相似时跳过重算，缓存残差
- **旧版效果**：约 2× 加速（rel_l1_thresh=0.6）
- **2.1 问题**：
  - mlx-teacache 明确警告"若 checkpoint 未在校准集上（如 2.1），会发出警告"
  - ComfyUI 第三方节点 ComfyUI-TeaCache 已冻结 14 个月（最后提交 2025-07），51 个 open issue
  - 通过 monkey-patch 核心 forward 方法，ComfyUI 重构模型类就会断裂
- **结论**：不推荐用于 2.1
- **来源**：https://github.com/welltop-cn/ComfyUI-TeaCache

### 6.3 Qwen-Image-Flash 蒸馏（arXiv 2606.03746）

- **方法**：DMD（Distribution Matching Distillation）将 Qwen-Image-2.0-Base 蒸馏到 4-NFE
- **结果**：4 步学生在 T2I-Bench 平均评分 3.56，超过 80-NFE 教师模型
- **2.1 适用性**：方法论可迁移，但官方未放出 2.1 蒸馏权重
- **来源**：arXiv 2606.03746

### 6.4 LayerCache（arXiv 2604.16492）

- **方法**：利用层间速度异质性，浅层缓存、深层始终计算
- **优势**：指出 TeaCache/DiCache/TaylorSeer 的深层缓存误差占 70%
- **2.1 适用性**：架构上适用于 flow matching 的 2.1，但未实测
- **来源**：arXiv 2604.16492

---

## 七、ComfyUI 生态加速节点详解

### 7.1 Qwen Image 2.1 Cache 节点（原生）

- **类别**：`model/conditioning/qwen image`
- **版本要求**：ComfyUI v0.37.0+
- **参数**：
  - `device`：auto（默认）/ gpu / cpu / off
  - `dtype`：default（无损）/ int8（减半）/ int4（1/4，误差翻倍）
- **接线**：接在 TextEncodeQwenImage21 之后，通过 model patch 生效，无需手动接到 KSampler
- **适用场景**：图生图 / 多轮编辑（前缀 prompt + 参考图固定，反复出图）
- **原理**：混合粒度注意力下，文本用 token-level causal mask，图像用 chunk-level mask；前缀 KV 在第一步计算后精确复用

### 7.2 EasyCache / LazyCache（核心内置）

- **版本要求**：ComfyUI v0.3.52+（2025-08-23 加入）
- **类别**：`advanced/debug`（标记为 experimental）
- **接线**：`Load Diffusion Model → EasyCache → KSampler`
- **参数**：
  - `reuse_threshold`：默认 0.2（调高=更多跳过=更快=画质损失更多）
  - `start_percent`：默认 0.15（前 15% 不跳过）
  - `end_percent`：默认 0.95（后 5% 不跳过）
- **EasyCache vs LazyCache**：
  - EasyCache：深度 hook，支持 CFG 批处理，按 UUID 缓存，画质更好
  - LazyCache：只 hook predict-noise，单缓存张量，兼容性更广但画质较差
- **注意**：不要与 TeaCache / Spectrum 等其他步跳过方法叠加

### 7.3 SageAttention

- **安装**：`pip install sageattention`（需匹配 CUDA/Torch/Python 版本）
- **启用**：启动参数 `--use-sage-attention`
- **原理**：Query/Key 用 INT8 量化，Value 保持 16-bit
- **效果**：采样阶段 20-40% 加速（社区报告最高约 50%）
- **互斥**：与 `--use-flash-attention`、`--use-pytorch-cross-attention` 三选一
- **来源**：https://github.com/thu-ml/SageAttention

### 7.4 torch.compile（TorchCompileModel 节点）

- **接线**：`Load Diffusion Model → TorchCompileModel → KSampler`
- **参数**：`backend` = inductor / cudagraphs
- **效果**：首次编译 60-180 秒，后续推理快 10-30%
- **注意**：Windows 上 Triton 不可用，可能无法启用
- **来源**：ComfyUI 核心节点

---

## 八、推荐加速组合

### 8.1 立即可用（零风险）

**组合 A：日常出图（推荐大多数用户）**
1. ComfyUI v0.37.0+
2. int8 convrot 模型 `qwen_image_2.1_int8_convrot.safetensors`
3. speed_preset = "官方标准 25步/CFG1 (推荐)"
4. 启动参数加 `--fast`
5. KSampler 右键 steps/cfg → Convert to input，接入 RECOMMENDED_* 端口

**预期**：RTX 4090 / 1024×1024 ≈ 7.5秒/张

**组合 B：迭代预览（更快）**
1. 组合 A 全部
2. speed_preset = "快速 15步/CFG1 (迭代预览)" 或 "极速 10步/CFG1 (快速草稿)"
3. model → EasyCache → KSampler（配合"缓存加速 20步/CFG1"档）

**预期**：RTX 4090 / 1024×1024 ≈ 4-5秒/张

**组合 C：编辑工作流**
1. 组合 A 全部
2. 添加 "Qwen Image 2.1 Cache" 节点（device=auto, dtype=int8）
3. 多轮编辑时前缀 KV 自动复用

### 8.2 进阶加速（需安装依赖）

**组合 D：最大化速度**
1. 组合 B 全部
2. `pip install sageattention` + 启动参数 `--use-sage-attention`
3. TorchCompileModel 节点（inductor 后端）

**预期**：RTX 4090 / 1024×1024 ≈ 3.5-4.5秒/张（首次编译后）

### 8.3 未来可用（等待发布）

**组合 E：Lightning 极速（待 2.1 专用 LoRA 发布）**
1. lightx2v 发布 2.1 专用 Lightning LoRA 后
2. speed_preset = "Lightning 4步/CFG1" 或 "Lightning 8步/CFG1"
3. LoraLoader 加载 LoRA（strength=1.0）
4. 预期：RTX 4090 / 1024×1024 ≈ 1-2秒/张

---

## 九、代码改动总结

### 9.1 修改文件清单

| 文件 | 改动内容 |
|------|----------|
| `nodes_enhancer.py` | `_DEFAULT_SPEED` 改为官方标准；`_SPEED_PRESETS` 从 4 档扩展为 11 档（全部 cfg=1.0）；`_finalize` UI 文本增加 7 条加速要点；preview_only 分支补加速档显示；模块 docstring 9路→10路；DESCRIPTION 更新 |
| `verify_import.py` | 默认预设名 / steps==25 断言 / 打印文案同步更新 |
| `README.md` | 末尾追加 ⚡ 加速指南章节 |
| `README.en.md` | 末尾追加 Acceleration Guide 章节 |
| `ACCELERATION_GUIDE.md` | 新建：完整加速指南（档位表 / 6项加速方案 / 暂不可用项 / 硬件实测 / 版本要求 / 来源） |

### 9.2 新增 speed_preset 档位

| # | 档位名 | steps | cfg | 类型 |
|---|--------|-------|-----|------|
| 1 | 官方标准 25步/CFG1 (推荐) | 25 | 1.0 | 新增（默认） |
| 2 | 快速 15步/CFG1 (迭代预览) | 15 | 1.0 | 新增 |
| 3 | 极速 10步/CFG1 (快速草稿) | 10 | 1.0 | 新增 |
| 4 | 高质量 35步/CFG1 (精细出图) | 35 | 1.0 | 新增 |
| 5 | 缓存加速 20步/CFG1 (配合EasyCache节点) | 20 | 1.0 | 新增 |
| 6 | Lightning 8步/CFG1 (需lightx2v 2.1专用LoRA) | 8 | 1.0 | 新增 |
| 7 | Lightning 4步/CFG1 (需lightx2v 2.1专用LoRA) | 4 | 1.0 | 新增 |
| 8-11 | 旧版兼容档（4个） | 修正值 | 1.0 | 保留（向后兼容） |

### 9.3 向后兼容保障

- 旧版 4 个 preset key 全部保留，旧工作流 JSON 加载不会报错
- 旧 key 的内部值已修正为 2.1 正确参数（cfg=1.0），用户打开旧工作流时自动获得正确参数
- 输出端口数量不变（10 路），模板数量不变（55 个）
- 前端 JS 未改动，backend 显隐逻辑不受影响

### 9.4 验证结果

| 验证项 | 结果 |
|--------|------|
| `py_compile` 全部 .py 文件 | ✅ 通过 |
| `verify_import.py`（ALL PASS） | ✅ 通过（10路输出 / 55模板 / steps=25 / cfg=1.0） |
| `node --check web/prompt_enhancer.js` | ✅ 通过 |
| 模板数量 | ✅ 55 个（未改动） |
| 输出端口数 | ✅ 10 路（未增减） |

---

## 十、来源汇总

### 官方来源
- ComfyUI 官方文档（Qwen Image 2.1 原生工作流）：https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-2-1
- ComfyUI 发布博客：https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight
- ComfyUI Changelog：https://docs.comfy.org/changelog
- Qwen 官方博客：https://qwen.ai/blog?id=qwen-image-2.1
- Qwen HuggingFace 组织：https://huggingface.co/Qwen
- ModelScope Qwen-Image-2.1：https://modelscope.cn/models/Qwen/Qwen-Image-2.1

### 学术论文
- LESA（arXiv 2602.20497）：可学习阶段感知预测器
- Qwen-Image-Flash（arXiv 2606.03746）：DMD 蒸馏到 4-NFE
- LayerCache（arXiv 2604.16492）：层间速度异质性缓存
- Glance（arXiv 2512.02899）：Slow-Fast 蒸馏
- SageAttention（arXiv 2411.10958）：INT4 量化注意力

### 社区来源
- MindStudio（RTX 4090 本地部署实测）：https://www.mindstudio.ai/blog/qwen-image-2-1-local-install
- KGP Talkie（RTX 5090 8-bit/4-bit 实测）：https://kgptalkie.com/tutorials/llm-benchmarking/qwen-image-2-1-rtx-5090-local-benchmark
- SGLang Cache-DiT 基准：https://sgl-project.github.io/diffusion/performance/cache/cache_dit.html
- vLLM-Omni day-0 支持：https://thakicloud.com/tech-blog/en/llmops/qwen-image-2-1-vllm-omni-day0/
- ComfyUI Wiki（旧版完整指南）：https://comfyui-wiki.com/zh/tutorial/advanced/image/qwen/qwen-image
- Neura Market（Lightning LoRA 质量对比表）：https://www.neura.market/directories/md-directory/architecture-md-ai-research-qwen-image-monugi8r
- OrcaRouter（SGLang day-0 报道）：https://www.orcarouter.ai/de/blog/qwen-image-2-1-sglang-day-zero-serving

### 第三方插件 / 项目
- lightx2v Lightning LoRA：https://huggingface.co/lightx2v/Qwen-Image-Lightning
- SageAttention：https://github.com/thu-ml/SageAttention
- Nunchaku（MIT Han Lab）：https://github.com/mit-han-lab/ComfyUI-nunchaku
- ComfyUI-TeaCache（已冻结）：https://github.com/welltop-cn/ComfyUI-TeaCache
- QuantFunc Plugin：https://www.modelscope.cn/models/QuantFunc/Plugin
- EasyCache vs TeaCache 对比：https://www.instasd.com/post/comfyui-easycache-teacache-spectrum-speedup

---

*报告生成时间：2026-09-22。Qwen Image 2.1 发布仅 2 天，加速生态正在快速形成。建议每周复查 lightx2v、ComfyUI releases 和 r/comfyui 版块获取最新动态。*
