# -*- coding: utf-8 -*-
"""
Jev Mode (Structured Parallel Decision) engine for ComfyUI-llama-cpp_vlm.

原理 (源自 Codacus 的 llama.cpp "parallel decision" 分支 / Jev 模式):
  - 不要求模型逐 token 手写 JSON, 而是为每个字段构造 "字段名: " 前缀,
    让模型在该位置"续写"一个选项。
  - 一条记录 = 共享前缀(指令+Schema+上下文) + 所有字段的追加块,
    全部在**同一次前向遍历**中完成: 没有逐 token 生成循环,
    一次 decode 同时得到所有字段的 logits。
  - 只读取候选选项 token 的 logits, softmax 归一化得到置信度分数;
    模型不可能产生 Schema 之外的输出 (类型安全 / 无幻觉)。
  - 关键修正 (视频踩坑): 字段名与冒号必须一起 tokenize, 在选项实际
    开始分叉的位置切断并读取 logits, 而不是在冒号后直接切断。

兼容性说明: 当前 llama-cpp-python (JamePeng 0.3.36 CUDA 构建) 的单 batch
多序列 (multi-seq) 解码不可用 (decode 返回 1 / seq_cp assert 崩溃),
因此记录间的并行通过顺序解码 + 字段同遍历实现;
每条记录内部的所有字段仍共享同一次前向计算。

本模块直接操作底层 LlamaBatch / ctx.decode / get_logits_ith,
与 Llama.eval 的 Python 侧账本完全隔离;
每次调用前后都会清理 KV 缓存, 不污染后续聊天会话。
"""
import json
import numpy as np

import comfy.model_management as mm


# --------------------------------------------------------------------------
# Schema 解析
# --------------------------------------------------------------------------

def parse_schema(schema_text: str):
    """
    解析 Schema 文本。每行一个字段:
        field_name: option1|option2|option3
    返回:
        [{"name": str, "options": [str, ...]}, ...]
    """
    fields = []
    for line in schema_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(
                f"Jev Schema 行缺少 ':' 分隔符: {line!r}\n"
                f"正确格式: 字段名: 选项1|选项2|选项3"
            )
        name, _, opts = line.partition(":")
        name = name.strip()
        opts = [o.strip() for o in opts.split("|") if o.strip()]
        if not name:
            raise ValueError(f"Jev Schema 行字段名为空: {line!r}")
        if not opts:
            raise ValueError(
                f"Jev Schema 字段 {name!r} 没有选项 (每个字段至少 1 个选项): {line!r}"
            )
        fields.append({"name": name, "options": opts})
    if not fields:
        raise ValueError(
            "Jev Schema 为空。每行格式: 字段名: 选项1|选项2|选项3"
        )
    return fields


def _common_prefix_len(opt_token_lists):
    """返回所有选项 token 序列的最长公共前缀长度 (在分叉处切断)。"""
    if not opt_token_lists:
        return 0
    min_len = min(len(t) for t in opt_token_lists)
    c = 0
    while c < min_len:
        tk = opt_token_lists[0][c]
        if all(t[c] == tk for t in opt_token_lists):
            c += 1
        else:
            break
    return c


# --------------------------------------------------------------------------
# Jev 运行器 (单序列: 所有字段同一次遍历)
# --------------------------------------------------------------------------

class JevRunner:
    def __init__(self, llm):
        self.llm = llm
        self.ctx = llm._ctx
        self.n_vocab = llm.n_vocab()
        self.n_batch = max(1, getattr(llm, "n_batch", 2048))

    # -- token 工具 ---------------------------------------------------------

    def _tokenize(self, text: str, add_bos: bool = False):
        """以 UTF-8 令牌化文本 (与 Llama.tokenize 语义一致)。"""
        toks = self.llm.tokenize(text.encode("utf-8"), add_bos=add_bos, special=True)
        return list(toks)

    # -- 字段/选项准备 -------------------------------------------------------

    def _prepare_field(self, field):
        """
        预计算一个字段所需的全部信息:
          - head_tokens:    tokenize(f"{name}: ")  (字段名与冒号整体)
          - common_tokens:  所有选项共享的公共前缀 token (不含分叉 token)
          - fork_tokens:    每个选项在分叉位置对应的 token
          - single:         所有选项 token 完全相同 (无需评分, 直接取值)
        """
        name = field["name"]
        options = field["options"]
        opt_token_lists = [self._tokenize(o) for o in options]
        if any(len(t) == 0 for t in opt_token_lists):
            raise ValueError(
                f"Jev 字段 {name!r} 存在无法令牌化的选项: {options!r}"
            )

        head_tokens = self._tokenize(f"{name}: ")
        c = _common_prefix_len(opt_token_lists)

        # 所有选项完全同 token (视为单一选项)
        if all(len(t) == c for t in opt_token_lists):
            return {
                "name": name,
                "options": options,
                "head_tokens": head_tokens,
                "common_tokens": opt_token_lists[0],
                "fork_tokens": [None] * len(options),
                "single": True,
                "single_idx": 0,
            }

        common_tokens = opt_token_lists[0][:c]
        fork_tokens = [t[c] if len(t) > c else None for t in opt_token_lists]

        return {
            "name": name,
            "options": options,
            "head_tokens": head_tokens,
            "common_tokens": common_tokens,
            "fork_tokens": fork_tokens,
            "single": False,
            "single_idx": -1,
        }

    # -- 主入口 ---------------------------------------------------------------

    def run(self, prefix_text: str, fields, records, verbose=True):
        """
        对每条记录执行 Jev 结构化并行决策。

        Args:
            prefix_text: 指令 + Schema 定义
            fields:      parse_schema() 输出
            records:     list[str], 每条记录一个上下文
        Returns:
            list[dict], 与 records 一一对应:
                {"field_name": {"value": str, "confidence": float,
                                "scores": {option: prob}}}
        """
        if not records:
            return []

        prepared = [self._prepare_field(f) for f in fields]
        prefix_tokens = self._tokenize(prefix_text, add_bos=True)
        P = len(prefix_tokens)

        # 每条记录的总 token 数 (prefix + ctx + 所有字段块), 用于容量分块
        record_token_lens = []
        for ctx_text in records:
            ctx_tokens = self._tokenize(ctx_text, add_bos=False)
            blocks = [
                list(f["head_tokens"]) + list(f["common_tokens"])
                for f in prepared
            ]
            record_token_lens.append((ctx_tokens, blocks))

        results = []
        for r_i, (ctx_tokens, blocks) in enumerate(record_token_lens):
            seq_len = P + len(ctx_tokens) + sum(len(b) for b in blocks)
            if seq_len > self.n_batch:
                raise RuntimeError(
                    f"Jev: 单条记录 token 数 ({seq_len}) 超过 batch 容量 "
                    f"({self.n_batch})。请增大 Model Loader 的 n_batch 或缩短输入。"
                )
            if verbose:
                print(
                    f"[llama-cpp_vlm][Jev] Record {r_i + 1}/{len(records)}: "
                    f"prefix={P}, total={seq_len} tokens, fields={len(prepared)} "
                    f"(single pass)"
                )
            # 每条记录从干净的 KV 缓存开始 (Jev 为独立会话)
            try:
                self.llm.reset()
                if self.ctx is not None:
                    self.ctx.memory_clear(True)
            except Exception:
                pass
            results.append(self._decode_record(
                prefix_tokens, ctx_tokens, blocks, prepared
            ))

        return results

    # -- 单条记录: 一次遍历所有字段 ---------------------------------------------

    def _decode_record(self, prefix_tokens, ctx_tokens, field_blocks, prepared):
        batch = self.llm._batch
        batch.reset()

        pos = 0
        # 1) 共享前缀
        batch.add_sequence(
            token_array=prefix_tokens,
            pos_array=list(range(pos, pos + len(prefix_tokens))),
            seq_ids=[0],
            logits_array=[False] * len(prefix_tokens),
        )
        pos += len(prefix_tokens)

        # 2) 上下文
        if ctx_tokens:
            batch.add_sequence(
                token_array=ctx_tokens,
                pos_array=list(range(pos, pos + len(ctx_tokens))),
                seq_ids=[0],
                logits_array=[False] * len(ctx_tokens),
            )
            pos += len(ctx_tokens)

        # 3) 所有字段块, 块末 token 标记 logits (一次前向同时得到全部字段)
        marker_positions = []
        for block in field_blocks:
            n = len(block)
            lg = [False] * n
            lg[-1] = True
            batch.add_sequence(
                token_array=block,
                pos_array=list(range(pos, pos + n)),
                seq_ids=[0],
                logits_array=lg,
            )
            marker_positions.append(pos + n - 1)  # batch 全局位置
            pos += n

        # 4) 一次解码
        if mm.processing_interrupted():
            raise mm.InterruptProcessingException()
        status = self.ctx.decode(batch)
        if status != 0:
            raise RuntimeError(
                f"Jev decode failed with status {status} "
                f"(KV cache 不足? 请增大 n_ctx 或缩短输入)"
            )

        # 5) 读取每个字段的 logits (get_logits_ith 索引 = batch 全局 token 位置)
        record_result = {}
        for f, gpos in zip(prepared, marker_positions):
            ptr = self.ctx.get_logits_ith(gpos)
            if not ptr:
                raise RuntimeError(
                    f"Jev: get_logits_ith({gpos}) 返回 NULL, logits 未计算。"
                )
            logits = np.ctypeslib.as_array(ptr, shape=(self.n_vocab,)).copy()

            if f["single"]:
                val = f["options"][f["single_idx"]]
                record_result[f["name"]] = {
                    "value": val,
                    "confidence": 1.0,
                    "scores": {val: 1.0},
                }
                continue

            opt_logits = []
            for opt_idx, opt in enumerate(f["options"]):
                ft = f["fork_tokens"][opt_idx]
                if ft is None:
                    opt_logits.append(float("-inf"))
                    continue
                opt_logits.append(float(logits[ft]))

            arr = np.array(opt_logits, dtype=np.float64)
            arr = arr - arr.max()
            probs = np.exp(arr)
            probs = probs / probs.sum()
            best = int(np.argmax(probs))
            record_result[f["name"]] = {
                "value": f["options"][best],
                "confidence": float(probs[best]),
                "scores": {
                    opt: float(p) for opt, p in zip(f["options"], probs)
                },
            }

        return record_result


# --------------------------------------------------------------------------
# 结果格式化
# --------------------------------------------------------------------------

def build_prefix(system_prompt: str, instruction: str, fields) -> str:
    """构造共享前缀: 指令 + 字段定义。"""
    parts = []
    if system_prompt and system_prompt.strip():
        parts.append(system_prompt.strip())
    if instruction and instruction.strip():
        parts.append(instruction.strip())
    if fields:
        lines = ["Fields and allowed values:"]
        for f in fields:
            lines.append(f"- {f['name']}: {' | '.join(f['options'])}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts).strip()


def results_to_json(results):
    """仅输出值。"""
    if len(results) > 1:
        return json.dumps(
            [{k: v["value"] for k, v in rec.items()} for rec in results],
            ensure_ascii=False,
        )
    if results:
        return json.dumps(
            {k: v["value"] for k, v in results[0].items()},
            ensure_ascii=False,
        )
    return "{}"


def results_to_confidence_json(results):
    """完整输出: 值 + 置信度 + 各选项分数。"""
    if len(results) > 1:
        return json.dumps([
            {k: {
                "value": v["value"],
                "confidence": round(v["confidence"], 4),
                "scores": {o: round(s, 4) for o, s in v["scores"].items()},
            } for k, v in rec.items()}
            for rec in results
        ], ensure_ascii=False, indent=2)
    if results:
        rec = results[0]
        return json.dumps({
            k: {
                "value": v["value"],
                "confidence": round(v["confidence"], 4),
                "scores": {o: round(s, 4) for o, s in v["scores"].items()},
            } for k, v in rec.items()
        }, ensure_ascii=False, indent=2)
    return "{}"


def results_to_text(results, fields):
    """人类可读摘要。"""
    if len(results) > 1:
        lines = []
        for i, rec in enumerate(results):
            lines.append(f"===== Record {i + 1} =====")
            for f in fields:
                v = rec[f["name"]]
                lines.append(
                    f"{f['name']}: {v['value']}  (confidence {v['confidence'] * 100:.1f}%)"
                )
        return "\n".join(lines)
    if results:
        rec = results[0]
        lines = []
        for f in fields:
            v = rec[f["name"]]
            lines.append(
                f"{f['name']}: {v['value']}  (confidence {v['confidence'] * 100:.1f}%)"
            )
        return "\n".join(lines)
    return ""
