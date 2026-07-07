# -*- coding: utf-8 -*-
"""
角色覆盖率统计(快速版):一条 exiftool 命令递归读整个目录,
而非逐张起进程(后者 12000 张要几十分钟)。
读 sidecar,不依赖 immich。
用法: python char_stats.py
"""
import os
import sys
import json
import tempfile
import subprocess

from config import EXIFTOOL, SCAN_DIRS, NO_CHAR_LIST
WORKDIR = os.path.dirname(EXIFTOOL)


def read_all_sidecars(d):
    """一条命令递归读整个目录的所有 .xmp,返回 [{SourceFile, TagsList}, ...]"""
    print(f"  读取 {d} ...", flush=True)
    # 路径走 argfile,避免中文路径命令行编码问题
    fd, argfile = tempfile.mkstemp(suffix=".txt", dir=WORKDIR)
    os.close(fd)
    try:
        with open(argfile, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(["-j", "-XMP-digiKam:TagsList", "-r", "-ext", "xmp", d]) + "\n")
        r = subprocess.run(
            [EXIFTOOL, "-charset", "utf8", "-charset", "filename=UTF8", "-@", argfile],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
        )
        try:
            return json.loads(r.stdout) if r.stdout.strip() else []
        except Exception as e:
            print(f"  [警告] 解析失败: {e}")
            return []
    finally:
        try:
            os.unlink(argfile)
        except Exception:
            pass


def seg(tags, prefix):
    if isinstance(tags, str):
        tags = [tags]
    return [t.split("/", 1)[1] for t in (tags or []) if t.startswith(prefix)]


def main():
    records = []
    for d in SCAN_DIRS:
        if not os.path.isdir(d):
            print(f"[警告] 目录不存在: {d}")
            continue
        records.extend(read_all_sidecars(d))

    total = len(records)
    if total == 0:
        print("没扫到 sidecar。")
        return

    with_char = no_char_total = no_char_has_copyright = no_char_bare = no_char_real_copyright = 0
    char_counter, copy_counter, artist_counter = {}, {}, {}
    no_char_samples = []

    for rec in records:
        tags = rec.get("TagsList", [])
        chars = seg(tags, "character/")
        copies = seg(tags, "copyright/")
        artists = seg(tags, "artist/")
        for c in chars:
            char_counter[c] = char_counter.get(c, 0) + 1
        for c in copies:
            copy_counter[c] = copy_counter.get(c, 0) + 1
        for a in artists:
            artist_counter[a] = artist_counter.get(a, 0) + 1
        if chars:
            with_char += 1
        else:
            no_char_total += 1
            if copies:
                no_char_has_copyright += 1
                if any(c != "original" for c in copies):
                    no_char_real_copyright += 1   # 有具体作品(非纯 original)
            else:
                no_char_bare += 1
            if copies and any(c != "original" for c in copies):
                src = rec.get("SourceFile", "")
                no_char_samples.append(src[:-4] if src.endswith(".xmp") else src)

    pct = lambda n: f"{n/total*100:.1f}%"
    print("=" * 56)
    print(f"总 sidecar(已打标图): {total}")
    print(f"  认出角色:   {with_char}  ({pct(with_char)})")
    print(f"  无角色:     {no_char_total}  ({pct(no_char_total)})   <- Tier0 候选范围")
    print("-" * 56)
    print("无角色细分:")
    print(f"  有作品(copyright)无角色: {no_char_has_copyright}")
    print(f"    其中有具体作品(非纯original): {no_char_real_copyright}  <- Tier0 真正有效范围")
    print(f"  纯描述无任何实体:        {no_char_bare}  (反向搜也难命中)")
    print("=" * 56)
    print(f"不同角色总数: {len(char_counter)}")
    print(f"不同作品总数: {len(copy_counter)}")
    print(f"不同画师总数: {len(artist_counter)}")

    def top(counter, n, label):
        print(f"\nTop {n} {label}:")
        for k, v in sorted(counter.items(), key=lambda x: -x[1])[:n]:
            print(f"  {v:5d}  {k}")

    top(char_counter, 20, "角色")
    top(copy_counter, 15, "作品")
    top(artist_counter, 15, "画师")

    with open(NO_CHAR_LIST, "w", encoding="utf-8") as f:
        for p in no_char_samples:
            f.write(p + "\n")
    print(f"\n有具体作品但无角色 清单(Tier0 候选)-> {NO_CHAR_LIST}  共 {len(no_char_samples)} 张")


if __name__ == "__main__":
    main()
