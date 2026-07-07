# -*- coding: utf-8 -*-
"""
清理孤儿 sidecar:扫描外部库目录,删除「对应图片已不存在」的 .xmp 文件。
(本地手动删图后,旁边的 .xmp 会变成孤儿)

判定:
  Form A  foo.png.xmp  -> 若 foo.png 不存在,则孤儿
  Form B  foo.xmp      -> 若 foo.<任何图片扩展名> 都不存在,则孤儿

默认 DRY-RUN(只列出、不删)。核对无误后加 --confirm 才真删。
用法:
  python orphan_sidecar_cleanup.py            # dry-run
  python orphan_sidecar_cleanup.py --confirm  # 真删
"""
import os
import sys
import glob

from config import SCAN_DIRS, ORPHAN_LIST
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def find_orphans():
    orphans = []
    total = 0
    for d in SCAN_DIRS:
        if not os.path.isdir(d):
            print(f"[警告] 目录不存在: {d}")
            continue
        for xmp in glob.glob(os.path.join(d, "**", "*.xmp"), recursive=True):
            total += 1
            base = xmp[:-4]                      # 去掉 ".xmp"
            stem, ext = os.path.splitext(base)
            if ext.lower() in IMG_EXTS:          # Form A: foo.png.xmp
                is_orphan = not os.path.exists(base)
            else:                                 # Form B: foo.xmp
                is_orphan = not any(os.path.exists(stem + e) for e in IMG_EXTS)
            if is_orphan:
                orphans.append(xmp)
    return total, orphans


def main():
    confirm = "--confirm" in sys.argv
    total, orphans = find_orphans()
    print(f"扫描到 {total} 个 .xmp  |  孤儿(对应图已不存在) {len(orphans)}  |  正常 {total-len(orphans)}")

    with open(ORPHAN_LIST, "w", encoding="utf-8") as f:
        for o in orphans:
            f.write(o + "\n")
    print(f"孤儿完整清单 -> {ORPHAN_LIST}")

    print("\n孤儿示例(前 30):")
    for o in orphans[:30]:
        print("  -", o)

    if not orphans:
        print("\n没有孤儿 sidecar,无需清理。")
        return

    if not confirm:
        print(f"\n[DRY-RUN] 未删除任何东西。核对 {ORPHAN_LIST} 无误后:")
        print("  python orphan_sidecar_cleanup.py --confirm")
        return

    print(f"\n[CONFIRM] 删除 {len(orphans)} 个孤儿 sidecar...")
    ok = err = 0
    for o in orphans:
        try:
            os.remove(o)
            ok += 1
        except Exception as e:
            err += 1
            print(f"  删除失败 {o}: {e}")
    print(f"\n完成:删除 {ok},失败 {err}")


if __name__ == "__main__":
    main()
