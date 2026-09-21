# -*- coding: utf-8 -*-
"""
BSAI Qwen Prompt Enhancer — 模板缩略图批量生成器

为 templates.json 里每个模板生成一张示例海报缩略图，存到 web/thumbnails/<id>.png。
依赖：ComfyUI 跑在 http://127.0.0.1:8180，模型文件已就位。

用法：
    python gen_thumbnails.py            # 生成所有缺失的缩略图
    python gen_thumbnails.py --force    # 强制重新生成全部
"""
import os, sys, json, time, urllib.request, urllib.parse, shutil, io
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
THUMBS = WEB / "thumbnails"
THUMBS.mkdir(exist_ok=True)

COMFY = "http://127.0.0.1:8181"

# 每个模板的示例图像 prompt（直接描述画面，不是 system prompt）
# 格式: id -> (width, height, prompt)
EXAMPLES = {
    # ===== official / community 类：通用高质量示例（竖版 2:3）=====
    "official_t2i":            (400, 600, "Vertical 2:3, serene mountain lake at sunrise, mist rising, pine trees on rocky shore, golden light, photorealistic, highly detailed"),
    "official_i2i":             (400, 600, "Vertical 2:3, young woman portrait, soft studio lighting, natural skin texture, gentle smile, shallow depth of field, photorealistic"),
    "api_prompt_extend":       (400, 600, "Vertical 2:3, sitting orange cat with soft fluffy fur, warm sunlight through window, wooden floorboards, curled tail, cozy peaceful atmosphere"),
    "formula_official":        (400, 600, "Vertical 2:3, cute 10-year-old Chinese girl in red dress, animal kingdom city street, watercolor style, golden hour, highly detailed"),
    "layout_poster":           (400, 600, "Vertical 2:3 presentation slide, dark blue gradient background, large white title \"QWEN-IMAGE 2.0\", three bullet points, geometric wave graphic, high contrast"),
    "community_six":           (400, 600, "Vertical 2:3, young woman with long flowing hair on city street at night, neon lights, cyberpunk illustration, purple and cyan palette"),
    "lightning_zh":            (400, 600, "Vertical 2:3, 橘猫蹲在青瓷碗旁的木窗台上，午后阳光，碗里冒热气，窗外老巷，暖色调，细腻纹理，浅景深"),
    "style_mix":               (400, 600, "Vertical 2:3, magical castle in forest, steampunk meets fantasy, Studio Ghibli style, warm lighting, whimsical"),
    "detail_control":          (400, 600, "Vertical 2:3, portrait close-up, focus on eyes, blurred natural background, soft morning light, warm tone, photorealistic skin texture"),

    # ===== design 类（竖版 2:3）=====
    "design_short_video_cover": (400, 600, "Vertical 2:3 short video cover. Top: huge bold glowing orange title \"AI ART REVOLUTION\". Subtitle: \"How AI Creates Art\". Bottom: young woman in neon cyberpunk city. Top-right logo \"BSAI\". High contrast, vibrant."),
    "design_magazine_cover":   (400, 600, "Vertical 2:3 magazine cover. Top: huge white masthead \"VOGUE\" on black. Main: fashion model in black dress. Right side cover lines: \"FALL FASHION\", \"BEAUTY\". High fashion photography."),
    "design_book_cover":       (400, 600, "Vertical 2:3 book cover. Top: large white title \"THE SILENT OCEAN\". Middle: underwater bioluminescent jellyfish, deep blue. Bottom: \"BSAI PRESS\". Elegant, atmospheric."),
    "design_desktop_wallpaper": (400, 600, "Vertical 2:3, lone tree on misty mountain peak at dawn, soft pastel pink and blue gradient sky, low saturation, calm atmosphere, no text"),
    "design_poster":           (400, 600, "Vertical 2:3 event poster. Top: large bold title \"MUSIC FESTIVAL 2026\". Middle: crowd with hands raised at sunset. Bottom: \"June 20-22 Shanghai\". Bright, energetic."),
    "design_magazine_inner":   (400, 600, "Vertical 2:3 magazine spread. Left: article title \"THE FUTURE OF AI\", columns of text. Right: futuristic cityscape photo. Clean editorial design."),
    "design_brochure_cover":   (400, 600, "Vertical 2:3 brochure cover. Top-left logo \"BSAI\". Large title \"INNOVATION SOLUTIONS\". Right: modern office building. Bottom: slogan \"Building Tomorrow\". Professional blue."),
    "design_brochure_inner":   (400, 600, "Vertical 2:3 brochure inner. Top title \"OUR SERVICES\". Left: service descriptions. Right: team collaborating. Bottom: 3 icons \"DESIGN BUILD SUPPORT\". Clean grid."),
    "design_outdoor_billboard": (400, 600, "Vertical 2:3 billboard. Center: huge bold text \"NEW COLLECTION\". Subtitle: \"Summer 2026\". Right: fashion model. Bottom-right: \"BSAI\" and \"bsai.ai\". High contrast."),

    # ===== cinema 类（竖版 2:3）=====
    "cinema_film_still":       (400, 600, "Vertical 2:3 cinematic film still. Lone figure in long coat walking through rain-soaked neon Tokyo alley at night, shallow DOF, film grain, Blade Runner color grade"),
    "cinema_film_storyboard":  (400, 600, "Vertical 2:3 film storyboard sheet. Top title: \"SCENE 1\". 6 panels in 3x2 grid: wide, medium, close-up, over-shoulder, extreme close-up, wide city. Each labeled. Clean lines."),
    "cinema_grid_4":           (400, 600, "Vertical 2:3, 2x2 grid of 4 cinematic frames with black borders: wide mountain, medium character, close-up face, close-up hands. Same character, consistent lighting"),
    "cinema_grid_6":           (400, 600, "Vertical 2:3, 3x2 grid of 6 cinematic frames: wide, medium, close-up, reaction, over-shoulder, detail. Same character in forest, golden hour"),
    "cinema_grid_9":           (400, 600, "Vertical 2:3, 3x3 grid of 9 cinematic frames: establishing, wide, medium, medium close-up, close-up, over-shoulder, two-shot, reaction, final wide. City scene"),
    "cinema_grid_12":          (400, 600, "Vertical 2:3, 4x3 grid of 12 cinematic frames, complete narrative sequence. Same character and setting, consistent lighting"),
    "cinema_character_3view":  (400, 600, "Vertical 2:3 character turnaround: three full-body views of young female with short black hair, brown leather jacket. Front, side, back. Pure white background, orthographic"),
    "cinema_character_4view":   (400, 600, "Vertical 2:3 character turnaround: four views of male warrior in armor. Front, three-quarter, side, back. Pure white, orthographic, concept art"),
    "cinema_character_6view":   (400, 600, "Vertical 2:3 character six-view. Top: 3 full-body views (front, side, back). Bottom: 3 head close-ups. Female mage with robes. Pure white"),
    "cinema_prop_3view":       (400, 600, "Vertical 2:3 prop turnaround: three views of medieval wooden treasure chest with metal bands. Front, side, top. Pure white, PBR materials"),
    "cinema_prop_4view":       (400, 600, "Vertical 2:3 prop turnaround: four views of sci-fi ray gun. Front, three-quarter, side, back. Pure white, detailed"),
    "cinema_prop_6view":       (400, 600, "Vertical 2:3 prop six-view. Top: 3 views of ancient lantern. Bottom: 3 detail close-ups. Pure white, PBR"),
    "cinema_scene_asset":      (400, 600, "Vertical 2:3 scene concept art: abandoned futuristic laboratory at dusk, large windows showing sunset, broken equipment, vines through cracks, atmospheric"),

    # ===== character 类（竖版 2:3）=====
    "character_full_sheet":    (400, 600, "Vertical 2:3 character reference sheet, pure white. Center: full-body front view of young female mage. Left: head close-up + bust. Right: side + back. Bottom: 6 expression squares + costume details + color palette. Professional design sheet, anime style"),
    "character_turnaround":    (400, 600, "Vertical 2:3 character turnaround, pure white. Four equal full-body views: front, three-quarter, side, back. Same character, same T-pose. Anime model sheet"),
    "character_expression_sheet": (400, 600, "Vertical 2:3 expression sheet, 3x2 grid on white. Same character bust, 6 expressions: neutral, happy, angry, sad, surprised, thinking. Labeled below. Anime style"),
    "character_outfit_breakdown": (400, 600, "Vertical 2:3 outfit breakdown, white background. Left: small full-body character. Right: 8 detail close-up boxes: collar, cuffs, belt, boots, hairpin, sword, fabric. Labeled"),
    "character_color_palette": (400, 600, "Vertical 2:3 character color palette, light gray. Left: character bust. Right: 6 color swatches with HEX labels: moon white, indigo, cinnabar, gold, skin, hair. Professional"),
    "character_consistency_anchor": (400, 600, "Vertical 2:3 text card on dark gradient. Title: \"CHARACTER ANCHOR\". Below: 5 lines of white monospace text describing character features. Minimal, clean design"),
    "character_fullbody_illustration": (400, 600, "Vertical 2:3 full-body illustration of young female warrior in armor, standing gracefully, soft rim lighting, gradient background, anime style, masterpiece"),
    "character_bust_portrait": (400, 600, "Vertical 2:3 bust portrait of young woman, 85mm lens, shallow DOF, focus on eyes, soft side lighting, blurred background, photorealistic"),
    "character_game_splash":   (400, 600, "Vertical 2:3 game splash art, female mage casting spell, dynamic pose, magical energy effects, dramatic lighting, dark fantasy, masterpiece, best quality"),
    "character_anime_mobile_ui": (400, 600, "Vertical 2:3 gacha character card. Center: anime girl in battle pose. Left UI panel with gold border: name \"LUNA\", 5 stars, element \"Fire\", 3 skill icons. Dark fantasy background"),
    "character_pose_sheet":    (400, 600, "Vertical 2:3 pose sheet, 2x3 grid on white. Same character in 6 poses: standing, walking, running, attacking, sitting, waving. Anime style, consistent"),
    "character_chinese_ancient": (400, 600, "Vertical 2:3 ancient Chinese character. Female xianxia in hanfu, high ponytail with jade hairpin, holding sword, ink wash background with plum blossoms, elegant, guohua style"),

    # ===== poster 类（竖版 2:3）=====
    "poster_one_sheet":        (400, 600, "Vertical 2:3 Hollywood one-sheet movie poster. Top half: dramatic portrait of a man in trench coat under rain. Bottom: large bold title \"THE LAST FRONTIER\". Tagline: \"This summer, the boundary breaks.\" Bottom credits: \"Directed by John Doe · Starring Jane Smith · JULY 2026\". Cinematic, epic"),
    "poster_ensemble":         (400, 600, "Vertical 2:3 ensemble cast poster. 5 main characters in dramatic diagonal formation, explosions in background. Top: title \"THE LAST STAND\". Epic blockbuster style, orange and gold tones"),
    "poster_minimalist":       (400, 600, "Vertical 2:3 minimalist movie poster. Solid deep red background. Single black silhouette of a lone figure with umbrella in center. Top: bold white title \"THE UMBRELLA\". Bottom: tagline \"Some storms are invisible.\" Saul Bass style"),
    "poster_split_screen":     (400, 600, "Vertical 2:3 split-screen movie poster. Left half: warm golden cozy living room. Right half: cold blue rainy dystopian city. Center: title \"TWO LIVES\" bridging the divide. Dramatic contrast"),
    "poster_environment":      (400, 600, "Vertical 2:3 environment-focused poster. Vast abandoned city skyline at sunset, tiny lone figure walking in foreground. Top: title \"THE LAST HUMAN\". Post-apocalyptic, atmospheric"),
    "poster_oscar_drama":      (400, 600, "Vertical 2:3 Oscar drama poster. Close-up of woman's face with tearful eyes, warm amber tones, Rembrandt lighting. Top: elegant serif title \"THE SILENT YEARS\". Minimal, emotional, awards contender style"),
    "poster_vintage_noir":     (400, 600, "Vertical 2:3 film noir poster. High contrast black and white. Detective in fedora and trench coat under streetlight, long shadow on wet pavement. Top: hand-painted title \"MIDNIGHT ALIBI\". 1940s style"),
    "poster_blockbuster":      (400, 600, "Vertical 2:3 summer blockbuster poster. Hero in tactical suit holding glowing weapon, explosion and helicopters behind. Top: metallic gold title \"IRON FURY\". Bottom: \"SUMMER 2026\". Orange and teal"),
    "poster_horror":           (400, 600, "Vertical 2:3 horror movie poster. Dark corridor, single flashlight beam illuminating a child's drawing on wall. Blurry tall figure in shadows. Top: dripping red title \"THE NURSERY\". Creepy, psychological"),
    "poster_romance":          (400, 600, "Vertical 2:3 romance movie poster. Silhouette of couple on beach at sunset, warm golden light, lens flare. Center: elegant script title \"SHORELINE\". Bottom: \"This summer, love finds its way.\" Soft, dreamy"),
    "poster_scifi":            (400, 600, "Vertical 2:3 sci-fi movie poster. Astronaut standing on alien planet surface, two moons in purple sky, futuristic ship behind. Top: geometric title \"ECHOES OF ANDROMEDA\". Cool blue and teal tones"),
    "poster_anime":            (400, 600, "Vertical 2:3 anime film poster. Young girl with magical staff standing in flower field under starry sky, Studio Ghibli style illustration. Top: calligraphy title \"THE STAR GARDEN\". Vibrant, hand-drawn, whimsical"),
}


def api_post(path, data):
    req = urllib.request.Request(
        COMFY + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def api_get(path):
    with urllib.request.urlopen(COMFY + path, timeout=30) as r:
        return json.loads(r.read())


def build_workflow(prompt_text, seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "BSAI-Qwen-Image-2.1-bf16.safetensors",
            "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "BSAI-Qwen-Image-2.1-TE.safetensors",
            "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {
            "vae_name": "BSAI-Qwen-Image-2.1-VAE.safetensors"}},
        "5": {"class_type": "TextEncodeQwenImage21", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0],
            "prompt": prompt_text,
            "negative_prompt": "low quality, blurry, distorted, deformed, text errors",
            "resolution": 448}},
        "10": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["5", 0], "negative": ["5", 1],
            "latent_image": ["5", 2],
            "seed": seed, "steps": 20, "cfg": 4,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "11": {"class_type": "VAEDecode", "inputs": {
            "samples": ["10", 0], "vae": ["3", 0]}},
        "12": {"class_type": "SaveImage", "inputs": {
            "images": ["11", 0], "filename_prefix": "BSAI_thumb"}},
    }


def wait_and_download(prompt_id, out_path, timeout=600):
    """轮询 history 直到完成，下载第一张图到 out_path"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        hist = api_get(f"/history/{prompt_id}")
        if prompt_id in hist:
            entry = hist[prompt_id]
            if entry.get("status", {}).get("completed"):
                # 找输出图
                for node_id, out in entry.get("outputs", {}).items():
                    for img in out.get("images", []):
                        fname = img["filename"]
                        subfolder = img.get("subfolder", "")
                        url = f"/view?filename={urllib.parse.quote(fname)}&subfolder={urllib.parse.quote(subfolder)}&type=output"
                        with urllib.request.urlopen(COMFY + url, timeout=60) as r:
                            out_path.write_bytes(r.read())
                        return True
            if entry.get("status", {}).get("status_str") == "error":
                print(f"  [ERROR] {entry.get('status')}", flush=True)
                return False
        time.sleep(3)
    print("  [TIMEOUT]", flush=True)
    return False


def main():
    force = "--force" in sys.argv

    # 读 templates.json 拿 id 列表
    with open(ROOT / "templates" / "templates.json", encoding="utf-8") as f:
        tpls = json.load(f)["templates"]

    # 连通性
    try:
        api_get("/system_stats")
    except Exception as e:
        print(f"无法连接 ComfyUI ({COMFY}): {e}")
        print("请先启动 ComfyUI (默认端口 8180)")
        return 1

    n_ok = n_skip = n_fail = 0
    for i, t in enumerate(tpls):
        tid = t["id"]
        out = THUMBS / f"{tid}.png"
        if out.exists() and not force:
            print(f"[{i+1:2d}/{len(tpls)}] SKIP  {tid} (已存在)")
            n_skip += 1
            continue
        if tid not in EXAMPLES:
            print(f"[{i+1:2d}/{len(tpls)}] MISS  {tid} (无示例 prompt)")
            n_fail += 1
            continue

        w, h, prompt = EXAMPLES[tid]
        print(f"[{i+1:2d}/{len(tpls)}] GEN   {tid}  ({w}x{h})", flush=True)
        wf = build_workflow(prompt, seed=hash(tid) & 0xFFFFFFFF)
        try:
            resp = api_post("/prompt", {"prompt": wf})
            pid = resp["prompt_id"]
            if wait_and_download(pid, out):
                print(f"       -> OK {out.name} ({out.stat().st_size//1024} KB)")
                n_ok += 1
            else:
                n_fail += 1
        except Exception as e:
            print(f"       -> FAIL {e}")
            n_fail += 1

    print(f"\n完成: {n_ok} 生成, {n_skip} 跳过, {n_fail} 失败")
    print(f"缩略图目录: {THUMBS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
