# BSAI Qwen Prompt Enhancer

> 基于千问（Qwen）家族系列大模型的 **ComfyUI 提示词增强 / 图像反推插件**。
> 把大白话提示词按官方规则增强为高质量出图提示词，或用多模态模型对图片进行反推描述。
> 三合一后端一键切换：**官方PE / 本地LLaMA / API**。

**中文** | [English](README.en.md)

## 🚀 最新更新 / Latest Updates

### v1.01 (2026-09-24) — 跨电脑打开工作流红框报错一键自愈 / One-click fix: validation errors when opening workflows saved on another PC

> **遇到 `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`、节点红框「无效输入」、控制台刷 `Output will be ignored`？** 这是**旧工作流存档的下拉值在本机不存在**（例如另一台电脑选了 Florence-2，本机 `models/LLM` 下没这个模型）。
> **升级到 v1.01 后自动解决，无需任何手动操作**：后端 `VALIDATE_INPUTS` 放行 combo 校验（不再红框/阻塞整图）+ 前端加载时自动把非法下拉值重置为列表首项。手动根治方法见文末「常见问题 / Troubleshooting」。
>
> **See `Value not in list: hf_model_name: ... not in ['<未发现 HF 模型>']`, a red "Invalid input" frame, or `Output will be ignored` spam?** The workflow saved a dropdown value that does not exist on this machine (e.g. Florence-2 was selected on another PC but is not in this PC's `models/LLM`). **v1.01 fixes this automatically — zero manual steps**: backend `VALIDATE_INPUTS` pass-through (no red frame / no blocked graph) + frontend auto-reset of invalid combo values on load. Manual root-cause fix in "Troubleshooting" at the end of this README.

---

### v0.9 (2026-09-23) — 后端稳定性修复 + 模板输出修复 / Backend Stability + Template Output Fixes

**核心：彻底解决"本地 LLaMA 首次调用 Invalid chat handler: None"报错；清除模板后不再残留；预览选模板时 ENHANCED_PROMPT 正确走模板输出。**
**Fixes: "Invalid chat handler: None" on first local-LLaMA call; no stale output after clearing the template; ENHANCED_PROMPT now correctly follows the selected template in preview mode.**

- **`keep_loaded` 默认关闭 + 用后清理**：修复 llama-cpp 在 keep_loaded=false 路径下加载后立即 `_clear_cache()` 提前 close LLM，导致 chat handler 被置空（`Invalid chat handler: None`）的问题。现在模型用完才清理，handler 始终有效 / `keep_loaded` now defaults off with post-use cleanup — the LLM is closed only after the call finishes, so the chat handler stays valid (fixes `Invalid chat handler: None`)
- **清理时机修复**：`_enhance_local` 的缓存清理不再干扰本轮调用，多后端（官方PE / 本地LLaMA / 本地HF / API）首次调用均稳定 / Cleanup timing fixed so it never interrupts the current call; all backends (Official PE / Local LLaMA / Local HF / API) are stable on first call
- **ENHANCED_PROMPT 模板优先**：预览模式下选择模板后，ENHANCED_PROMPT 输出端口的预览正确显示模板拼接结果（有模板→模板，无模板→原文），不再出现"选了官方PE却直出原文" / In preview mode, ENHANCED_PROMPT now correctly shows the merged template (template if set, raw text otherwise) — no more "selected Official PE but got the raw text"
- **清除模板按钮新版**：点击清除后预览与输出端口彻底清空，不再反复输出旧模板内容 / New "Clear Template" button: preview and output ports are fully cleared — no more repeated stale template output
- **角色卡模板升级（57 个模板）**：完整设定总表融合 GPT Image 2 角色提示板方法论（自由排版 / 心理特质四要素 / 多套服装叠穿 / 参考图优先），新增「心理特质四要素」「多套服装+叠穿设定」2 个模板 / Character-sheet templates upgraded: the full reference sheet now follows the GPT Image 2 character-board methodology (free layout / psychology 4-element / multi-outfit layering / reference-first), plus 2 new templates (psychology profile, multi-outfit wardrobe)
- **角色卡模板再升级（59 个模板）**：完整设定总表追加 **剪影区 / 动作姿态区 / 局部细节放大区**（Krea2 全能动态设计表方法论），新增「单图转多视角设计表」「剪影设计」2 个模板 / Character-sheet templates re-upgraded: the full reference sheet now adds **silhouette / pose-action / detail-closeup zones** (Krea2 all-in-one dynamic sheet methodology), plus 2 new templates (single-reference to multi-view, silhouette design)
- **艺术风格模板库（74 个模板）**：参照 ComfyUI EasyUse 风格库体系新增 **「艺术风格」分类 15 个风格模板**（现代日式动漫 / 吉卜力治愈风 / 日漫黑白漫画 / 美式漫画 / 铅笔素描 / 炭笔素描 / 照片写实 / 电影感胶片 / 古典油画 / 水彩插画 / 中国水墨 / 浮世绘 / 赛博朋克霓虹 / 像素艺术 / 3D 皮克斯动画），海报墙同步新增「艺术风格」分类与动态统计 / Art-style template library (74 templates): new **Art Styles** category with 15 style templates (modern anime / Ghibli / manga B&W / US comic / pencil sketch / charcoal / photoreal / film still / classical oil / watercolor / Chinese ink wash / ukiyo-e / cyberpunk / pixel art / 3D Pixar), poster wall now has the Art Styles filter and live stats

---

## ✨ 功能特性

### 🔥 支持千问家族全部模型

本插件的 **本地 LLaMA 后端** 支持千问家族全系列多模态模型的本地推理与图像反推：

| 模型系列 | Chat Handler | 说明 |
|---|---|---|
| **Qwen 3.8-VL** | `Qwen35ChatHandler` | 最新旗舰多模态，27B / 7B 等规格 |
| **Qwen 3.6-VL** | `Qwen35ChatHandler` | 高效多模态，支持 MTP 加速 |
| **Qwen 3.5-VL** | `Qwen35ChatHandler` | 9B / 72B 等，官方 PE 底层 |
| **Qwen 3-VL** | `Qwen3VLChatHandler` | 第三代多模态 |
| **Qwen 2.5-VL** / **Qwen 2-VL** | `Qwen25VLChatHandler` | 经典多模态系列 |

同时兼容其他主流多模态模型：
- **Gemma 4** / **Gemma 3** — `Gemma4ChatHandler`
- **GLM-4.6V / 4.1V** — 通用 mtmd handler
- **MiniCPM-V4.5 / V2.6** — 专用 handler
- **LFM 2.5V / 2V** — 通用 mtmd handler
- **Step 3V** — 通用 mtmd handler
- **LLaVA 1.5 / 1.6** — 专用 handler
- 以及更多 llama-cpp-python 支持的模型

> 💡 **自动识别**：`chat_handler` 选 `auto` 时，节点按模型名自动匹配对应 handler，开箱即用。

### 🎯 三大后端

| 后端 | 特点 | 适用场景 |
|---|---|---|
| **官方 PE** | 本地加载 Qwen Image 2.1 PE 权重，按官方 8 步规则增强 | 追求官方效果、有显卡跑 PE |
| **本地 LLaMA** | 本地 GGUF + mmproj，支持千问全系列多模态模型 | 离线使用、图像反推、自定义模型 |
| **API** | OpenAI 兼容接口（如阿里云百炼） | 在线服务、无需本地显存 |

### 📚 内置模板库（102 个模板，10 大分类）

`Qwen Image 2.1 官方增强提示词模板` 节点内置 **102 个增强模板**：

#### ① 官方权威（5 个）
- Qwen-Image-2.1 官方 PE-T2I 系统规则（10KB 原文）
- Qwen-Image-2.1 官方 PE-I2I 系统规则（18KB 原文）
- 官方 API prompt_extend 改写风格（含示例）
- 官方 Prompt 公式：主体+场景+风格+镜头+氛围+细节
- 官方海报/幻灯片布局模板

#### ② 社区最佳实践（4 个）
- 社区通用六要素模板（Tensor.Art 最佳实践）
- 中文高质量描述技巧（Qwen-Image-Lightning）
- 风格混合模板（社区）
- 细节控制模板（社区）

#### ③ 设计模板（9 个，支持自定义变量）
- 短视频封面（9:16 竖版）
- 杂志封面（2:3 竖版）
- 书籍封面（2:3 竖版）
- 桌面壁纸（16:9 横版）
- 海报设计（2:3 竖版）
- 杂志内页跨页（3:2 横版）
- 宣传册封面（3:2 横版）
- 宣传册内页（3:2 横版）
- 户外广告看板（21:9 超宽）

#### ④ 电影资产（13 个，支持自定义变量）
- 电影剧照（16:9 单帧）
- 电影分镜板（3x2 带标注）
- 4 宫格分镜（2x2）
- 6 宫格分镜（3x2）
- 9 宫格分镜（3x3）
- 12 宫格分镜（4x3）
- 角色三视图（正/侧/背）
- 角色四视图（正/3-4/侧/背）
- 角色六视图（全身+头部特写）
- 道具三视图（正/侧/背）
- 道具四视图（正/3-4/侧/背）
- 道具六视图（正/侧/背+细节特写）
- 场景资产概念图

#### ⑤ 角色卡（16 个，支持自定义变量）
- 完整设定总表（三视图+表情+服装拆解+配色板）【已升级：融合 GPT Image 2 角色提示板 + Krea2 全能动态设计表方法论】
- 转面四视图（正/3-4/侧/背）
- 表情差分表（6/8 宫格）
- 服装与配饰细节拆解
- 角色配色板（含色卡）
- 一致性描述锚（50+词固定句，每次复用）
- 单张全身立绘
- 头像胸像特写
- 游戏卡牌/闪绘（splash art）
- 手游式 UI 角色卡（带信息面板）
- 姿势差分表（6 宫格动作）
- 古风/国风角色设定
- 心理特质四要素（心理特征/内在冲突/行为模式/情绪基线）【新增】
- 多套服装+叠穿设定（16:9 两套 / 21:9 三套）【新增】
- 单图转多视角设计表（参考图驱动补全）【新增】
- 剪影设计（轮廓/身材比例/外轮廓辨识）【新增】

#### ⑥ 电影海报（12 个风格，支持自定义变量）
- 标准竖版 One-Sheet
- 群像 Ensemble Cast
- 极简 Minimalist
- 分屏对比 Split-Screen
- 环境焦点 Environment Focus
- 奥斯卡剧情片 Oscar Drama
- 复古黑色电影 Vintage Noir
- 暑期大片 Summer Blockbuster
- 恐怖片 Horror
- 爱情片 Romance
- 科幻片 Sci-Fi
- 动画电影 Anime Film

#### ⑦ 艺术风格（15 个风格转换模板）【新增】
- 现代日式动漫（赛璐璐/清晰描线）
- 吉卜力治愈风（宫崎骏）
- 日漫黑白漫画（线稿+网点）
- 美式漫画（超级英雄漫画）
- 铅笔素描（排线明暗）
- 炭笔素描（浓黑氛围）
- 照片写实（photorealistic）
- 电影感胶片（cinematic film still）
- 古典油画（厚涂布面）
- 水彩插画（透明纸纹）
- 中国水墨（留白墨韵）
- 浮世绘（和风版画）
- 赛博朋克霓虹（未来都市）
- 像素艺术（16-bit 复古）
- 3D 皮克斯动画（渲染质感）

#### ⑧ 人物动作姿势（16 个姿势锚点模板）【新增 · 全球全网姿势体系归纳】
- 自然站姿（Contrapposto 重心偏移）
- 双手叉腰站姿（自信开放）
- 英雄力量站姿（Power Stance 低角度）
- 椅坐（翘腿/叠腿从容）
- 地面盘坐（蝴蝶坐/正坐/割座）
- 悬坐翘腿（Figure Four 俏皮）
- 单膝跪姿 / 蹲匍（庄重/潜行）
- 侧卧躺姿（慵懒放松）
- 行走奔跑位移（动势引导）
- 跳跃腾空（动感对角线）
- 格斗战斗架势（拳击/武术）
- 手势特写（比耶/指向等）
- 情绪演绎（欢呼/庆祝等表演状态）
- 舞蹈体育（芭蕾阿拉贝斯克等）
- 动态瞬间（回眸抓拍/慢动作）
- 双人互动（背靠背/对视等）

#### ⑨ 灵感精选（12 个 Web 灵感模板）【新增 · 全球全网真实提示词提取】
- 东方神话人物志百科海报（AI2Image #415）
- 中世纪复古旅行海报（AI2Image #418）
- 室内晨间写实摄影（AI2Image #414）
- 极简建筑地标海报（AI2Image #411）
- 日系手绘涂鸦半身插画（AI2Image #423）
- Cozy Academia 学习手记（AI2Image #408）
- 品牌户外广告信息图（Prompt123 #1223）
- 动漫数字海报网格（Prompt123 #975）
- 吉卜力田园治愈风（Prompt123 风格标签）
- 水墨工笔花鸟（Prompt123 风格标签）
- 极简现代主义版式（Prompt123 风格标签）
- 水彩植物图鉴（Prompt123 风格标签）

### 模板变量替换

设计/电影/角色类模板内置 `{{TITLE}}` `{{SUBTITLE}}` `{{BRAND}}` `{{MAIN_SUBJECT}}` `{{COLOR}}` `{{STYLE}}` 等占位符。
在节点的 **variables** 输入框按 `KEY: value` 逐行填写，节点自动替换并输出完整 SYSTEM_PROMPT：

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
- 输出的 SYSTEM_PROMPT 接入增强节点的 `system_template`
- 若需用自己的照片作主视觉，把图片接到增强节点的 `image_1` 输入

> 💡 想修改模板内容（覆盖 / 追加要求 / 改库文件 / 新增模板）？详见 [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md)。

### 🖼 模板海报墙（可视化选择器）

模板节点自带 **可视化海报墙**，点击节点上的「🖼 打开模板海报墙」按钮即可弹出：

| 功能 | 说明 |
|---|---|
| **大图预览** | 102 个模板全部配有缩略图，一眼看清版式布局 |
| **分类筛选** | 10 大分类一键切换：全部 / 官方规则 / 官方文档 / 社区实践 / 设计版式 / 电影资产 / 角色卡 / 电影海报 / 艺术风格 / 人物姿势 / 灵感精选 |
| **点击即用** | 点击任意卡片自动回填到节点，无需手动选择下拉 |
| **中英双语** | 右上角 🌐 切换使用说明语言 |
| **变量提示** | 每张卡片显示该模板支持的所有变量名 |

海报墙路径：`web/templates_wall.html`

## 📦 安装

1. 将本插件放入 `ComfyUI/custom_nodes/` 目录：
   ```
   ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer/
   ```

2. **依赖**：
   - **官方 PE 后端**：ComfyUI 0.37.0 及以上（内置 Qwen Image 2.1 PE 支持）
   - **本地 LLaMA 后端**：需安装 `llama-cpp-python`（推荐 0.3.36+，以支持 Qwen 3.5/3.6/3.8 全系列）
     ```bash
     pip install llama-cpp-python
     ```
   - **API 后端**：无额外依赖

3. 重启 ComfyUI

## 🚀 使用方法

### 方式一：官方 PE 后端（文生图 / 图生图增强）

1. 将 PE 权重放入 `ComfyUI/models/text_encoders/`：
   - `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors`（文生图）
   - `qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors`（图生图）

2. 用 `CLIPLoader` 加载 PE 权重，接到节点的 `clip` 输入
3. `backend` 选 `官方PE`，填写提示词 → 运行

### 方式二：本地 LLaMA 后端（千问全系列反推 / 增强）

1. 将 GGUF 模型和 mmproj 投影器放入 `ComfyUI/models/LLM/`（**相对路径**）：
   ```
   ComfyUI/models/LLM/
   ├── Qwen3.8-27B-Instruct-Q6_K_L.gguf
   └── Qwen3.8/
       └── Qwen3.8-27B-f16_mmproj.gguf
   ```

2. 添加 `BSAI Qwen Prompt Enhancer` 节点：
   - `backend` 选 `本地LLaMA (GGUF + mmproj)`
   - `llm_model_name` 下拉选择主模型 GGUF
   - `mmproj_name` 选择对应的 mmproj（多模态反推必填）
   - `chat_handler` 选 `auto`（自动匹配千问系列专用 handler）
   - 接入 `image_1` ~ `image_16` 进行图像反推（最多 16 张图）

3. 运行即可得到增强后的提示词或图片反推描述

> 💡 **MTP 层自动处理**：含 MTP/NextN 预测层的模型（如 Qwen 3.6/3.8 CRACK 版）会自动检测并生成去 MTP 版本（`-noMTP.gguf`），兼容各版本 llama-cpp-python。

### 方式三：API 后端

1. `backend` 选 `API`
2. 填写 `api_base`、`api_key`、`api_model_name`
3. 支持 OpenAI 兼容接口（阿里云百炼、本地 vLLM/Ollama 等）
4. 同样支持多图输入

## 📁 目录结构

```
BSAI_Qwen_Prompt_Enhancer/
├── __init__.py                  # 节点注册
├── common.py                    # 公共工具：规则加载/消息构造/输出解析/图片转换
├── nodes_enhancer.py            # 三合一增强节点（官方PE / 本地LLaMA / API）
├── nodes_template.py            # 模板库节点
├── system_prompts/              # 官方 PE-T2I/I2I system_prompt 原文
├── templates/                   # 模板库（cinema / design / 官方公式）
├── web/                         # 前端 JS + 缩略图
├── examples/                    # 示例工作流
└── README.md
```

## 🔧 节点输出

增强节点统一输出 10 路：

| 输出 | 说明 |
|---|---|
| `ENHANCED_PROMPT` | 增强后的提示词（可直接接 KSampler positive） |
| `WH_RATIO` | 输出的宽高比（文生图模式时） |
| `RATIO_FOLLOW` | 是否按参考图比例输出 |
| `RAW_OUTPUT` | 模型原始输出 JSON |
| `THINKING` | 模型思考过程（thinking 模式时返回） |
| `RECOMMENDED_STEPS` | 推荐的采样步数（随 speed_preset 档位联动） |
| `RECOMMENDED_CFG` | 推荐的 CFG 值（Qwen Image 2.1 为 1.0） |
| `RECOMMENDED_SAMPLER` | 推荐的采样器（euler） |
| `RECOMMENDED_SCHEDULER` | 推荐的调度器（simple） |
| `MERGED_TEXT` | 模板原文 + 用户要求拼接文本（可直接接下游文本节点） |

> KSampler 上右键 `steps`/`cfg` → Convert to input，接上 `RECOMMENDED_STEPS`/`RECOMMENDED_CFG`，切换 speed_preset 档位即自动联动采样参数。


## ⚠️ 仅预览（preview_only）模式

`preview_only`（仅预览）开启时，**所有后端都不会调用模型**，节点直接输出文本预览，不做任何增强：

- `ENHANCED_PROMPT` = 你的原始 `prompt_text`（原文直出，不增强）
- `MERGED_TEXT` = 模板 + 用户要求拼接（无模板时为空）
- 开启时节点会**变红**并提示"未增强"，防止误用

**适用场景**：模板海报墙选卡时的快速预览、查看模板拼接效果。
**正式出图必须关闭「仅预览」**，否则官方PE / 本地LLaMA 不会真正增强，出图用的是你的原文。

> 提示：用模板海报墙选模板会自动勾选「仅预览」用于秒出预览，选完记得关闭再出图。

## 📝 说明

- 模型目录全部使用 **相对路径**（`models/LLM/`、`models/text_encoders/`），插件移动到任何位置都能正常工作
- 与 BSAI 系列其他插件的 Qwen 反推逻辑完全对齐，加载参数一致
- 支持 `keep_loaded` 保持模型驻留显存，批量处理时不用反复加载

## ⚡ 加速指南（Qwen Image 2.1 最新升级）

Qwen Image 2.1（7B DiT）为 **CFG-distilled 架构**，官方 day-0 推荐参数为 **25步 / cfg=1.0 / euler / simple**。
**不要再用旧版 20B 的 cfg=3~4**，否则会过饱和、过曝、构图僵硬，且每步要多跑一次模型前向。

### 内置 11 档加速预设（speed_preset）

选档后 `RECOMMENDED_STEPS` / `RECOMMENDED_CFG` 直接输出对应参数，KSampler 接线即可联动：

| 档位 | steps | 用途 |
|---|---|---|
| 官方标准 25步/CFG1（默认） | 25 | 日常出图（官方推荐，画质最优） |
| 快速 15步/CFG1 | 15 | 迭代预览，更快 |
| 极速 10步/CFG1 | 10 | 快速草稿（画质略降） |
| 高质量 35步/CFG1 | 35 | 精细出图 |
| 缓存加速 20步/CFG1 | 20 | 配合 EasyCache / Cache 节点 |
| Lightning 8/4步/CFG1 | 8/4 | 待 2.1 专用 Lightning LoRA 发布后使用 |
| 旧版兼容档 ×4 | 修正值 | 保留旧 key，防旧工作流失效 |

### 推荐模型与叠加加速（按收益排序）

1. **模型用官方 int8 convrot 版**：`qwen_image_2.1_int8_convrot.safetensors`（显存减半、更快）
2. **启动参数**：`--fast --use-sage-attention`（fused kernels + SageAttention 注意力加速，采样阶段快 20-40%）
3. **TE-Speed QwenImage21 节点**（第三方，输出预测缓存）：接线 `UNETLoader → QwenImage21Cache → TE-Speed → KSampler`，提速 30-40%
4. **EasyCache / KV Cache**：ComfyUI 内置 `QwenImage21Cache`，编辑工作流加速明显
5. **torch.compile**：`TorchCompileModel` 节点，10-30%（首次编译有冷启动）

### 参考速度

RTX 4090 / 1024×1024 / int8 / 25步 ≈ **7.5 秒/张**；叠加 SageAttention + EasyCache 后约 **4-5 秒**。

### ⚠️ 注意事项

- **2.1 专用 Lightning LoRA 尚未发布**（预计 2-6 周），当前选 8/4 步档会出噪图
- **勿用旧版 20B Lightning LoRA**（如 `Qwen-Image-Lightning-8steps-V2.0`，架构不同，权重形状不匹配）
- **勿用 TeaCache**（已冻结 14 个月，不兼容 2.1）
- ComfyUI 需 **v0.37.0+** 才原生支持 2.1

详细加速方案与硬件实测见 [ACCELERATION_GUIDE.md](ACCELERATION_GUIDE.md)，技术调研见 [RESEARCH_REPORT.md](RESEARCH_REPORT.md)。模板机制与修改方法见 [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md)。


---

## ❓ 常见问题 / Troubleshooting

### Q：打开工作流报错 `Value not in list: hf_model_name: 'Florence-2-base [...]' not in ['<未发现 HF 模型>']`，节点弹红框「无效输入」，控制台刷 `Output will be ignored`？

**原因**：工作流是在**另一台电脑**保存的，`hf_model_name`（本地 HF 后端）选了 `Florence-2-base [Florence2ForConditionalGeneration]`；当前电脑的 `ComfyUI/models/LLM` 下**没有该模型**（未下载 / 目录不同），下拉列表只剩 `<未发现 HF 模型>`，ComfyUI 校验失败 → 红框 + 整图被忽略。

**✅ 一键解决（v1.01+，无需任何手动操作）**：升级到 **v1.01**，插件内置两层自愈：

1. **后端放行**：`VALIDATE_INPUTS` 跳过 combo 的 value-in-list 校验 → 开图不再红框、不再阻塞整图；
2. **前端自动重置**：加载工作流时把非法下拉值自动重置为当前列表首项，并在节点 tooltip 提示「下拉选项已自动重置」。

升级后打开工作流即恢复正常，在 `hf_model_name` 下拉里重新选择本机实际存在的模型即可。

**手动解决（根治）**：把 Florence-2 模型放入 `ComfyUI/models/LLM/`（目录结构：`models/LLM/<模型目录>/model.safetensors` + `config.json` 等 Transformers 目录格式）。下载参考：

```
pip install -U huggingface_hub
hf download microsoft/Florence-2-base --local-dir ComfyUI/models/LLM/Florence-2-base
```

### Q：其他下拉也报 `Value not in list`？

同一原因（旧存档值不在当前选项列表，如模板库版本变化后的 `system_template`、模型目录变化后的 `llm_model_name`）。v1.01 对**全部下拉**统一做了自愈，重启 ComfyUI 后打开工作流即自动重置，无需手动改节点。

---

## v1.01 (2026-09-24) — 一键兼容旧工作流 / One-click compatibility for saved workflows

- **修复跨电脑打开工作流红框报错**：combo 存档值不在当前选项列表（典型：另一台电脑选了 Florence-2，本机未下载该模型）时，不再弹「无效输入」/ 刷 `Value not in list` / `Output will be ignored`。后端 `VALIDATE_INPUTS` 放行 + 前端加载时自动重置非法下拉值，开图即用 / Fixes red-frame validation errors when opening workflows saved on another PC (stored combo values missing on this machine, e.g. Florence-2 not downloaded): backend VALIDATE_INPUTS pass-through + frontend auto-reset of invalid combo values on load.
- **README 双语新增疑难解答** / Bilingual troubleshooting added.
