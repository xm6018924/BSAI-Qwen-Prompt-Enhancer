// BSAI Qwen Prompt Enhancer — 合并节点前端扩展
// 1) backend 下拉切换时，动态显隐后端专属 widget（widget.options.hidden，与官方
//    CreateBoundingBoxes 扩展同款机制，支持新版 Vue 前端）
// 2) 注入"打开模板海报墙"按钮，选模板后自动回填 system_template 下拉
import { app } from "/scripts/app.js";

const MERGED_NODE = "BSAI_Qwen_Prompt_Enhancer";
const TEMPLATE_NODE = "QwenImage21_Prompt_Template";
const WALL_BUTTON_LABEL = "🖼 打开模板海报墙";

// 公共参数：三个后端始终可见
const COMMON_WIDGETS = [
  "backend",
  "prompt_text",
  "system_template",
  "custom_system_prompt",
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

function setWidgetHidden(widget, hidden) {
  widget.hidden = hidden;
  if (!widget.options) widget.options = {};
  widget.options.hidden = hidden;
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

app.registerExtension({
  name: "BSAI.PromptEnhancer.MergedNode",

  nodeCreated(node) {
    if (!isMergedNode(node)) return;

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
    // 工作流加载时 widget 值在 nodeCreated 之后才回填，包一层 onConfigure 确保按存档的 backend 恢复显隐
    const origConfigure = node.onConfigure;
    node.onConfigure = function (...args) {
      const r = origConfigure ? origConfigure.apply(this, args) : undefined;
      syncWidgetVisibility(node);
      return r;
    };
    syncWidgetVisibility(node);

    // 2) 模板海报墙按钮
    const widget = (node.widgets || []).find(
      (w) => w.name === "system_template" || w.name === "template"
    );
    if (!widget) return;
    try {
      node.addWidget("button", WALL_BUTTON_LABEL, null, () => {
        const url =
          `/extensions/BSAI_Qwen_Prompt_Enhancer/templates_wall.html` +
          `?node_id=${node.id}&widget=${widget.name}`;
        window.open(url, "_blank", "width=1400,height=900,noopener=0");
      });
    } catch (e) {
      console.warn("[BSAI.PromptEnhancer] 注入海报墙按钮失败:", e);
    }
  },
});
