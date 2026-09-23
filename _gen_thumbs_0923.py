# -*- coding: utf-8 -*-
"""生成 Qwen 28 + H3 4 个新模板缩略图：下载 -> 448x448 -> 叠加百声AI圆形logo
Qwen:  web/thumbnails/<id>.png
H3:    web/previews/<id>.webp
"""
import io, os, urllib.request
from PIL import Image

LOGO = r"C:\BSAI\AI资料\input\061\百声AI-logo-圆形.png"

# (url_suffix -> id)
QWEN = {
    "https://aka.doubaocdn.com/s/eH9KvxV7SO": "pose_standing_natural",
    "https://aka.doubaocdn.com/s/X8B5JAqGOD": "pose_standing_arms",
    "https://aka.doubaocdn.com/s/0QbKfYl3aD": "pose_power_hero",
    "https://aka.doubaocdn.com/s/Dnmw8EJU2b": "pose_sitting_chair",
    "https://aka.doubaocdn.com/s/fRvcPygVzN": "pose_sitting_floor",
    "https://aka.doubaocdn.com/s/dLDH9XUcBX": "pose_sitting_crossed",
    "https://aka.doubaocdn.com/s/k95ar19bdA": "pose_kneel_squat",
    "https://aka.doubaocdn.com/s/f8UOlFuvEm": "pose_lying_recline",
    "https://aka.doubaocdn.com/s/KUpmTTqiqp": "pose_walk_run",
    "https://aka.doubaocdn.com/s/XaaAVATsKL": "pose_jump_leap",
    "https://aka.doubaocdn.com/s/BdcnptMbjo": "pose_combat_fight",
    "https://aka.doubaocdn.com/s/jTeLuvCKv4": "pose_hand_gesture",
    "https://aka.doubaocdn.com/s/Cq9pXZILUp": "pose_emotion_perform",
    "https://aka.doubaocdn.com/s/bIUC9F7cyR": "pose_dance_sport",
    "https://aka.doubaocdn.com/s/iTQVBOK68w": "pose_motion_capture",
    "https://aka.doubaocdn.com/s/3RE82go7y9": "pose_two_person",
    "https://aka.doubaocdn.com/s/Ejee2OlNzV": "inspiration_myth_poster",
    "https://aka.doubaocdn.com/s/hJiPdqH1Vw": "inspiration_travel_poster",
    "https://aka.doubaocdn.com/s/1ocSVhLdAi": "inspiration_morning_photo",
    "https://aka.doubaocdn.com/s/vutO3mukt4": "inspiration_landmark_poster",
    "https://aka.doubaocdn.com/s/IqwVC4PkUn": "inspiration_jp_illust",
    "https://aka.doubaocdn.com/s/wlVxl47yU3": "inspiration_study_photo",
    "https://aka.doubaocdn.com/s/2eafD5AVN3": "inspiration_brand_ad",
    "https://aka.doubaocdn.com/s/a8SwlIubx9": "inspiration_anime_city",
    "https://aka.doubaocdn.com/s/bKjseSzU86": "inspiration_ghibli",
    "https://aka.doubaocdn.com/s/GOUAACkxUu": "inspiration_ink",
    "https://aka.doubaocdn.com/s/Tq1Y9oHa4G": "inspiration_minimal",
    "https://aka.doubaocdn.com/s/zhlxmM8gWY": "inspiration_watercolor",
}
H3 = {
    "https://aka.doubaocdn.com/s/8jt89aTzMd": "gufeng_costume_change",
    "https://aka.doubaocdn.com/s/Un0zLWPFOr": "xiyu_princess_drama",
    "https://aka.doubaocdn.com/s/dDZFPctktE": "gufeng_swordswoman",
    "https://aka.doubaocdn.com/s/mcoUXTG61J": "bride_costume_vlog",
}

QWEN_DIR = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer\web\thumbnails"
H3_DIR = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI-MiniMAX-H3-Prompt\web\previews"

def load_logo():
    im = Image.open(LOGO).convert("RGBA")
    return im

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def compose(src_bytes, logo, size=448, logo_w=112, margin=10):
    base = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    base = base.resize((size, size), Image.LANCZOS)
    lw = logo_w
    lh = int(logo.height * lw / logo.width)
    l = logo.resize((lw, lh), Image.LANCZOS)
    base.paste(l, (size - lw - margin, size - lh - margin), l)
    return base

def main():
    logo = load_logo()
    ok, fail = 0, []
    for url, tid in QWEN.items():
        try:
            img = compose(fetch(url), logo)
            img.save(os.path.join(QWEN_DIR, tid + ".png"))
            ok += 1
            print("Qwen OK", tid)
        except Exception as e:
            fail.append((tid, str(e)))
            print("Qwen FAIL", tid, e)
    for url, tid in H3.items():
        try:
            img = compose(fetch(url), logo)
            img.save(os.path.join(H3_DIR, tid + ".webp"), "WEBP", quality=88)
            ok += 1
            print("H3 OK", tid)
        except Exception as e:
            fail.append((tid, str(e)))
            print("H3 FAIL", tid, e)
    print("done ok=%d fail=%d" % (ok, len(fail)))
    for t, e in fail:
        print("  FAILED:", t, e)

if __name__ == "__main__":
    main()
