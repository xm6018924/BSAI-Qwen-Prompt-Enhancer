# -*- coding: utf-8 -*-
"""
BSAI 姿势海报墙 —— 缩略图生成工具

把素材库原图（900x1200 PNG）批量缩成海报墙用的 300x400 JPEG，
落到 web/pose_thumbnails/，浏览器滚动才不卡。

用法：
    python gen_pose_thumbs.py                 # 扫描默认素材库，增量补齐缩略图
    python gen_pose_thumbs.py --force         # 全部重做
    python gen_pose_thumbs.py --root "D:\\xxx\\AI姿势"   # 指定素材库
    python gen_pose_thumbs.py --size 400      # 指定缩略图宽度（高度按 3:4）

放在插件根目录，可随时双击/命令行运行；ComfyUI 端也会在缺图时惰性补单张。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from . import pose_library as pl
except ImportError:
    import pose_library as pl


def _make_one(task):
    """生成一张缩略图（多进程用，必须是顶层函数）。"""
    root, eid, fname = task
    src = os.path.join(root, fname)
    dest = os.path.join(pl.THUMB_DIR, "%s.jpg" % eid)
    if not os.path.isfile(src):
        return (eid, False)
    try:
        from PIL import Image
        os.makedirs(pl.THUMB_DIR, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            scale = pl.THUMB_WIDTH / float(im.width)
            nh = max(1, int(round(im.height * scale)))
            im = im.resize((pl.THUMB_WIDTH, nh), Image.LANCZOS)
            if nh < pl.THUMB_HEIGHT:
                canvas = Image.new("RGB", (pl.THUMB_WIDTH, pl.THUMB_HEIGHT), "#ffffff")
                canvas.paste(im, (0, (pl.THUMB_HEIGHT - nh) // 2))
                im = canvas
            elif nh > pl.THUMB_HEIGHT:
                canvas = Image.new("RGB", (pl.THUMB_WIDTH, pl.THUMB_HEIGHT), "#ffffff")
                canvas.paste(im.crop((0, 0, pl.THUMB_WIDTH, pl.THUMB_HEIGHT)), (0, 0))
                im = canvas
            im.save(dest, "JPEG", quality=pl.THUMB_QUALITY, optimize=True)
        return (eid, True)
    except Exception as e:
        print("[gen_pose_thumbs] %s 失败: %s" % (eid, e))
        return (eid, False)


def main():
    force = "--force" in sys.argv
    root = pl.get_library_root()
    if "--root" in sys.argv:
        i = sys.argv.index("--root")
        if i + 1 < len(sys.argv):
            root = sys.argv[i + 1]
    if "--size" in sys.argv:
        i = sys.argv.index("--size")
        if i + 1 < len(sys.argv):
            try:
                w = int(sys.argv[i + 1])
                pl.THUMB_WIDTH = w
                pl.THUMB_HEIGHT = int(round(w * 4 / 3))
            except Exception:
                pass

    print("[gen_pose_thumbs] 素材库: %s" % root)
    if not os.path.isdir(root):
        print("[gen_pose_thumbs] 素材库不存在，退出。")
        return 1

    t0 = time.time()
    manifest = pl.build_manifest(root, force=True)
    entries = manifest.get("entries", [])
    print("[gen_pose_thumbs] 扫描到 %d 张图，清单: %s" % (len(entries), pl.MANIFEST_PATH))

    tasks = []
    for e in entries:
        dest = os.path.join(pl.THUMB_DIR, "%s.jpg" % e["id"])
        if force or not (os.path.exists(dest) and os.path.getsize(dest) > 512):
            tasks.append((root, e["id"], e["file"]))
    if not tasks:
        print("[gen_pose_thumbs] 缩略图已齐全，无需处理。")
        return 0

    print("[gen_pose_thumbs] 待生成 %d 张（已存在 %d 张跳过）" % (
        len(tasks), len(entries) - len(tasks)))

    os.makedirs(pl.THUMB_DIR, exist_ok=True)
    ok = 0
    fail = 0
    workers = min(8, max(1, (os.cpu_count() or 4) - 1))
    try:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for i, (eid, good) in enumerate(ex.map(_make_one, tasks, chunksize=16), 1):
                if good:
                    ok += 1
                else:
                    fail += 1
                if i % 200 == 0:
                    print("[gen_pose_thumbs] 进度 %d/%d" % (i, len(tasks)))
    except Exception as e:
        print("[gen_pose_thumbs] 多进程不可用(%s)，改用单进程。" % e)
        for t in tasks:
            _, good = _make_one(t)
            if good:
                ok += 1
            else:
                fail += 1

    total = 0
    try:
        for fn in os.listdir(pl.THUMB_DIR):
            total += os.path.getsize(os.path.join(pl.THUMB_DIR, fn))
    except Exception:
        pass
    print("[gen_pose_thumbs] 完成：成功 %d / 失败 %d，用时 %.1fs" % (ok, fail, time.time() - t0))
    print("[gen_pose_thumbs] 缩略图目录: %s（合计 %.1f MB）" % (pl.THUMB_DIR, total / 1024.0 / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
