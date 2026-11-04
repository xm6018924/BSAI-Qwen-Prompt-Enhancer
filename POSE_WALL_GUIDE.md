# AI 姿势海报墙（Pose Wall）使用说明

> BSAI Qwen Prompt Enhancer 插件 v1.11.0 新增功能
> 把本地 AI 姿势素材库做成可筛选的「海报墙」，挑好的姿势自动排成 **@图1 / @图2 / @图3 …** 编号，
> 这个编号顺序 **就是** 送进 Qwen-Image 2.1 的 `image_1 … image_N` 输入顺序。

---

## 一、素材库结构

默认素材库根目录：

```
C:\BSAI\AI资料\素材库离线版带网页预览\AI姿势
```

文件命名规则：`{姿势组}_P{编号}_{机位}.png`

| 姿势组 | 说明 | 张数 |
|--------|------|------|
| `full_sexy` | 全身·性感 | 399 |
| `full_single` | 全身·单人 | 365 |
| `pair60` | 双人互动 | 275 |
| `upper80v2` | 上半身 v2 | 400 |

| 机位 | 说明 | 张数 |
|------|------|------|
| `front` | 正面 | 288 |
| `high` | 俯视 | 288 |
| `low` | 仰视 | 287 |
| `side` | 侧面 | 288 |
| `diag` | 斜侧 | 288 |

合计 **1439** 张，编号 `P001 ~ P080`。全部 900×1200（3:4）。

---

## 二、怎么打开

两种入口，任选其一：

1. **ComfyUI 节点按钮（推荐）**
   - `BSAI_Qwen_Pose_Wall` 节点 → 点 **「🖼 打开姿势海报墙」**
   - `BSAI_Qwen_Prompt_Enhancer`（增强）节点 → 点 **「🖼 打开姿势海报墙」**
   - 两种入口都会带上 `node_id`，海报墙可直接把清单写回节点

2. **浏览器直接开**
   ```
   http://127.0.0.1:8191/bsai_pose_wall
   ```
   （端口按实际 ComfyUI 端口改，默认启动器是 8191）

> 端口打不开 / 页面空白 → 跑插件目录下的 `fix_wall.bat`，它会自动探测端口 + 修代理例外。

---

## 三、参考图编号与输入顺序（重点）

这是整套功能的核心：**墙上怎么排，送进模型就是什么顺序。**

| 墙面上的操作 | 对应模型输入 |
|--------------|--------------|
| 清单第 1 项 | `image_1` |
| 清单第 2 项 | `image_2` |
| … | … |
| 清单第 N 项 | `image_N`（增强节点共 `image_1 ~ image_16`，最多 16 张） |

- 卡片左上角的蓝色角标 = 它的 **@图N** 编号
- 右侧清单可用 **↑ / ↓** 调整顺序 —— 改完立刻保存并同步到插件目录
- 清单顺序会同时写进插件目录的 `pose_selection.json`，关掉页面再打开不丢
- 浏览器本地也存一份（localStorage），换浏览器时以后者为准

### 四种复制/回填方式

| 按钮 | 产出 | 什么时候用 |
|------|------|-----------|
| 📋 复制编号清单 | `图1 = full_sexy_P001_front.png（全身·性感 · P001 · 正面）` | 给人看的清单 |
| 📋 复制文件名 | 每行一个文件名，顺序即 image_1..N | 自己往节点里接图 |
| 📋 复制英文提示词片段 | 带图序的英文描述 | 直接粘进 Qwen-Image 2.1 提示词 |
| 💾 写入 user_requirement | 上面那段英文片段写进增强节点的 `user_requirement` 输入框 | PE 增强通道 |
| 📤 上传并连线 image_1..N | 自动建 LoadImage 节点、上传到 input、连到增强节点对应输入口 | 一步到位接参考图 |

英文提示词片段长这样：

```
Reference images (use them in exactly this order):
Image 1 - full_sexy_P001_front.png (全身·性感, pose 001, 正面 view, 3D mannequin pose reference, white background)
Image 2 - full_sexy_P001_side.png (全身·性感, pose 001, 侧面 view, 3D mannequin pose reference, white background)
Follow the body pose and camera angle of each reference image exactly. Keep the same character,
outfit, hairstyle and lighting across all images. The reference images are pose and camera-angle
guides only; render them as the final artwork.
```

---

## 四、墙面的其它功能

- **姿势组 / 机位 / 编号区间 / 关键词** 四重筛选，实时过滤
- **卡片墙 ↔ 同组对照** 两种视图：
  - 卡片墙：一张一卡，适合按编号翻找
  - 同组对照：同一个姿势编号的 5 个机位并排一行，适合挑角度
- **🔍 放大**：卡片右上角放大镜或灯箱里双击 → 看原图（900×1200），支持 ← → 翻页、Esc 关闭
- **密度切换**：小 / 中 / 大三档
- **🔄 重新扫描**：素材库新增图后点一下，重新建清单并补缩略图
- 卡片上按 **@图N** 角标可一眼看出哪些已经选过

---

## 五、节点说明

### BSAI_Qwen_Pose_Wall | AI 姿势海报墙 (Pose Reference List)

**Category:** `BSAI/Qwen Image 2.1`

| 输入 | 类型 | 说明 |
|------|------|------|
| `library_root` | STRING | 素材库根目录。默认自动读取 |
| `apply_root` | BOOLEAN | 勾上并运行一次 = 把上面路径写成插件配置并重建清单（只勾一次即可） |

| 输出 | 类型 | 说明 |
|------|------|------|
| `REFERENCE_LIST` | STRING | 中文编号清单，第 1 项 = image_1 |
| `PROMPT_SNIPPET` | STRING | 英文提示词片段（带图序） |
| `SUMMARY` | STRING | 统计摘要（总张数 / 组数 / 机位数 / 已选数 / 路径） |

节点输出走 `pose_selection.json`，所以**海报墙 → 节点**这一段不需要手动同步，点一下「运行」即可。

---

## 六、换素材库位置

三种方式，优先级从高到低：

1. 环境变量 `BSAI_POSE_LIBRARY`
   ```bat
   set BSAI_POSE_LIBRARY=D:\素材库\AI姿势
   ```
2. 插件目录 `pose_library.json`
   ```json
   { "root": "D:\\素材库\\AI姿势" }
   ```
3. 节点上填 `library_root` + 勾 `apply_root` 运行一次

改完点海报墙上的「🔄 重新扫描」。

---

## 七、文件落位

| 文件 | 作用 |
|------|------|
| `web/pose_wall.html` | 海报墙页面 |
| `web/pose_manifest.json` | 素材清单（分组/机位/编号/尺寸/文件名） |
| `web/pose_thumbnails/*.jpg` | 300×400 缩略图（1439 张，约 21 MB） |
| `pose_selection.json` | 当前参考图清单（顺序 = 输入顺序） |
| `pose_library.json` | 素材库根目录配置 |
| `pose_library.py` | 后端：扫描 / 缩略图 / 清单 / 路由 |
| `nodes_pose.py` | 节点定义 |
| `gen_pose_thumbs.py` | 缩略图批量生成工具（可命令行单独跑） |

**原图不复制**：海报墙看原图时走后端 `/bsai_pose_image?id=…` 从素材库按需流式返回，
600MB+ 的原始 PNG 一个字节都没往插件目录搬。

---

## 八、常见问题

| 现象 | 原因 / 处理 |
|------|------------|
| 页面提示「姿势清单加载失败」 | ComfyUI 没起，或素材库路径失效。先看 ComfyUI 日志里有没有「姿势海报墙路由已注册」 |
| 图片全是空白方块 | 缩略图缺失 → 点「🔄 重新扫描」；或命令行跑 `python gen_pose_thumbs.py --force` |
| 打不开 127.0.0.1 | 跑 `fix_wall.bat`（自动探测端口 + 加代理例外） |
| 上传并连线没反应 | 增强节点上 `image_1..image_16` 需要是输入口（不能被改成别的类型）；浏览器控制台有详细报错 |
| 想清空清单 | 右侧面板底部「清空清单」 |
| 中文显示成乱码 | 插件的 .py/.html 都是 UTF-8；Windows 终端乱码不影响网页 |

---

## 九、常见使用路线

**A. 我要一张某个姿势的人物图**
1. 海报墙筛出想要的姿势（组 + 机位 + 编号）
2. 点卡片 → 清单里出现 @图1
3. 要第二个角度就再点一张 → @图2
4. 「📤 上传并连线 image_1..N」
5. 在增强节点的 `user_requirement` 里补其它要求 → 运行

**B. 我要对比一组机位挑一个**
1. 切「同组对照」视图
2. 同一个 P 编号的 5 个机位并排看
3. 点中意的那个 → 自动进清单

**C. 素材库加了新图**
1. 海报墙右上「🔄 重新扫描」
2. 新图立刻出现在墙上，编号规则不用改
