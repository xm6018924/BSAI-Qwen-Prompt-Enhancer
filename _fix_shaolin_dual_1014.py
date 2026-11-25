# -*- coding: utf-8 -*-
"""
少林招式模板双轨修复（v2，纠正 v1 的错误判断）。

【v1 的判断是错的】
v1 认为根因是「提示词里混入中文」，于是把 100 条动作说明译成英文。
中文确实会让 Qwen-Image 渲染文字，但那不是本例的主因——真正的原因是：

    用户工作流的后端是「官方PE」（专用微调模型），它的训练范式是
        system prompt = 提示词「改写指令」  →  模型输出改写后的画面描述
    官方PE 只认指令式 system prompt。

    少林模板是全库唯一的「成品直出型」模板（text 直接就是最终提示词）。
    把它当 system prompt 喂给官方PE，模型会把这段文字当成
    「需要处理的目标文本」而非「处理规则」，于是照着指令里的改写规则
    把这段描述当成要呈现的内容，输出一整页说明性文字
    （即用户截图里的多栏英文文字页，内容正是官方 PE 系统规则全文）。

    其他模板（design/character/style…）的 text 全是「你是资深XX，请把
    用户描述转写为…」这种指令体，天然匹配官方PE，所以都能正常出图。

【本次修复：双轨并行】
  A. 主库 templates/templates.json + web/templates.json
     100 条 shaolin 改为「指令式」system prompt，与其它分类完全统一，
     官方PE 本地后端可直接跑通。
  B. 新增 user_templates/shaolin_direct.json
     100 条「直出版」成品提示词，供 API / 本地 LLaMA 等能直接执行成品
     提示词的后端使用；同时保留英文动作描述 + no-text 反向约束。

两条轨道都保证：无中日韩字符、无失效的单花括号占位符。

缩略图：直出版复用主库 web/thumbnails/shaolin_XXX.png（已存在，100 张）。
"""
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "templates" / "templates.json"
WEB = ROOT / "web" / "templates.json"
USER_DIR = ROOT / "user_templates"
USER_FILE = USER_DIR / "shaolin_direct.json"
THUMBS = ROOT / "web" / "thumbnails"

# ------------------------------------------------------------------ 英文动作说明
EN_DETAIL = {
    "001": "Both knees bent into a deep horse stance, one fist chambered at the waist, the other fist punched straight forward, force concentrated on the striking knuckles.",
    "002": "Horse stance, one forearm raised above the head with the elbow bent as a guard, the other fist punched forward.",
    "003": "Horse stance, both arms chopping downward simultaneously from above, force landing on the heel of the fist.",
    "004": "Horse stance, a hooking punch driven upward from below, palm of the fist turned inward.",
    "005": "Horse stance, both arms bent and swung forward in an arc from the sides, the two fists striking together face to face.",
    "006": "Horse stance, both palms pushed forward level, palms facing forward, force driven through the heel of the palm.",
    "007": "Horse stance, both palms lifted in an arc upward to either side, palms angled up.",
    "008": "Horse stance, one palm raised overhead as a block, the other hand chambered at the waist.",
    "009": "Horse stance, one arm smashed downward from above, force driven through the back of the fist.",
    "010": "Horse stance, both palms split from the chest and pushed outward to either side.",
    "011": "Front knee bent in a half squat, rear leg extended straight in a bow stance, one fist punched forward.",
    "012": "Bow stance, the heel of the palm thrust forward with fingertips pointing up.",
    "013": "Bow stance, the arm chopping down from above, force landing on the heel of the fist.",
    "014": "Bow stance, one forearm raised overhead as a guard, the other fist punched forward.",
    "015": "Bow stance, both fists driven forward at the same time.",
    "016": "Bow stance, elbow bent and driven horizontally forward from behind, force concentrated at the elbow point.",
    "017": "Bow stance, a straight arm thrusting the palm forward, fingertips leading.",
    "018": "Bow stance, one hand hooking inward from outside while the other fist punches forward.",
    "019": "Bow stance, one arm smashed downward from above.",
    "020": "Front leg bent to support the weight, the other leg hooking forward with the toe pulled.",
    "021": "Bow stance, one arm pushing a vertical palm forward, the other arm extended diagonally down with an open palm.",
    "022": "Bow stance, both palms thrust forward in a pushing-a-window motion.",
    "023": "Bow stance, elbow bent and pressed downward.",
    "024": "Bow stance, the fist driving down from above, force concentrated on the striking knuckles.",
    "025": "Bow stance, both palms pressing outward to either side with arms spread.",
    "026": "One leg fully crouched, the other extended straight and flattened, the palm threading out along the inner side of the leg.",
    "027": "Crouch stance, one palm displayed beside the head, the other hand resting on the side of the leg.",
    "028": "Crouched leg supporting the weight, the other leg extended and lifted, the hand slapping the top of the foot.",
    "029": "Crouch stance, the arm circling a full rotation then slapping down toward the ground.",
    "030": "Crouch stance, the torso leaning forward and pressing down onto the extended front leg.",
    "031": "After threading the palm in crouch stance, the arm sweeping backslash upward from below.",
    "032": "Crouch stance, one arm chopping the fist down from above.",
    "033": "Crouch stance, one forearm raised as a guard, the other fist punched downward.",
    "034": "Rear leg bent in a half squat for support, front leg resting lightly on the toes, the fist driving down.",
    "035": "Empty stance, one forearm raised as a guard, the other fist punched forward.",
    "036": "Empty stance, the palm pushed gently forward.",
    "037": "Empty stance, one palm displayed beside the head, the other hand resting on the hip.",
    "038": "Empty stance, the hand formed into a hook and extended down and back.",
    "039": "After the downward plant punch in empty stance, the arm sweeping backslash upward.",
    "040": "Empty stance, the palm stabbed straight forward like a thrust through the heart.",
    "041": "Empty stance, the palm lifted upward from below.",
    "042": "Both legs crossed in a full squat, the hips resting on the heels.",
    "043": "Rest stance, one arm punching the fist forward.",
    "044": "Rest stance, one hand covering downward while the other fist punches forward.",
    "045": "Rest stance, the arm circling a full rotation then smashing the fist downward.",
    "046": "Rest stance, the fist lifted upward from below.",
    "047": "After the jump, the right leg kicks forward while the right hand slaps the top of the right foot.",
    "048": "After the jump, the body spins 180 degrees in the air, the inside crescent kick striking.",
    "049": "After the jump, the right leg sweeps outward, both hands slapping the top of the foot in turn.",
    "050": "After the jump, both feet kick forward and push away.",
    "051": "A long striding leap landing into a crouch stance with a threading palm.",
    "052": "Jumping off the left foot, kicking first with the right foot then the left, the right hand slapping the right foot.",
    "053": "After the jump, one foot stamping down forcefully in mid-air.",
    "054": "After the whirlwind kick, landing into a full front split.",
    "055": "After the jump, both feet kicking forward at the same time.",
    "056": "One foot supporting, the other knee lifted and stepping forward to stomp.",
    "057": "One leg raised horizontally behind, the torso leaning forward, both arms extended sideways like a swallow spreading its wings.",
    "058": "One leg standing straight in support, the other knee raised, the palm pushing forward.",
    "059": "One leg raised behind, the torso tilting sideways and the head turned back to gaze, like watching the moon.",
    "060": "One leg standing straight, the other foot hooked behind the knee of the supporting leg.",
    "061": "One knee bent and the leg crossed up onto the thigh of the supporting leg.",
    "062": "Based on the swallow balance, the torso bowing forward as if reaching into the sea.",
    "063": "During the knee-raise balance, one palm displayed beside the head.",
    "064": "Kneeling on one knee, both palms held together in front of the chest.",
    "065": "A straight arm punching forward, force concentrated on the striking knuckles.",
    "066": "The fist swung forward in an arc from the side to strike.",
    "067": "The fist hooking upward from below, like scooping something up.",
    "068": "The fist chopping down from above.",
    "069": "The fist driving down from above.",
    "070": "The fist smashed down hard from above.",
    "071": "The heel of the palm thrust forward.",
    "072": "The palm lifted upward from below.",
    "073": "The palm chopping down from above.",
    "074": "The palm pressing downward.",
    "075": "The palm threading straight forward in a straight line.",
    "076": "Fingertips stabbing straight forward.",
    "077": "The palm sweeping backslash upward from below to the front.",
    "078": "The palm swung forward in an arc from the side.",
    "079": "The palm slapping forward.",
    "080": "The five fingers pinched together into a hook with the wrist bent.",
    "081": "The hand formed into a hook with the wrist turned inward.",
    "082": "The arm wrapping in an arc, tracing a circle.",
    "083": "Both arms alternating circular cloud-hand motions in front of the body.",
    "084": "The palm opening like a fan and pushing forward.",
    "085": "Support leg straight, the other leg with the toe hooked, kicking forward to head height.",
    "086": "One leg supporting, the other leg with the toe hooked, kicking out to the side.",
    "087": "The leg swinging in an arc from outside to inside.",
    "088": "The leg swinging in an arc from inside to outside.",
    "089": "The thigh raised, the lower leg snapping forward quickly.",
    "090": "The knee bent and lifted, then the heel driving forward.",
    "091": "The knee bent and lifted, the sole stamping down.",
    "092": "The leg scooping out in an arc from inside to outside.",
    "093": "The toe hooked, kicking inward from outside to inside.",
    "094": "The leg sweeping backslash upward from below to the front.",
    "095": "One leg extended and lifted, the hand slapping the top of the foot.",
    "096": "The leg kicking diagonally upward.",
    "097": "The leg sweeping backslash upward and behind.",
    "098": "Crouch stance, pivoting on the supporting leg, the other leg sweeping forward in a full circle.",
    "099": "Crouch stance, pivoting on the supporting leg, the other leg sweeping backward in a full circle.",
    "100": "Both legs landing split front and back into a full front split.",
}

CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
STALE_PLACEHOLDER = re.compile(
    r"\{(?:MAIN_SUBJECT|COLOR_PALETTE|SCENE_DETAILS)\}|"
    r"\{\{(?:MAIN_SUBJECT|COLOR_PALETTE|SCENE_DETAILS)\}\}",
    re.IGNORECASE,
)


def strip_num(name_en):
    """'1. Horse Stance Punch' -> 'Horse Stance Punch'"""
    return re.sub(r"^\d+\.\s*", "", name_en or "").strip()


def move_label(name_en):
    """动作名：带序号，便于模型区分同族招式。"""
    return (name_en or "").strip()


# ------------------------------------------------ A. 指令式（主库，供官方PE）
def build_directive(num, name_en):
    """指令式 system prompt：与 design/character/pose 等分类同构。

    关键：明确告诉模型「你要输出画面描述，而不是复述这段文字」，
    并禁止在画面里出现任何文字，堵住文字页渲染。
    """
    move = strip_num(name_en)
    label = move_label(name_en)
    return (
        "你是资深武术动作摄影师与提示词撰写者。请把用户给出的画面描述，"
        f"转写为少林武术「{label}」这一招式的英文出图提示词。\n\n"
        f"本招式的标准动作要领（必须准确体现在描述里）：{EN_DETAIL[num]}\n\n"
        "画面锚点（必须逐条体现）：\n"
        "- 主体：一名少林武僧，灰色传统僧服，神情专注沉静\n"
        f"- 动作：精准还原上述「{move}」动作要领，四肢角度、站型与发力方向清晰可辨\n"
        "- 景别：全身景，从头到脚完整入画，四周留出边距，不裁切四肢\n"
        "- 姿态：武术姿势标准、重心稳定，手位与脚位分明，肢体解剖准确，肌肉张力自然\n"
        "- 背景：简洁空净的寺院练功场，浅景深虚化，无杂物\n"
        "- 影调：写实武术摄影质感，干净柔和的光线，主体锐利\n\n"
        "转换规则：保留原描述中的人物形象、服装、场景与情绪不变，"
        "仅把肢体语言准确改写为上述标准动作。\n"
        "严格禁止：描述或生成画面中的任何文字——不要标题、字幕、图注、编号、"
        "标签、水印、签名、海报排版；画面里只出现人物与场景，不要文字版面。\n"
        "输出：一段完整英文提示词（含 full body shot、correct martial arts posture、"
        "anatomically accurate、realistic martial arts photography 等关键词，且不含任何文字元素）。"
    )


# ------------------------------------------------ B. 直出版（用户区，供 API/LLM）
def build_direct(num, name_en):
    """成品直出提示词：供 API / 本地 LLaMA 等能直接执行成品提示词的后端。"""
    move = strip_num(name_en)
    return (
        f"A Shaolin monk in traditional grey robes performing the {move} martial arts pose, "
        f"a signature move of the Shaolin Hundred Form routine. {EN_DETAIL[num]} "
        "Full body shot, entire figure visible from head to toe with margin around it, "
        "correct martial arts posture, stable stance, clear hands and feet positioning, "
        "anatomically accurate limbs, natural muscle tension. "
        "Background: simple uncluttered neutral temple courtyard, softly blurred, no objects. "
        "Style: realistic martial arts photography, clean soft lighting, sharp focus on the figure. "
        "No text, no letters, no numbers, no captions, no watermark, no signature, no poster layout."
    )


def clean(text):
    """兜底清洗：去失效占位符、去 CJK、收拾标点空格。

    注意：指令式模板的中文是「指令正文」，必须保留，
    因此 clean 只对直出版使用（指令式不调用）。
    """
    text = STALE_PLACEHOLDER.sub("", text)
    text = CJK.sub("", text)
    text = re.sub(r"\(\s*\)|\[\s*\]|,\s*,", ",", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    return text.strip()


def main():
    problems = []

    # ---------- 读主库 ----------
    data = json.loads(BACKEND.read_text(encoding="utf-8"))
    shaolin = [t for t in data["templates"] if t.get("type") == "shaolin"]
    if len(shaolin) != 100:
        problems.append(f"主库 shaolin 条数异常: {len(shaolin)}")

    # ---------- A) 改写主库为指令式 ----------
    for t in shaolin:
        num = re.fullmatch(r"shaolin_(\d{3})", t.get("id", ""))
        if not num:
            problems.append(f"{t.get('id')}: id 格式异常")
            continue
        n = num.group(1)
        if n not in EN_DETAIL:
            problems.append(f"{t['id']}: 缺少英文动作说明")
            continue
        directive = build_directive(n, t.get("name_en") or t.get("name") or "")
        for key in ("text", "prompt"):
            if key in t:
                t[key] = directive
        # 描述字段补充「指令式 / 直出版」使用说明，便于用户在海报墙分辨
        if t.get("desc"):
            t["desc"] = t["desc"] + "（指令式：官方PE 可直接用；成品直出见「用户模板区」）"
    BACKEND.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[A] 主库 templates/templates.json：{len(shaolin)} 条改为指令式")

    # ---------- 同步 web 版 ----------
    web = json.loads(WEB.read_text(encoding="utf-8"))
    web_shaolin = [t for t in web["templates"] if t.get("type") == "shaolin"]
    by_id = {t["id"]: t for t in shaolin}
    for t in web_shaolin:
        src = by_id.get(t.get("id"))
        if src:
            for key in ("prompt", "text"):
                if key in t:
                    t[key] = src.get(key, src.get("text", ""))
            if t.get("description"):
                t["description"] = src.get("desc", t["description"])
    WEB.write_text(json.dumps(web, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[B] web/templates.json：{len(web_shaolin)} 条同步")

    # ---------- C) 生成用户区直出版 ----------
    direct_list = []
    thumb_ok = 0
    for t in shaolin:
        num = re.fullmatch(r"shaolin_(\d{3})", t["id"])
        if not num:
            continue
        n = num.group(1)
        if n not in EN_DETAIL:
            continue
        thumb = t.get("thumbnail") or f"{t['id']}.png"
        if (THUMBS / thumb).exists():
            thumb_ok += 1
        direct_list.append({
            "id": f"shaolin_direct_{n}",
            "name": f"少林直出 · {t['name']}",
            "desc": f"成品直出提示词（API/本地LLM后端用）：{t.get('desc', '').split('（指令式')[0]}",
            "type": "user",
            "category": "少林直出",
            "tags": ["少林", "武术", "招式", "直出", "kungfu"],
            "thumbnail": thumb,
            "text": clean(build_direct(n, t.get("name_en") or t.get("name") or "")),
        })

    USER_DIR.mkdir(exist_ok=True)
    USER_FILE.write_text(
        json.dumps({"templates": direct_list}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[C] user_templates/shaolin_direct.json：{len(direct_list)} 条直出版（缩略图复用 {thumb_ok} 张）")

    # ---------- 复核 ----------
    print("\n===== 复核 =====")
    # 主库：指令式，应含中文（指令正文），但不得含失效占位符
    d = json.loads(BACKEND.read_text(encoding="utf-8"))
    sl = [t for t in d["templates"] if t.get("type") == "shaolin"]
    bad_ph = [t["id"] for t in sl if STALE_PLACEHOLDER.search(t.get("text", ""))]
    not_instr = [
        t["id"] for t in sl
        if not t.get("text", "").startswith("你是资深武术动作摄影师")
    ]
    print(f"主库 指令式: {len(sl)} 条 | 失效占位符 {len(bad_ph)} | 非指令式 {len(not_instr)}")
    if bad_ph:
        problems.append(f"主库残留占位符: {bad_ph[:5]}")
    if not_instr:
        problems.append(f"主库非指令式条目: {not_instr[:5]}")

    # web 版一致性
    w = json.loads(WEB.read_text(encoding="utf-8"))
    wsl = [t for t in w["templates"] if t.get("type") == "shaolin"]
    mismatch = []
    wmap = {t["id"]: t for t in wsl}
    for t in sl:
        ww = wmap.get(t["id"])
        if ww and ww.get("prompt") != t.get("text"):
            mismatch.append(t["id"])
    print(f"web  版 shaolin: {len(wsl)} 条 | 与主库不一致 {len(mismatch)}")
    if mismatch:
        problems.append(f"web 版不一致: {mismatch[:5]}")

    # 用户直出版：必须零中文
    u = json.loads(USER_FILE.read_text(encoding="utf-8"))
    ul = u["templates"]
    bad_cjk = [t["id"] for t in ul if CJK.search(t.get("text", ""))]
    bad_ph_u = [t["id"] for t in ul if STALE_PLACEHOLDER.search(t.get("text", ""))]
    print(f"直出版: {len(ul)} 条 | 含中文 {len(bad_cjk)} | 失效占位符 {len(bad_ph_u)}")
    if bad_cjk:
        problems.append(f"直出版含中文: {bad_cjk[:5]}")
    if bad_ph_u:
        problems.append(f"直出版残留占位符: {bad_ph_u[:5]}")

    print("\n===== 样例 =====")
    print("[指令式 shaolin_001]")
    print(next(t for t in sl if t["id"] == "shaolin_001")["text"][:420])
    print("\n[直出版 shaolin_direct_001]")
    print(ul[0]["text"][:420])

    print("\n结果:", "全部通过" if not problems else "存在问题")
    for p in problems:
        print("  -", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())