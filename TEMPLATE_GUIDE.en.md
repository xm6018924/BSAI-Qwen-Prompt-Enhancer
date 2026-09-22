# Prompt Template Modification Guide (TEMPLATE_GUIDE)

This guide explains the prompt template mechanism of the BSAI Qwen Prompt Enhancer and how to modify template content.
It applies to all four backends (Official PE / Local LLaMA / API / Local HF) — the template resolution logic is fully shared, **no backend switch is needed to modify templates**.

---

## 1. Template Mechanism Overview

Each BSAI node has three template-related inputs:

| Input | Effect | Sent into the LLM chat? |
|---|---|---|
| `system_template` (dropdown) | Pick a built-in template from the library | Yes |
| `custom_system_prompt` | When non-empty, **fully overrides** the dropdown template as the system prompt | Yes (overrides template) |
| `user_requirement` | Does **not** override the template; appended as "User Requirements" to the final MERGED_TEXT output | No (appended to output text) |

### Template resolution priority (`resolve_template`)

```
If custom_system_prompt is non-empty
  → used as-is (fully overrides the template), template_id = "custom"
Otherwise match the system_template dropdown value in order:
  1. Template "name" prefix match (e.g. "电影海报 · 暑期大片 … [poster_blockbuster]")
  2. Legacy alias map (old display name → template id, for backward compatibility)
  3. Trailing "[id]" suffix match
  4. Fallback: Official PE-T2I rules
```

### user_requirement concatenation format (`_build_merged_text`)

```
Resolved template text (system prompt after resolution)
(if user_requirement is empty, merged == template text)

【用户要求】
用户对当前任务的额外要求：
<your content>
（请务必在生成时满足以上用户要求。）
```

---

## 2. Method 1: Modify Per-Run on the Node (no files touched, most common)

On the BSAI node (or the text-input nodes wired into it in the workflow):

- **Fully replace the template**: fill in `custom_system_prompt` with your own system prompt → the template is completely overridden.
  Use when: you want to change the PE rewriting rules entirely / use your own rule set.
- **Keep the template + append requirements**: fill in `user_requirement` (e.g. "change title to XXX", "output in Chinese", "use a top-bottom layout") → the template stays intact, and the requirement is appended to the final output.
  Use when: the template is fine overall, you just need per-run extras.
- **Switch template**: change the `system_template` dropdown directly.

> In the example workflow: node [27] "自定义输入覆盖模板作为 system prompt 输出" maps to `custom_system_prompt`;
> node [28] "修改提示词模板内容，优化模板输出" maps to `user_requirement`.

---

## 3. Method 2: Permanently Edit Template Library Files

Template library root:

```
custom_nodes\BSAI_Qwen_Prompt_Enhancer\
├── system_prompts\                    # Official PE-T2I / PE-I2I system rules (verbatim originals)
│   ├── qwen_image_2.1_pe_t2i_system_prompt.txt
│   └── qwen_image_2.1_pe_i2i_system_prompt.txt
├── templates\
│   ├── templates.json                 # Template registry + inline template texts
│   ├── design\*.txt                   # Design template bodies
│   └── cinema\*.txt                   # Cinema template bodies
└── web\template_texts.json            # Inline texts for the template wall display (full official rules)
```

| Template type | Where the body lives | What to edit |
|---|---|---|
| official (Official PE rules) | `system_prompts\*.txt` (pointed to by the `file` field in templates.json) | Edit the matching txt directly |
| design / cinema | `templates\design\*.txt`, `templates\cinema\*.txt` | Edit the matching txt directly |
| official-doc / community | Inline in the `text` field of `templates\templates.json` | Edit the `text` field of the entry in the json |

After editing, **refresh the ComfyUI page** — the dropdown options are built at page load; runtime resolution reads the files without caching, so no restart is needed.

> Note: the Official PE rule files are verbatim originals; editing them changes the system rules used by the Official PE backend.
> If you also use the template wall (the official full texts in `web\template_texts.json`), sync that file too.

---

## 4. Method 3: Add Your Own Template

Append an entry to the `templates` array in `templates\templates.json`:

```json
{
  "id": "my_custom_template",
  "name": "My Custom Template",
  "type": "community",
  "text": "You are an AI image prompt engineer... (template body)"
}
```

Or store the body in a separate file referenced by the `file` field:

```json
{
  "id": "my_custom_template",
  "name": "My Custom Template",
  "type": "design",
  "file": "templates/design/my_custom_template.txt",
  "vars": ["TITLE", "STYLE"],
  "desc": "..."
}
```

After refreshing the page, the new template appears in the `system_template` dropdown.

---

## 5. Variable Placeholders `{{KEY}}`

Design/cinema/character template bodies often contain placeholders such as `{{TITLE}}`, `{{MAIN_SUBJECT}}`, `{{COLOR}}`, `{{STYLE}}` (the `vars` field in templates.json declares which variables a template needs).

- Fill them via the node's `variables` input, **one per line**, format `KEY: value` (KEY is case-insensitive; Chinese colons are accepted):

  ```
  TITLE: Summer Chill Special
  MAIN_SUBJECT: a glass of fizzy lemon soda
  COLOR: cool blue & white
  ```

- Unfilled placeholders are **left as-is** in the prompt (no error).

---

## 6. Backend Differences (Important)

| Backend | Template editing | Notes |
|---|---|---|
| Official PE | Fully supported | Official PE is a fine-tuned dedicated model — **keep the Official rule templates recommended**; overriding with `custom_system_prompt` deviates from its training distribution, and losing the official aspect-ratio table may break the `wh_ratio` output. In I2I mode with the default T2I template still selected, it auto-switches to the Official I2I rules. |
| Local LLaMA | Fully supported | A general model — any template is followed literally, **best for testing your edited templates**. |
| API / Local HF | Fully supported | Same as Local LLaMA. |

**Conclusion: modifying template content does not require selecting a specific backend; to freely experiment with your edited templates, Local LLaMA is the best choice.**
