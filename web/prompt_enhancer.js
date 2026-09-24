// BSAI Qwen Prompt Enhancer — 合并节点前端扩展
// 1) backend 下拉切换时，动态显隐后端专属 widget（widget.options.hidden，与官方
//    CreateBoundingBoxes 扩展同款机制，支持新版 Vue 前端）
// 2) 注入"打开模板海报墙"按钮，选模板后自动回填 system_template 下拉
// 3) 海报墙选模板时同步把模板节点（QwenImage21_Prompt_Template）的预览跑一次，
//    让挂 Show Text 的下游立刻看到模板原文 + 合并后的 MERGED_TEXT
import { app } from "/scripts/app.js";

const MERGED_NODE = "BSAI_Qwen_Prompt_Enhancer";
const TEMPLATE_NODE = "QwenImage21_Prompt_Template";
const WALL_BUTTON_LABEL = "🖼 打开模板海报墙";

// 公共参数：四个后端始终可见
const COMMON_WIDGETS = [
  "backend",
  "prompt_text",
  "system_template",
  "custom_system_prompt",
  "user_requirement",
  "preview_only",
  "temperature",
  "top_p",
  "top_k",
  "repeat_penalty",
  "seed",
  "max_tokens",
  "speed_preset",
];

// backend 值（必须与 nodes_enhancer.py 的 BACKEND_LABELS 完全一致）-> 该后端可见的 widget 名
const BACKEND_WIDGET_GROUPS = {
  "官方PE (本地 Qwen3.5-9B)": COMMON_WIDGETS.concat(["pe_mode", "min_p", "thinking", "mtp"]),
  "本地LLaMA (GGUF+mmproj)": COMMON_WIDGETS.concat([
    "llm_model_name", "mmproj_name", "chat_handler",
    "n_ctx", "n_gpu_layers", "load_mtp", "keep_loaded",
  ]),
  "本地HF (Transformers)": COMMON_WIDGETS.concat([
    "hf_model_name", "hf_task", "hf_device", "hf_keep_loaded",
  ]),
  "API (OpenAI兼容)": COMMON_WIDGETS.concat(["api_base", "api_key", "api_model_name", "timeout"]),
};

function isMergedNode(node) {
  const cls = node?.comfyClass || node?.constructor?.comfyClass;
  return cls === MERGED_NODE;
}

function isTemplateNode(node) {
  const cls = node?.comfyClass || node?.constructor?.comfyClass;
  return cls === TEMPLATE_NODE;
}

function setWidgetHidden(widget, hidden) {
  widget.hidden = hidden;
  if (!widget.options) widget.options = {};
  widget.options.hidden = hidden;
}

/**
 * 【v1.01】combo 自愈：工作流存档里的下拉值在当前选项列表中不存在时（典型：
 * hf_model_name 存档为 'Florence-2-base [...]' 但本机 models/LLM 下没有该模型，
 * 列表只剩 '<未发现 HF 模型>'），ComfyUI 会报 "Value not in list" 红框并阻塞整图。
 * 这里在加载工作流时自动把非法值重置为当前列表首项（不弹窗、不打断），
 * 用户重新下拉选择真实模型即可；配合后端 VALIDATE_INPUTS 放行实现开图即用。
 */
function autoFixComboValues(node) {
  if (!node || !Array.isArray(node.widgets)) return 0;
  let fixed = 0;
  for (const w of node.widgets) {
    if (!w || w.type !== "combo" || !w.options || !Array.isArray(w.options.values)) continue;
    const vals = w.options.values;
    if (!vals.length || vals.includes(w.value)) continue;
    const old = w.value;
    w.value = vals[0];
    if (typeof w.callback === "function") { try { w.callback(w.value); } catch (_) {} }
    if (Array.isArray(node.widgets_values)) {
      const i = node.widgets.indexOf(w);
      if (i >= 0) node.widgets_values[i] = w.value;
    }
    try { node.setDirtyCanvas?.(true, true); } catch (_) {}
    console.log(
      `[BSAI.PromptEnhancer] 自愈 combo '${w.name}': '${old}' -> '${vals[0]}'（存档值不在当前选项，已自动重置）`
    );
    fixed++;
  }
  if (fixed > 0) {
    node.tooltip = `⚠ ${fixed} 个下拉选项已自动重置（旧存档值对应的模型/模板在本机不可用），请重新选择。`;
    try { node.setDirtyCanvas?.(true, true); } catch (_) {}
  }
  return fixed;
}

/**
 * 【v1.06.0】数值 widget 类型自愈：threads / timeout / seed / max_tokens 等 INT/FLOAT 参数，
 * 旧工作流存档里若为字符串/布尔/null（典型报错："无效输入 / 输入值类型错误"），
 * 自动重置为默认 number，并同步 widgets_values —— 开图不红框、不阻塞整图。
 */
function autoFixNumericValues(node) {
  if (!node || !Array.isArray(node.widgets)) return 0;
  let fixed = 0;
  for (const w of node.widgets) {
    if (!w) continue;
    const t = w.type;
    const isNum = t === "number" || t === "slider" || t === "INT" || t === "FLOAT";
    if (!isNum) continue;
    const v = w.value;
    if (typeof v === "number" && Number.isFinite(v)) continue;
    let def = 0;
    if (w.options && typeof w.options.default !== "undefined" && typeof w.options.default === "number") {
      def = w.options.default;
    }
    const old = v;
    w.value = def;
    if (typeof w.callback === "function") { try { w.callback(w.value); } catch (_) {} }
    if (Array.isArray(node.widgets_values)) {
      const i = node.widgets.indexOf(w);
      if (i >= 0) node.widgets_values[i] = w.value;
    }
    try { node.setDirtyCanvas?.(true, true); } catch (_) {}
    console.log(
      `[BSAI.PromptEnhancer] 自愈数值 widget '${w.name}': ${JSON.stringify(old)} -> ${w.value}`
    );
    fixed++;
  }
  if (fixed > 0) {
    node.tooltip = `⚠ ${fixed} 个数值参数已自动重置为默认值（旧存档类型异常）。`;
    try { node.setDirtyCanvas?.(true, true); } catch (_) {}
  }
  return fixed;
}

function syncWidgetVisibility(node) {
  if (!isMergedNode(node)) return;
  const backendWidget = (node.widgets || []).find((w) => w.name === "backend");
  if (!backendWidget) return;
  const visible = BACKEND_WIDGET_GROUPS[backendWidget.value] || COMMON_WIDGETS;
  for (const w of node.widgets || []) {
    if (w.name === "backend") continue;
    if (w.type === "button" || w.name === WALL_BUTTON_LABEL) continue; // 海报墙按钮常显
    setWidgetHidden(w, !visible.includes(w.name));
  }
  // 强制重绘，让节点高度按可见 widget 重排
  if (node.graph) node.graph.setDirtyCanvas(true, true);
}

// 【2026-09-23】仅预览醒目警告：preview_only=true 时节点变红 + tooltip 提示"未增强"
const NODE_COLOR_DEFAULT = "#3f789e";
const NODE_BG_DEFAULT = "#353535";
const NODE_COLOR_PREVIEW = "#c04848";
const NODE_BG_PREVIEW = "#3a2626";
function syncPreviewWarning(node) {
  if (!isMergedNode(node)) return;
  const pv = (node.widgets || []).find((w) => w.name === "preview_only");
  if (!pv) return;
  const on = pv.value === true || pv.value === "true";
  if (on) {
    node.color = NODE_COLOR_PREVIEW;
    node.bgcolor = NODE_BG_PREVIEW;
    node.tooltip = "⚠ 仅预览模式已开启：所有后端均不调用模型，输出为原文直出。正式出图请关闭「仅预览」。";
  } else {
    node.color = NODE_COLOR_DEFAULT;
    node.bgcolor = NODE_BG_DEFAULT;
    node.tooltip = "";
  }
  try { node.setDirtyCanvas?.(true, true); } catch (_) {}
}

/**
 * 把「选模板 + 用户要求」的事件投递给「指定节点 + 模板节点」：
 *   1) 把 displayName 写到目标节点的 system_template（合并节点）或 template_name（模板节点）
 *   2) 把 userRequirementText 写到目标节点的 user_requirement（合并节点）+ 模板节点
 *   3) 触发一次 queuePrompt，让挂 Show Text 的下游立刻显示
 *
 * 匹配规则（按优先级）：
 *   1) URL 里 ?merged_id= 或 ?tnode_id= 显式指定节点 id
 *   2) 全图找第一个对应类节点
 */
function dispatchTemplateSelection(payload) {
  payload = payload || {};
  const templateNodeId = payload.templateNodeId || payload.tnode_id || "";
  const mergedNodeId   = payload.mergedNodeId   || payload.merged_id || "";
  const displayName    = payload.displayName    || "";
  const userRequirementText = payload.userRequirementText || "";
  try {
    if (!window.opener || window.opener.closed || !window.opener.app) {
      console.warn("[BSAI.PromptEnhancer] 海报墙未连接到 ComfyUI，无法触发预览");
      return false;
    }
    const openerApp = window.opener.app;
    const all = openerApp.graph._nodes || [];

    function findNode(cls, idHint) {
      if (idHint) {
        const n = openerApp.graph.getNodeById(Number(idHint));
        if (n) return n;
      }
      return all.find((n) => (n.comfyClass || n.constructor?.comfyClass) === cls);
    }

    const tnode   = findNode(TEMPLATE_NODE, templateNodeId);
    const mnode   = findNode(MERGED_NODE,   mergedNodeId);

    // 1) 模板节点：写回 template_name / user_requirement
    if (tnode) {
      const tplWidget = (tnode.widgets || []).find((w) => w.name === "template_name");
      if (tplWidget) {
        tplWidget.value = displayName;
        if (typeof tplWidget.callback === "function") tplWidget.callback();
      }
      const reqWidget = (tnode.widgets || []).find((w) => w.name === "user_requirement");
      if (reqWidget) {
        reqWidget.value = userRequirementText || reqWidget.value || "";
        if (typeof reqWidget.callback === "function") reqWidget.callback();
      }
    }

    // 2) 合并节点：写回 system_template / user_requirement
    if (mnode) {
      const sysW = (mnode.widgets || []).find((w) => w.name === "system_template");
      if (sysW) {
        sysW.value = displayName;
        if (typeof sysW.callback === "function") sysW.callback();
      }
      const reqW = (mnode.widgets || []).find((w) => w.name === "user_requirement");
      if (reqW) {
        reqW.value = userRequirementText || reqW.value || "";
        if (typeof reqW.callback === "function") reqW.callback();
      }
      // 【v3】同时勾上 preview_only → 让合并节点走「纯预览」路径，不调模型
      const pvW = (mnode.widgets || []).find((w) => w.name === "preview_only");
      if (pvW) {
        pvW.value = true;
        if (typeof pvW.callback === "function") pvW.callback();
      }
    }

    if (!tnode && !mnode) {
      console.warn("[BSAI.PromptEnhancer] 未找到模板/合并节点，无法推送预览");
      return false;
    }

    // 3) 触发一次工作流重算，让下游 Show Text 立即显示
    if (typeof openerApp.queuePrompt === "function") {
      try { openerApp.canvas?.setDirty?.(true, true); } catch (_) {}
      openerApp.queuePrompt();
    } else if (typeof openerApp.refreshComboInNodes === "function") {
      openerApp.refreshComboInNodes();
    }

    try { openerApp.canvas?.centerOnNode?.(mnode || tnode); } catch (_) {}
    return true;
  } catch (e) {
    console.warn("[BSAI.PromptEnhancer] 推送模板选择失败:", e);
    return false;
  }
}

// 暴露到 opener.app，海报墙 HTML 里可以稳定调用
// （避免每次都通过 opener 注入最新函数引用）
try {
  const _origReady = app.onReady;
  if (typeof _origReady === "function") {
    app.onReady = function (cb) {
      const r = _origReady.apply(this, arguments);
      try { app.__BSAI_PromptEnhancer_selectTemplate = dispatchTemplateSelection; } catch (_) {}
      return r;
    };
  } else {
    app.onReady = function (cb) {
      try { app.__BSAI_PromptEnhancer_selectTemplate = dispatchTemplateSelection; } catch (_) {}
    };
  }
  // 兜底：立即挂一次
  try { app.__BSAI_PromptEnhancer_selectTemplate = dispatchTemplateSelection; } catch (_) {}
} catch (e) {
  console.warn("[BSAI.PromptEnhancer] 暴露 selectTemplate 全局接口失败:", e);
}

app.registerExtension({
  name: "BSAI.PromptEnhancer.MergedNode",

  nodeCreated(node) {
    if (isMergedNode(node)) {
      // 1) backend 切换时同步显隐
      const backendWidget = (node.widgets || []).find((w) => w.name === "backend");
      if (backendWidget) {
        const origCallback = backendWidget.callback;
        backendWidget.callback = function (value, ...args) {
          const r = origCallback ? origCallback.call(this, value, ...args) : undefined;
          syncWidgetVisibility(node);
          return r;
        };
      }
      // 1b) preview_only 值变化时同步"仅预览"醒目警告（节点变红，提示未增强）
      const pvWidget = (node.widgets || []).find((w) => w.name === "preview_only");
      if (pvWidget) {
        const origPvCallback = pvWidget.callback;
        pvWidget.callback = function (value, ...args) {
          const r = origPvCallback ? origPvCallback.call(this, value, ...args) : undefined;
          syncPreviewWarning(node);
          return r;
        };
      }
      // 工作流加载时 widget 值在 nodeCreated 之后才回填，包一层 onConfigure 确保按存档的 backend 恢复显隐
      const origConfigure = node.onConfigure;
      node.onConfigure = function (...args) {
        const r = origConfigure ? origConfigure.apply(this, args) : undefined;
        autoFixComboValues(node);
        autoFixNumericValues(node);
        syncWidgetVisibility(node);
        syncPreviewWarning(node);
        return r;
      };
      syncWidgetVisibility(node);
      syncPreviewWarning(node);

      // 【v1.06.0】合并节点底部左侧「💾 保存为模板」：把当前提示词直接存为用户模板（user_templates/）
      function refreshTemplateCombo(savedName, savedId) {
        try {
          const sysW = (node.widgets || []).find((w) => w.name === "system_template");
          if (!sysW) return;
          fetch("/api/bsai/templates").then((r) => r.json()).then((j) => {
            const vals = ["无模板（清空输出，不使用系统规则）[none]"];
            for (const t of j.templates || []) vals.push(`${t.name} [${t.id}]`);
            sysW.options.values = vals;
            if (savedName && savedId) {
              const target = `${savedName} [${savedId}]`;
              if (vals.includes(target)) {
                sysW.value = target;
                if (typeof sysW.callback === "function") { try { sysW.callback(target); } catch (_) {} }
                if (Array.isArray(node.widgets_values)) {
                  const i = node.widgets.indexOf(sysW);
                  if (i >= 0) node.widgets_values[i] = target;
                }
              }
            }
            try { app.graph?.setDirtyCanvas?.(true, true); } catch (_) {}
          }).catch((e) => console.warn("[BSAI.PromptEnhancer] 刷新模板下拉失败:", e));
        } catch (e) {
          console.warn("[BSAI.PromptEnhancer] 刷新模板下拉异常:", e);
        }
      }
      try {
        node.addWidget("button", "💾 保存为模板", "", async () => {
          try {
            const gw = (n) => (node.widgets || []).find((x) => x.name === n);
            const sysW = gw("custom_system_prompt");
            const usrW = gw("user_requirement");
            const pvW = gw("prompt_text");
            let text = "";
            if (sysW && typeof sysW.value === "string" && sysW.value.trim()) text = sysW.value;
            else if (pvW && typeof pvW.value === "string" && pvW.value.trim()) text = pvW.value;
            if (!text.trim()) {
              alert("[BSAI] 请先在「自定义系统提示词」或「用户提示词」输入内容，再保存为模板。");
              return;
            }
            const name = prompt("模板名称（将保存到用户模板区 user_templates/）：", "");
            if (!name || !name.trim()) return;
            const desc = prompt("模板描述（可空，将显示在海报墙卡片）：", "用户自定义共享模板");
            const resp = await fetch("/bsai_save_user_template", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name: name.trim(), desc: (desc || "").trim(), text: text.trim() }),
            });
            const j = await resp.json();
            if (j && j.ok) {
              alert(`已保存为模板「${j.name}」→ user_templates/${j.file}\n下拉已自动选中，海报墙刷新后可见。`);
              refreshTemplateCombo(j.name, j.id);
            } else {
              alert("保存失败: " + ((j && j.message) || "未知错误"));
            }
          } catch (e) {
            console.warn("[BSAI.PromptEnhancer] 保存模板失败:", e);
            alert("保存失败: " + e.message);
          }
        });
      } catch (e) {
        console.warn("[BSAI.PromptEnhancer] 注入保存模板按钮失败:", e);
      }

      // 2) 模板海报墙按钮
      const widget = (node.widgets || []).find(
        (w) => w.name === "system_template" || w.name === "template"
      );
      if (!widget) return;
      try {
        node.addWidget("button", WALL_BUTTON_LABEL, null, () => {
          // 把当前节点 id 和 widget name 写到 URL，让海报墙能回填到正确位置
          // 同时让海报墙在选中卡片时把模板原文实时推送到模板节点预览
          // v1.04.0: 改用插件直达路由 /bsai_templates_wall —— 部分 ComfyUI 版本/网络环境下
          // /extensions/ 静态路由返回无效响应（ERR_INVALID_RESPONSE），直达路由由插件直接返回 HTML。
          const url =
            `/bsai_templates_wall` +
            `?node_id=${node.id}` +
            `&widget=${widget.name}` +
            `&merged_id=${node.id}` +
            `&tnode_id=${findFirstTemplateNodeId() || ""}`;
          window.open(url, "_blank", "width=1400,height=900,noopener=0");
        });
      } catch (e) {
        console.warn("[BSAI.PromptEnhancer] 注入海报墙按钮失败:", e);
      }
    }

    // 3) 模板节点：把 user_requirement 输入框放到「system_template」之下，并把
    //    它跟按钮「🖼 打开模板海报墙」对齐，方便用户一眼看到两处自定义输入。
    if (isTemplateNode(node)) {
      // 【v1.01】加载工作流时自愈 combo（template_name 旧值不在当前模板列表时自动重置）
      const tplOrigConfigure = node.onConfigure;
      node.onConfigure = function (...args) {
        const r = tplOrigConfigure ? tplOrigConfigure.apply(this, args) : undefined;
        autoFixComboValues(node);
        autoFixNumericValues(node);
        return r;
      };
      try {
        node.addWidget("button", WALL_BUTTON_LABEL, null, () => {
          // v1.04.0: 改用插件直达路由 /bsai_templates_wall
          const url =
            `/bsai_templates_wall` +
            `?tnode_id=${node.id}` +
            `&widget=template_name`;
          window.open(url, "_blank", "width=1400,height=900,noopener=0");
        });
      } catch (e) {
        console.warn("[BSAI.PromptEnhancer] 模板节点注入海报墙按钮失败:", e);
      }
    }

    // 4) 合并节点：新增「清除模板（恢复默认）」按钮
    //    通过 LiteGraph 原生 addWidget("button", label, callback) 注入，
    //    这种 button 的 callback 参数位置和 widget 类型不同，必须传 null 作为 value。
    //    callback 内手动修改 widget.value 并派发 change 事件让 Vue 重渲染。
    if (isMergedNode(node)) {
      try {
        // 【2026-09-23】清除 = 切到「无模板（清空输出）」，resolve_template 返回空 system prompt，
        // 右侧预览/输出随之清空（不再恢复官方默认模板）
        const NONE_TEMPLATE_DISPLAY = "无模板（清空输出，不使用系统规则）[none]";
        // LiteGraph 标准按钮 widget：第四个参数是 callback（注意不是第三参数 value）
        node.addWidget("button", "🧹 清除模板（清空输出）", "", () => {
          try {
            const sysW = (node.widgets || []).find(w => w.name === "system_template");
            if (!sysW) return;
            const pvW = (node.widgets || []).find(w => w.name === "preview_only");
            const isNone = sysW.value === NONE_TEMPLATE_DISPLAY;
            const pvOn = pvW && (pvW.value === true || pvW.value === "true");
            // 防重复触发：已是「无模板」且「仅预览」已关 → 无动作，不 queuePrompt（避免反复出图）
            if (isNone && !pvOn) {
              console.log("[BSAI.PromptEnhancer] 清除模板按钮：已是无模板且仅预览已关，跳过运行");
              return;
            }
            // ① system_template -> 无模板（清空输出）：只走标准变更通知，不手动调 onChange
            sysW.value = NONE_TEMPLATE_DISPLAY;
            if (typeof sysW.callback === "function") {
              try { sysW.callback(NONE_TEMPLATE_DISPLAY); } catch (_) {}
            }
            // ② preview_only -> 关（清除模板时一并退出「仅预览」，恢复正式出图，
            //    消除海报墙自动勾选遗留的直出状态）
            if (pvW && pvOn) {
              pvW.value = false;
              if (typeof pvW.callback === "function") {
                try { pvW.callback(false); } catch (_) {}
              }
              syncPreviewWarning(node);
            }
            // 兼容更新 graph widgets_values
            if (Array.isArray(node.widgets_values)) {
              const i1 = node.widgets.indexOf(sysW);
              if (i1 >= 0) node.widgets_values[i1] = NONE_TEMPLATE_DISPLAY;
              if (pvW) {
                const i2 = node.widgets.indexOf(pvW);
                if (i2 >= 0) node.widgets_values[i2] = false;
              }
            }
            // ③ 不自动 queuePrompt：清除模板只复位状态，是否运行由用户手动 Queue
            //    （避免误触发 LLM 真增强/反复出图）
            try { app.graph?.setDirtyCanvas?.(true, true); } catch (_) {}
            console.log("[BSAI.PromptEnhancer] 清除模板按钮执行：system_template -> 无模板, preview_only -> 关");
          } catch (e) {
            console.warn("[BSAI.PromptEnhancer] 清除模板按钮执行失败:", e);
          }
        });
      } catch (e) {
        console.warn("[BSAI.PromptEnhancer] 注入清除模板按钮失败:", e);
      }
      // 【v1.06.0】合并节点底部右侧「⬆ 上传模板」：选择本地 .json 模板，直接写入 user_templates/
      try {
        node.addWidget("button", "⬆ 上传模板", "", () => {
          try {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".json,application/json";
            input.style.display = "none";
            document.body.appendChild(input);
            input.onchange = async () => {
              try {
                const file = input.files && input.files[0];
                if (!file) return;
                const fd = new FormData();
                fd.append("file", file);
                const resp = await fetch("/bsai_upload_user_template", { method: "POST", body: fd });
                const j = await resp.json();
                if (j && j.ok) {
                  alert(`已上传模板 → user_templates/${(j.files || []).join(", ")}\n下拉已刷新，海报墙刷新后可见。`);
                  refreshTemplateCombo();
                } else {
                  alert("上传失败: " + ((j && j.message) || "未知错误"));
                }
              } catch (e) {
                console.warn("[BSAI.PromptEnhancer] 上传模板失败:", e);
                alert("上传失败: " + e.message);
              } finally {
                try { document.body.removeChild(input); } catch (_) {}
              }
            };
            input.click();
          } catch (e) {
            console.warn("[BSAI.PromptEnhancer] 触发上传模板失败:", e);
          }
        });
      } catch (e) {
        console.warn("[BSAI.PromptEnhancer] 注入上传模板按钮失败:", e);
      }
    }
  },
});


/**
 * 找当前工作流里第一个 QwenImage21_Prompt_Template 节点 id，
 * 给合并节点的「打开海报墙」按钮写入 tnode_id，海报墙选中卡片时直接推送预览。
 */
function findFirstTemplateNodeId() {
  try {
    const graph = app.graph;
    const all = graph?._nodes || [];
    const tnode = all.find((n) => isTemplateNode(n));
    return tnode?.id;
  } catch (_) {
    return null;
  }
}
