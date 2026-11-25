# -*- coding: utf-8 -*-
"""
修复 少林招式 100 条模板出图变文字的问题。

根因：
  少林模板是全库唯一「成品直出型」模板——text 直接就是喂给 Qwen-Image 的
  最终提示词（其余类型是喂给 LLM 的 system prompt）。而这 100 条的 text 里
  混入了大量中文招式名与中文动作说明。Qwen-Image 2.1 是中文文字渲染能力
  极强的模型，提示词里出现中文即被判定为「画面里要写字」，于是渲染成一整页
  文字（截图里的多栏文字页）。

次因：
  结尾残留 {MAIN_SUBJECT}, {COLOR_PALETTE}, {SCENE_DETAILS} 单花括号占位符。
  apply_variables 只替换双花括号 {{KEY}}，这些单花括号永远不会被替换，
  会以字面量「{MAIN_SUBJECT}」进入提示词，同样强化「写字」倾向。

修复：
  1. 中文动作说明逐条译为英文，英文招式名已存在，直接复用；
  2. 删除失效的单花括号占位符；
  3. 追加显式反向约束 no text / no letters / no watermark，压住文字倾向；
  4. 保持 name / name_en / description / thumbnail 不变，海报墙显示不受影响。

同步写入 templates/templates.json（后端 source of truth）与
web/templates.json（海报墙静态回退数据），保证两条加载路径一致。
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "templates" / "templates.json"
WEB = ROOT / "web" / "templates.json"

# ---------------------------------------------------------------- 英文动作说明
# 键为 001..100，逐条对应原模板第 2 行的中文动作说明。
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
# 失效的单花括号占位符（apply_variables 只认 {{KEY}} 双花括号）
STALE_PLACEHOLDER = re.compile(
    r"\{(?:MAIN_SUBJECT|COLOR_PALETTE|SCENE_DETAILS)\}|"
    r"\{\{(?:MAIN_SUBJECT|COLOR_PALETTE|SCENE_DETAILS)\}\}",
    re.IGNORECASE,
)


def build_text(num, name_en):
    """生成纯英文、无失效占位符、带反向约束的直出提示词。"""
    detail = EN_DETAIL[num]
    # name_en 形如 "1. Horse Stance Punch"，剥掉序号前缀
    move = re.sub(r"^\d+\.\s*", "", name_en).strip()
    return (
        f"A Shaolin monk in traditional grey robes performing the {move} "
        f"martial arts pose, a signature move of the Shaolin Hundred Form routine. "
        f"{detail} "
        "Full body shot, entire figure visible from head to toe with margin around it, "
        "correct martial arts posture, stable stance, clear hands and feet positioning, "
        "anatomically accurate limbs, natural muscle tension. "
        "Background: simple uncluttered neutral temple courtyard, softly blurred, no objects. "
        "Style: realistic martial arts photography, clean soft lighting, sharp focus on the figure. "
        "No text, no letters, no numbers, no captions, no watermark, no signature, no poster layout."
    )


def clean(text):
    """兜底：确保输出里没有任何 CJK 字符，也没有失效占位符。"""
    text = STALE_PLACEHOLDER.sub("", text)
    text = CJK.sub("", text)
    # 清理替换后残留的空括号 / 连续空格 / 悬空逗号
    text = re.sub(r"\(\s*\)|\[\s*\]|,\s*,", ",", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    return text.strip()


def rewrite(path, field):
    """重写指定 JSON 文件里的 shaolin 模板。返回 (总数, 改动数, 问题列表)。"""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    items = data["templates"]
    shaolin = [t for t in items if t.get("type") == "shaolin"]
    problems = []
    changed = 0

    for t in shaolin:
        m = re.fullmatch(r"shaolin_(\d{3})", t.get("id", ""))
        if not m:
            problems.append(f"{t.get('id')}: id 格式异常，跳过")
            continue
        num = m.group(1)
        if num not in EN_DETAIL:
            problems.append(f"{t['id']}: 缺少英文动作说明，跳过")
            continue

        name_en = t.get("name_en") or t.get("name") or ""
        new_text = clean(build_text(num, name_en))

        # 后端文件同时维护 prompt / text 两个字段，保持同源一致
        for key in (field, "text", "prompt"):
            if key in t:
                t[key] = new_text

        # 同步 prompt 字段存在性：web 版用 prompt，templates 版两者都有
        changed += 1
        if CJK.search(new_text):
            problems.append(f"{t['id']}: 输出仍含中文，请检查")

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(shaolin), changed, problems


def main():
    ok = True
    for path, field in ((BACKEND, "text"), (WEB, "prompt")):
        if not path.exists():
            print(f"[SKIP] 文件不存在: {path}")
            continue
        total, changed, problems = rewrite(path, field)
        status = "OK" if not problems else "WARN"
        print(f"[{status}] {path.relative_to(ROOT)}")
        print(f"       shaolin 模板 {total} 条，重写 {changed} 条")
        for p in problems:
            print(f"       - {p}")
        if problems:
            ok = False

    # 复核：重新读回，确认 0 条残留中文、0 条失效占位符
    print("\n===== 复核 =====")
    for path in (BACKEND, WEB):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["templates"]
        sl = [t for t in items if t.get("type") == "shaolin"]
        bad_cjk = [t["id"] for t in sl if CJK.search(t.get("text") or t.get("prompt") or "")]
        bad_ph = [
            t["id"]
            for t in sl
            if STALE_PLACEHOLDER.search(t.get("text") or t.get("prompt") or "")
        ]
        print(
            f"{path.relative_to(ROOT)}: 总模板 {len(items)} 条，"
            f"shaolin {len(sl)} 条，含中文 {len(bad_cjk)} 条，残留占位符 {len(bad_ph)} 条"
        )
        if bad_cjk:
            print(f"       含中文: {bad_cjk[:10]}")
            ok = False
        if bad_ph:
            print(f"       残留占位符: {bad_ph[:10]}")
            ok = False

    # 打印首条样例供人工确认
    print("\n===== 样例 shaolin_001 =====")
    data = json.loads(BACKEND.read_text(encoding="utf-8"))
    s = next(t for t in data["templates"] if t.get("id") == "shaolin_001")
    print(f"name: {s['name']}  ({s.get('name_en')})")
    print(f"desc: {s.get('desc') or s.get('description')}")
    print("prompt:")
    print(s.get("text") or s.get("prompt"))

    print("\n===== 样例 shaolin_100 =====")
    s = next(t for t in data["templates"] if t.get("id") == "shaolin_100")
    print(f"name: {s['name']}  ({s.get('name_en')})")
    print("prompt:")
    print(s.get("text") or s.get("prompt"))

    print("\n结果:", "全部通过" if ok else "存在问题，请查看上方 WARN")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())