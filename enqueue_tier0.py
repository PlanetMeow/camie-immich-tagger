# -*- coding: utf-8 -*-
"""
把新图里「有具体作品(非 original)但 camie 没认出角色」的,追加进 Tier 0 队列
(no_character_images.txt)。只入队,不跑 SauceNAO —— 由 tier0_saucenao.py 后台慢慢消费。
去重:已在队列的、Tier 0 已处理过的(tier0_progress.json)都不重复加。

由 update.bat 在 camie_pipeline 之后调用。也可单独跑:python enqueue_tier0.py
"""
import os
import json
import tempfile
import subprocess

from config import EXIFTOOL, SCAN_DIRS, NO_CHAR_LIST as CANDIDATES, TIER0_PROGRESS as PROGRESS
WORKDIR = os.path.dirname(EXIFTOOL)


def read_all_sidecars(d):
    fd, argfile = tempfile.mkstemp(suffix=".txt", dir=WORKDIR)
    os.close(fd)
    try:
        with open(argfile, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(["-j", "-XMP-digiKam:TagsList", "-r", "-ext", "xmp", d]) + "\n")
        r = subprocess.run(
            [EXIFTOOL, "-charset", "utf8", "-charset", "filename=UTF8", "-@", argfile],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
        return json.loads(r.stdout) if r.stdout.strip() else []
    except Exception:
        return []
    finally:
        try:
            os.unlink(argfile)
        except Exception:
            pass


def seg(tags, prefix):
    if isinstance(tags, str):
        tags = [tags]
    return [t for t in (tags or []) if t.startswith(prefix)]


def main():
    existing = set()
    if os.path.exists(CANDIDATES):
        existing = set(l.strip() for l in open(CANDIDATES, encoding="utf-8") if l.strip())
    done = set()
    if os.path.exists(PROGRESS):
        try:
            done = set(json.load(open(PROGRESS, encoding="utf-8")).keys())
        except Exception:
            pass

    new_enq = []
    for d in SCAN_DIRS:
        if not os.path.isdir(d):
            continue
        for rec in read_all_sidecars(d):
            src = rec.get("SourceFile", "")
            img = src[:-4] if src.endswith(".xmp") else src
            tags = rec.get("TagsList", [])
            has_char = bool(seg(tags, "character/"))
            copies = seg(tags, "copyright/")
            real_copy = any(c != "copyright/original" for c in copies)
            if (not has_char) and real_copy:
                if img not in existing and img not in done:
                    new_enq.append(img)
                    existing.add(img)  # 防同次重复

    if new_enq:
        with open(CANDIDATES, "a", encoding="utf-8") as f:
            for img in new_enq:
                f.write(img + "\n")
    print(f"[enqueue] 新入队 Tier 0 候选: {len(new_enq)} 张  (队列总计 {len(existing)})")


if __name__ == "__main__":
    main()
