# -*- coding: utf-8 -*-
"""
少林招式模板修复 v3 —— 按官方 PE 输出契约重写指令式模板。

【v1 误判】根因当成「提示词含中文 → 渲染文字」，把 100 条动作说明译成英文。
【v2 误判】根因当成「模板体裁与后端不匹配」，把成品直出改成中文指令式。
   截图2 推翻了 v2：正常出图的 formula_official 本身就是中文指令式，
   与 v2 改出来的结构几乎一致，说明体裁说也不成立。

【v3 真根因】官方PE 是专用微调模型，训练目标恒为输出 JSON：
    {"rewritten_prompt": "<画面描述>", "wh_ratio": "<W:H>"}
该契约只写在官方系统规则文件末尾（qwen_image_2.1_pe_t2i_system_prompt.txt
第 188-192 行 / i2i 文件的 Output format 段）。

插件 common.py:251 的解析是「失败即兜底」：
    enhanced = data.get("rewritten_prompt", answer if answer else raw_text)
  · JSON 解析成功 → 取 rewritten_prompt，干净画面描述进图模型 → 正常出图
  · JSON 解析失败 → 把模型整个原始输出当提示词 → 解释性文字进图模型 → 文字页

v2 的模板塞了大量「严格禁止描述或生成画面中的任何文字／不要标题字幕编号标签」
这类元指令，把官方PE 推出训练分布，它开始「解释自己该怎么写」，JSON 崩掉，
于是原始输出被整体兜底进模型 —— 即用户截图 1 里那页极淡的小字。

【v3 修法】严格照官方规范改，三处关键：
  1. 指令末尾原样带上 JSON 输出契约（rewritten_prompt / wh_ratio），
     让模型始终落在训练分布内；
  2. 按官方 I2I 规则明文要求（"State requirements affirmatively rather than as
     prohibitions"），把所有「禁止/不要…」改写为正面画面描述；
  3. 去掉编号前缀与关键词清单式要求，降低格式漂移风险。

直出版（user_templates/shaolin_direct.json）同样去掉 negative 式的
"No text..." 尾巴，改为正面陈述画面内容。
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "templates" / "templates.json"
WEB = ROOT / "web" / "templates.json"
USER_FILE = ROOT / "user_templates" / "shaolin_direct.json"
THUMBS = ROOT / "web" / "thumbnails"

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
STALE = re.compile(
    r"\{(?:MAIN_SUBJECT|COLOR_PALETTE|SCENE_DETAILS)\}|"
    r"\{\{(?:MAIN_SUBJECT|COLOR_PALETTE|SCENE_DETAILS)\}\}", re.I)
# 官方 I2I 规则明确要求：正面表述，而非禁止式
NEGATIVE_CN = ["严格禁止", "不要标题", "禁止", "不得出现", "杜绝", "不要文字", "不含任何文字"]
NEGATIVE_EN = ["No text", "no text,", "no letters", "no watermark", "no signature",
               "no captions", "no numbers", "no poster layout"]


def strip_num(s):
    return re.sub(r"^\d+\.\s*", "", s or "").strip()


def build_directive(num, name_en):
    """指令式：照官方契约结尾 + 全正面表述，贴近官方PE 训练分布。"""
    move = strip_num(name_en)
    return (
        "You are a professional martial arts photography prompt engineer. "
        f"Rewrite the user's plain request into a single high-quality English image prompt "
        f"depicting the Shaolin form \"{move}\" executed correctly.\n\n"
        "Movement to depict precisely:\n"
        f"{EN_DETAIL[num]}\n\n"
        "Scene to build:\n"
        "- A Shaolin monk in traditional grey robes, focused and composed.\n"
        f"- The posture matches the {move} movement above: limb angles, stance shape and "
        "direction of force are clearly readable.\n"
        "- Full body framing, the entire figure from head to toe inside the frame with "
        "generous margin around it.\n"
        "- Correct martial arts posture, stable centre of gravity, hands and feet clearly "
        "placed, anatomically accurate limbs, natural muscle tension.\n"
        "- Background: a simple uncluttered temple training courtyard, softly blurred, "
        "free of objects.\n"
        "- Look: realistic martial arts photography, clean soft light, the figure in "
        "sharp focus.\n"
        "- The frame contains the monk and the courtyard; the image reads as a clean "
        "photograph with the figure as the only subject.\n\n"
        "Keep the user's subject, clothing, setting and mood; only the body language is "
        "rewritten to the movement above.\n\n"
        "Output format:\n"
        "Return one strictly valid JSON object on a single line, nothing before or after:\n"
        '{"rewritten_prompt": "<the description>", "wh_ratio": "<e.g. 2:3"}'
    )


def build_direct(num, name_en):
    """成品直出：全正面陈述，不含 negative 尾巴。"""
    move = strip_num(name_en)
    return (
        f"A Shaolin monk in traditional grey robes performing the {move} martial arts pose, "
        f"a signature move of the Shaolin Hundred Form routine. {EN_DETAIL[num]} "
        "Full body shot, the entire figure from head to toe inside the frame with generous "
        "margin around it, correct martial arts posture, stable centre of gravity, hands and "
        "feet clearly placed, anatomically accurate limbs, natural muscle tension. "
        "Background: a simple uncluttered temple training courtyard, softly blurred, free of "
        "objects. Style: realistic martial arts photography, clean soft lighting, the figure in "
        "sharp focus, the monk and the courtyard are the only content in a clean photographic "
        "frame."
    )


def clean_direct(t):
    """直出版兜底清洗（去掉失效占位符与任何 CJK 残留）。"""
    t = STALE.sub("", t)
    t = CJK.sub("", t)
    t = re.sub(r"\(\s*\)|\[\s*\]|,\s*,", ",", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*\.", ".", t)
    return t.strip()


def main():
    problems = []
    data = json.loads(BACKEND.read_text(encoding="utf-8"))
    shaolin = [t for t in data["templates"] if t.get("type") == "shaolin"]
    if len(shaolin) != 100:
        problems.append(f"shaolin 条数异常 {len(shaolin)}")

    # ---- 主库改指令式 ----
    for t in shaolin:
        m = re.fullmatch(r"shaolin_(\d{3})", t.get("id", ""))
        if not m or m.group(1) not in EN_DETAIL:
            problems.append(f"{t.get('id')} 跳过")
            continue
        body = build_directive(m.group(1), t.get("name_en") or t.get("name") or "")
        for k in ("text", "prompt"):
            if k in t:
                t[k] = body
        if t.get("desc"):
            t["desc"] = re.sub(r"（指令式.*?）", "", t["desc"]).strip()
    BACKEND.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[A] 主库 {len(shaolin)} 条 → 指令式（含 JSON 契约，全正面表述）")

    # ---- web 同步 ----
    web = json.loads(WEB.read_text(encoding="utf-8"))
    byid = {t["id"]: t for t in shaolin}
    n = 0
    for t in web["templates"]:
        if t.get("type") == "shaolin" and t["id"] in byid:
            for k in ("prompt", "text"):
                if k in t:
                    t[k] = byid[t["id"]].get(k, "")
            n += 1
    WEB.write_text(json.dumps(web, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[B] web 版同步 {n} 条")

    # ---- 直出版更新 ----
    if USER_FILE.exists():
        u = json.loads(USER_FILE.read_text(encoding="utf-8"))
        for t in u["templates"]:
            m = re.fullmatch(r"shaolin_direct_(\d{3})", t.get("id", ""))
            if m and m.group(1) in EN_DETAIL:
                t["text"] = clean_direct(build_direct(m.group(1), t.get("name", "")))
        USER_FILE.write_text(
            json.dumps(u, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[C] 直出版更新 {len(u['templates'])} 条（去 negative 尾巴）")

    # ---------------- 校验 ----------------
    print("\n===== 校验 =====")
    d = json.loads(BACKEND.read_text(encoding="utf-8"))
    sl = [t for t in d["templates"] if t.get("type") == "shaolin"]
    no_contract = [t["id"] for t in sl if '"rewritten_prompt"' not in t.get("text", "")]
    neg_cn = [t["id"] for t in sl if any(w in t.get("text", "") for w in NEGATIVE_CN)]
    stale = [t["id"] for t in sl if STALE.search(t.get("text", ""))]
    print(f"指令式 {len(sl)} | 缺 JSON 契约 {len(no_contract)} | 含禁止式中文 {len(neg_cn)} | 残留占位符 {len(stale)}")
    for label, arr in (("缺契约", no_contract), ("禁止式", neg_cn), ("占位符", stale)):
        if arr:
            problems.append(f"{label}: {arr[:5]}")

    w = json.loads(WEB.read_text(encoding="utf-8"))
    wmap = {t["id"]: t for t in w["templates"] if t.get("type") == "shaolin"}
    mism = [t["id"] for t in sl if wmap.get(t["id"], {}).get("prompt") != t.get("text")]
    print(f"web 一致性不一致 {len(mism)}")
    if mism:
        problems.append(f"web 不一致 {mism[:5]}")

    if USER_FILE.exists():
        u = json.loads(USER_FILE.read_text(encoding="utf-8"))
        ul = u["templates"]
        cjk = [t["id"] for t in ul if CJK.search(t.get("text", ""))]
        neg = [t["id"] for t in ul if any(w in t.get("text", "") for w in NEGATIVE_EN)]
        print(f"直出版 {len(ul)} | 含中文 {len(cjk)} | 含 negative 尾巴 {len(neg)}")
        if cjk:
            problems.append(f"直出版含中文 {cjk[:5]}")
        if neg:
            problems.append(f"直出版含 negative {neg[:5]}")

    print("\n===== 样例 shaolin_001 =====")
    print(next(t for t in sl if t["id"] == "shaolin_001")["text"])

    print("\n结果:", "全部通过" if not problems else "存在问题")
    for p in problems:
        print("  -", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())