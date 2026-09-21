---
base_model:
- ""
license: other
license_link: LICENSE
license_name: qwen-research
tags:
- qwen
- prompt-rewriting
- text-to-image
---

<p align="center">
    <img src="https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-Image/image2.1/logo.png" width="400"/>
</p>
<p align="center">
    🤖 <a href="https://modelscope.cn/models/Qwen/Qwen-Image-2.1">ModelScope</a>&nbsp;&nbsp;|
    &nbsp;&nbsp;🤗 <a href="https://huggingface.co/Qwen/Qwen-Image-2.1">HuggingFace</a>&nbsp;&nbsp;|
    &nbsp;&nbsp;📑 <a href="https://qwen.ai/blog?id=qwen-image-2.1">Blog</a>&nbsp;&nbsp;|
    &nbsp;&nbsp;🖥️ <a href="https://huggingface.co/spaces/Qwen/Qwen-Image-2.1">Demo</a>&nbsp;&nbsp;|
    &nbsp;&nbsp;🫨 <a href="https://discord.gg/CV4E9rpNSD">Discord</a>
</p>

## Introduction

We are excited to open-source **Qwen-Image-2.1**, a unified text-to-image generation and image editing model in the Qwen family. With just **7B parameters in its visual generation component** (32 Single-Stream DiT layers), Qwen-Image-2.1 balances generation quality, inference efficiency, and versatility.

Four key improvements define this release:

- **Compact and Efficient** — A lightweight architecture with mixed-granularity attention and prefix KV cache reuse delivers strong image quality at low computational cost.
- **Native Transparency, Unified Creation and Editing** — Generate regular or transparent (RGBA) images from text, edit transparent layers, and extract subjects from photographs—all in one model.
- **Versatile Editing** — Support up to **10 reference images**, specify local edits via circles, painted annotations, or separate masks, and preserve identity for people and products.
- **Realistic Textures and Refined Aesthetics** — Improved typography, portrait lighting, and fine details for more visually compelling results.

<p align="center">
    <img src="https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen-Image/image2.1/images/example-01.png" width="100%"/>
</p>

# Qwen-Image-2.1-PE-T2I

Text-to-image **prompt rewriting model** for [Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1). A fine-tuned Qwen3.5-VL 9B that turns a brief image request in any language into a detailed English prompt plus a recommended aspect ratio.

For more details, see the [GitHub repo](https://github.com/QwenLM/Qwen-Image-2.1) and [Blog](https://qwen.ai/blog?id=qwen-image-2.1).

## Quick Start

### Installation

```bash
pip install transformers>=5.4.0 torch>=2.4.0 accelerate pillow
```

### Usage with Transformers

```python
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "Qwen/Qwen-Image-2.1-PE-T2I"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id, dtype=torch.bfloat16, device_map="auto"
).eval()

# Load the system prompt shipped with the model
import huggingface_hub
sys_prompt_path = huggingface_hub.hf_hub_download(model_id, "system_prompt.txt")
system_prompt = open(sys_prompt_path).read().strip()

user_prompt = "一只在雨中弹吉他的柯基"

text = tokenizer.apply_chat_template(
    [{"role": "system", "content": system_prompt},
     {"role": "user", "content": user_prompt}],
    tokenize=False, add_generation_prompt=True, enable_thinking=True,
)
inputs = tokenizer(text, return_tensors="pt").to(model.device)

with torch.no_grad():
    out = model.generate(
        **inputs, max_new_tokens=16256,
        do_sample=True, temperature=1.0, top_p=0.95, top_k=20,
    )
gen = tokenizer.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)

# Split thinking from the answer
thinking, _, answer = gen.partition("</think>")
result = json.loads(answer.strip())
print(result)
# {"rewritten_prompt": "<long detailed English prompt>", "wh_ratio": "16:9"}
```

### Integration with Diffusers

```python
import json
import torch
from diffusers import QwenImage21Pipeline

WH_RATIO_TO_SIZE = {
    "1:1": (2048, 2048), "4:3": (2400, 1792), "3:4": (1792, 2400),
    "3:2": (2528, 1696), "2:3": (1696, 2528), "16:9": (2752, 1536),
    "9:16": (1536, 2752),
}

# Assuming `result` from above
prompt = result["rewritten_prompt"]
width, height = WH_RATIO_TO_SIZE.get(result["wh_ratio"], (2048, 2048))

pipe = QwenImage21Pipeline.from_pretrained(
    "Qwen/Qwen-Image-2.1", torch_dtype=torch.bfloat16
).to("cuda")

image = pipe(
    prompt=prompt,
    width=width, height=height,
    num_inference_steps=40,
    generator=torch.Generator("cuda").manual_seed(42),
).images[0]

image.save("rewritten_t2i.png")
```

### Output Format

The model outputs a JSON object after a `<think>` reasoning block:

```json
{
  "rewritten_prompt": "<long detailed English prompt describing the finished image>",
  "wh_ratio": "16:9"
}
```

- `rewritten_prompt` — the expanded prompt to pass to the image generation model
- `wh_ratio` — the recommended aspect ratio for rendering

## License

This model is licensed under the [Qwen Research License Agreement](./LICENSE).

