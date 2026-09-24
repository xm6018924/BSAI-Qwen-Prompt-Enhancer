# 用户模板区（User Templates）

把你自己写的千问提示词模板放进本目录（可建子目录），插件会自动汇聚成「共享用户模板」，
出现在：
- 模板节点 `QwenImage21_Prompt_Template` 的下拉列表（分类 `user`）
- 海报墙（templates_wall.html）的「用户模板」分类
- 动态模板 API `GET /api/bsai/templates`

**添加/修改后：完全重启 ComfyUI 生效**（或刷新海报墙页面）。

## 模板文件格式（三选一）

1. 单个模板对象：
```json
{
  "id": "my_template",
  "name": "用户模板 · 我的风格",
  "desc": "一句话说明",
  "text": "你是资深风格转换师。请把用户的画面描述转写为……"
}
```
2. 模板对象 + 外部文本文件（text 放在插件内任意 txt/md，用 file 引用相对插件根的路径）：
```json
{
  "id": "my_template",
  "name": "用户模板 · 我的风格",
  "desc": "一句话说明",
  "file": "user_templates/my_style.txt"
}
```
3. 模板列表（一个文件放多个模板）：
```json
{
  "templates": [
    {"id": "a", "name": "模板A", "text": "……"},
    {"id": "b", "name": "模板B", "text": "……"}
  ]
}
```

## 规则

- `id` 与内置模板冲突时自动加 `user_` 前缀，无需手动改
- 模板内可用 `{{KEY}}` 占位符，配合节点 `variables` 输入（每行 `KEY: value`）自动替换
- 解析失败的文件会被跳过并打印提示，不影响其它模板
- 缩略图：可选，放到 `web/thumbnails/<id>.png`（448×448），海报墙会自动显示

## 示例

见同目录 `示例模板.json`（含 2 个示例模板，可直接复制修改）。
