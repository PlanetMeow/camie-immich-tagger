# -*- coding: utf-8 -*-
"""
清理 tier0_progress.json 里 "hit_but_danbooru_err" 的记录(旧版 tier0_saucenao.py 遗留)。
这些图 SauceNAO 已命中(配额已花),但回查 Danbooru 失败没拿到标签,
旧逻辑把它们记成"已处理"导致永不重试。删掉这些 key 让它们重新排队
(会重新消耗 SauceNAO 配额;新版脚本已不会再产生这种记录)。

默认 DRY-RUN。加 --confirm 才改(自动备份 .bak)。
运行前确认 tier0_saucenao.py 没在跑,否则它会把删掉的记录写回去。
用法: python fix_tier0_progress.py [--confirm]
"""
import os, sys, json, shutil
from collections import Counter

from config import TIER0_PROGRESS as PROGRESS


def main():
    confirm = "--confirm" in sys.argv
    if not os.path.exists(PROGRESS):
        raise SystemExit(f"找不到 {PROGRESS}")
    prog = json.load(open(PROGRESS, encoding="utf-8"))

    kinds = Counter()
    for v in prog.values():
        if v.startswith("hit_but_danbooru_err"):
            kinds["hit_but_danbooru_err"] += 1
        elif v.startswith("hit"):
            kinds["hit"] += 1
        elif v == "miss":
            kinds["miss"] += 1
        else:
            kinds["err/other"] += 1

    bad = [k for k, v in prog.items() if v.startswith("hit_but_danbooru_err")]
    print("=" * 56)
    print(f"progress 总条数: {len(prog)}")
    for k, v in kinds.most_common():
        print(f"  {k}: {v}")
    print("-" * 56)
    print(f"待清理(命中但回查失败,应重试): {len(bad)} 条")
    for k in bad[:10]:
        print("  ", k)
    print("=" * 56)

    if not bad:
        print("没有需要清理的记录。")
        return
    if not confirm:
        print("[DRY-RUN] 未修改。确认无误后: python fix_tier0_progress.py --confirm")
        return

    shutil.copy(PROGRESS, PROGRESS + ".bak")
    for k in bad:
        del prog[k]
    json.dump(prog, open(PROGRESS, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"已删除 {len(bad)} 条,剩余 {len(prog)} 条(备份 -> {os.path.basename(PROGRESS)}.bak)")
    print("这些图会在下次 Tier 0 运行时重新尝试。")


if __name__ == "__main__":
    main()
