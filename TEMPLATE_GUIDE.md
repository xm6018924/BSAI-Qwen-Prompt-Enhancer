# 提示词模板修改指南（TEMPLATE_GUIDE）

本指南说明 BSAI Qwen Prompt Enhancer 的提示词模板机制，以及如何修改模板内容。
适用于四个后端（官方PE / 本地LLaMA / API / 本地HF）——模板解析逻辑完全共用，**修改模板不需要切换后端**。

---

## 一、模板机制总览

每个 BSAI 节点上有三个与模板相关的输入：

| 输入 | 作用 | 进不进 LLM 对话 |
|---|---|---|
| `system_template`（下拉） | 从模板库选一个内置模板 | 进 |
| `custom_system_prompt` | 非空时**完全覆盖**下拉模板，作为 system prompt | 进（覆盖模板） |
| `user_requirement` | **不覆盖模板**，作为「用户要求」追加到最终 MERGED_TEXT 输出 | 不进（拼进输出文本） |

### 模板解析优先级（`resolve_template`）

```
custom_system_prompt 非空
  → 用 custom_system_prompt 完全覆盖，template_id = "custom"
否则按 system_template 下拉值依次匹配：
  1. 模板「name 前缀」匹配（如 "电影海报 · 暑期大片 … [poster_blockbuster]"）
  2. 历史别名映射（旧显示名 → 模板 id，向后兼容旧工作流）
  3. 尾部 "[id]" 后缀匹配
  4. 兜底：官方 PE-T2I 规则
```

### user_requirement 拼接格式（`_build_merged_text`）

```
模板原文（解析后的 system prompt）
（空 user_requirement 时 merged == 模板原文）

【用户要求】
用户对当前任务的额外要求：
<你填写的内容>
（请务必在生成时满足以上用户要求。）
```

---

## 二、方式一：节点内临时修改（不碰任何文件，最常用）

在 BSAI 节点（或工作流中连到节点输入的前置文本框节点）上：

- **完全替换模板**：在 `custom_system_prompt` 填入你的 system prompt → 模板被整个覆盖。
  适合：想彻底改变 PE 的改写规则 / 换一套自己的规则。
- **保留模板 + 追加要求**：在 `user_requirement` 填入要求（如「标题改为XXX」「输出中文」「布局改成上下结构」）→ 模板不变，要求拼进最终输出。
  适合：模板整体可用，只补充本次的特殊要求。
- **换一个模板**：直接改 `system_template` 下拉选项。

> 工作流示例中：节点 [27]「自定义输入覆盖模板作为 system prompt 输出」对应 `custom_system_prompt`；
> 节点 [28]「修改提示词模板内容，优化模板输出」对应 `user_requirement`。

---

## 三、方式二：永久修改模板库文件

模板库根目录：

```
custom_nodes\BSAI_Qwen_Prompt_Enhancer\
├── system_prompts\                    # 官方 PE-T2I / PE-I2I 系统规则（逐字原文）
│   ├── qwen_image_2.1_pe_t2i_system_prompt.txt
│   └── qwen_image_2.1_pe_i2i_system_prompt.txt
├── templates\
│   ├── templates.json                 # 模板清单 + 内联模板文本
│   ├── design\*.txt                   # 设计类模板正文
│   └── cinema\*.txt                   # 电影类模板正文
└── web\template_texts.json            # 模板墙展示用内联文本（官方规则全文）
```

| 模板类型 | 正文在哪里 | 改哪里 |
|---|---|---|
| official（官方 PE 规则） | `system_prompts\*.txt`（templates.json 的 `file` 字段指向） | 直接编辑对应 txt |
| design / cinema（设计/电影/角色） | `templates\design\*.txt`、`templates\cinema\*.txt` | 直接编辑对应 txt |
| official-doc / community（官方文档/社区） | 内联在 `templates\templates.json` 的 `text` 字段 | 编辑 json 对应条目的 `text` |

修改后 **刷新 ComfyUI 页面**即可生效（下拉选项在页面加载时构建）；运行时读取不缓存，无需重启。

> 注意：官方 PE 规则文件是官方原文，改动后官方 PE 后端的系统规则也随之改变；
> 若同时使用模板墙（`web\template_texts.json` 里的官方全文），建议一并同步。

---

## 四、方式三：新增你自己的模板

在 `templates\templates.json` 的 `templates` 数组末尾追加一个条目：

```json
{
  "id": "my_custom_template",
  "name": "我的自定义模板",
  "type": "community",
  "text": "你是 AI 绘画提示词工程师……（模板正文）"
}
```

或把正文放到独立文件并用 `file` 字段引用：

```json
{
  "id": "my_custom_template",
  "name": "我的自定义模板",
  "type": "design",
  "file": "templates/design/my_custom_template.txt",
  "vars": ["TITLE", "STYLE"],
  "desc": "……"
}
```

刷新页面后，新模板即出现在 `system_template` 下拉中。

---

## 五、变量占位符 `{{KEY}}`

设计/电影/角色类模板正文中常含占位符，例如 `{{TITLE}}`、`{{MAIN_SUBJECT}}`、`{{COLOR}}`、`{{STYLE}}`（templates.json 的 `vars` 字段声明了该模板需要哪些变量）。

- 通过节点的 `variables` 输入填充，**每行一个**，格式 `KEY: 值`（KEY 不区分大小写，支持中文冒号）：

  ```
  TITLE: 夏日冰爽特辑
  MAIN_SUBJECT: 一杯冒气泡的柠檬汽水
  COLOR: 清凉蓝白
  ```

- 未提供的占位符会**原样保留**在提示词中（不会报错）。

---

## 六、后端差异（重要）

| 后端 | 模板修改 | 注意事项 |
|---|---|---|
| 官方PE | 全部生效 | 官方PE 是专用微调模型，**推荐保持官方规则模板**；用 `custom_system_prompt` 覆盖会偏离训练分布，且官方规则中的画幅比例表丢失后 `wh_ratio` 输出可能失效。I2I 模式且模板仍为默认 T2I 时会自动切换为官方 I2I 规则。 |
| 本地LLaMA | 全部生效 | 通用模型，任何模板都按字面执行，**最适合测试你改的模板效果**。 |
| API / 本地HF | 全部生效 | 同本地LLaMA。 |

**结论：修改模板内容不需要选择特定后端；想自由试验改后的模板效果，用本地LLaMA 最合适。**
