# -*- coding: utf-8 -*-
"""BSAI Qwen Prompt Enhancer 插件导入验证脚本"""
import sys
sys.path.insert(0, r'C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI')
sys.path.insert(0, r'C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes')

import BSAI_Qwen_Prompt_Enhancer as P

print('节点注册:')
for k, v in P.NODE_CLASS_MAPPINGS.items():
    print('  ', k, '->', v.__name__)
print('显示名:')
for k, v in P.NODE_DISPLAY_NAME_MAPPINGS.items():
    print('  ', k, '=>', v)

from BSAI_Qwen_Prompt_Enhancer.common import (
    load_templates, resolve_template, build_official_chat, get_enhanced_result,
)

ts = load_templates()
print()
print('模板库条目数:', len(ts))
for t in ts:
    print('   - %s: %s' % (t['id'], t['name']))

sp, tid = resolve_template('Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]', '')
print()
print('T2I 官方规则解析: id=%s, 长度=%d, 开头=%r' % (tid, len(sp), sp[:60]))

sp_i, tid_i = resolve_template('Qwen-Image-2.1 官方 PE-I2I 系统规则 [official_i2i]', '')
print('I2I 官方规则解析: id=%s, 长度=%d, 开头=%r' % (tid_i, len(sp_i), sp_i[:60]))

chat = build_official_chat(sp, '一只橘猫', image_count=0, thinking=True)
print()
print('T2I 消息结尾:', repr(chat[-140:]))

chat2 = build_official_chat(sp_i, '把图1的女孩放进图2的场景', image_count=2, thinking=True)
idx = chat2.index('user') + 7
print('I2I 消息 user 段:', repr(chat2[idx:idx + 140]))

# PE 输出解析测试
sample = '<think>\nThe user wants a cat image.\n</think>\n\n{"rewritten_prompt": "A fluffy orange cat basking in warm sunlight on a windowsill, soft bokeh background, highly detailed", "wh_ratio": "3:2"}'
enhanced, wh, rf, raw, think = get_enhanced_result(sample)
print()
print('解析测试:')
print('  thinking:', think[:50])
print('  enhanced:', enhanced[:80])
print('  wh_ratio:', wh, '| ratio_follow:', rf)

# 节点 INPUT_TYPES 冒烟测试
for cls_name in P.NODE_CLASS_MAPPINGS:
    cls = P.NODE_CLASS_MAPPINGS[cls_name]
    try:
        it = cls.INPUT_TYPES()
        print()
        print('INPUT_TYPES OK:', cls_name)
        print('  required keys:', list(it['required'].keys()))
        print('  optional keys:', list(it.get('optional', {}).keys()))
        print('  return:', cls.RETURN_TYPES, '| function:', cls.FUNCTION)
    except Exception as e:
        print('INPUT_TYPES FAIL:', cls_name, e)

# ---- 合并节点专项验证 ----
from BSAI_Qwen_Prompt_Enhancer.nodes_enhancer import (
    BSAI_Qwen_Prompt_Enhancer, BACKEND_LABELS, BACKEND_PE, BACKEND_LLAMA, BACKEND_API,
    _api_request,
)

print()
print('合并节点验证:')
node = BSAI_Qwen_Prompt_Enhancer()
it = node.INPUT_TYPES()
assert list(it['required']['backend'][0]) == BACKEND_LABELS, 'backend 下拉与标签不一致'
assert node.RETURN_NAMES == (
    'ENHANCED_PROMPT', 'WH_RATIO', 'RATIO_FOLLOW', 'RAW_OUTPUT', 'THINKING',
    'RECOMMENDED_STEPS', 'RECOMMENDED_CFG', 'RECOMMENDED_SAMPLER', 'RECOMMENDED_SCHEDULER',
    'MERGED_TEXT'), '10 路输出名异常'
assert len(node.RETURN_TYPES) == 10, '输出类型数 != 10'
print('  backend 标签:', BACKEND_LABELS)
print('  输出 10 路 OK:', node.RETURN_NAMES)

# 1) _finalize 统一收尾（10 路 result）
out = node._finalize('{"rewritten_prompt": "cat", "wh_ratio": "1:1", "ratio_follow": true}',
                     '标准质量 20步/CFG3 (推荐, 7B原生)', '测试')
assert len(out['result']) == 10, 'finalize 结果数 != 10'
assert out['result'][0] == 'cat' and out['result'][1] == '1:1' and out['result'][5] == 20
assert isinstance(out['result'][9], str) and out['result'][9], 'MERGED_TEXT 应为非空字符串'
print('  _finalize OK: 10 路 result, steps=20 cfg=3.0')

# 2) enhance() 按 backend 分发：API 后端最小调用验证（mock 掉真实 HTTP）
calls = []
def fake_request(url, payload, headers, timeout):
    calls.append((url, payload, headers, timeout))
    return {'choices': [{'message': {'content': '{"rewritten_prompt": "api cat", "wh_ratio": "16:9"}'}}]}
_orig = _api_request
import BSAI_Qwen_Prompt_Enhancer.nodes_enhancer as NE
NE._api_request = fake_request
try:
    out = node.enhance(
        backend=BACKEND_API,
        prompt_text='一只猫', system_template='Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]',
        api_base='http://127.0.0.1:1/v1', api_key='sk-test', api_model_name='qwen3.5-vl-9b',
        temperature=0.7, top_p=0.95, top_k=40, seed=42, max_tokens=1024, timeout=30,
    )
finally:
    NE._api_request = _orig
assert len(calls) == 1, 'API 应只发一次请求'
url, payload, headers, timeout = calls[0]
assert url == 'http://127.0.0.1:1/v1/chat/completions'
assert payload['model'] == 'qwen3.5-vl-9b' and payload['top_k'] == 40 and payload['seed'] == 42
assert headers.get('Authorization') == 'Bearer sk-test'
assert out['result'][0] == 'api cat' and out['result'][1] == '16:9' and len(out['result']) == 10
print('  API 分发 OK: payload=%s' % {k: payload[k] for k in ('model', 'temperature', 'max_tokens', 'top_p', 'top_k', 'seed')})

# 3) API 400 降级：服务端不认 top_k/seed -> 自动用最小 payload 重试
calls2 = []
def flaky_request(url, payload, headers, timeout):
    calls2.append(payload)
    if len(calls2) == 1:
        import urllib.error
        raise urllib.error.HTTPError(url, 400, 'unknown parameter', headers, None)
    return {'choices': [{'message': {'content': '{"rewritten_prompt": "fallback ok"}'}}]}
NE._api_request = flaky_request
try:
    out = node.enhance(
        backend=BACKEND_API,
        prompt_text='一只猫', system_template='Qwen-Image-2.1 官方 PE-T2I 系统规则 [official_t2i]',
        api_base='http://127.0.0.1:1/v1', api_key='', api_model_name='m',
        temperature=0.7, top_p=0.95, top_k=40, seed=0, max_tokens=1024, timeout=30,
    )
finally:
    NE._api_request = _orig
assert len(calls2) == 2, '应降级重试一次'
assert 'top_k' not in calls2[1] and 'seed' not in calls2[1], '最小 payload 不应含 top_k/seed'
assert out['result'][0] == 'fallback ok'
print('  API 400 降级 OK: 第2次 payload=%s' % {k: calls2[1][k] for k in calls2[1]})

# 4) 未知 backend 报错
try:
    node.enhance(backend='不存在的后端', prompt_text='x', system_template='x', api_base='x')
    raise SystemExit('应该抛错而未抛')
except ValueError as e:
    print('  未知 backend 报错 OK:', str(e)[:60])

print()
print('ALL PASS')
