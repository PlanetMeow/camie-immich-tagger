# -*- coding: utf-8 -*-
"""
用 PixAI tagger v0.9 给图补角色(camie 角色识别不准 / 不认识 2024 下半年后的新角色)。

作者库上的实测(2026-10-06):
  - camie 漏认的 74 张已知答案图:PixAI@0.85 认对 12 / 认错 7(camie 0)
  - camie 已有角色的 300 张:PixAI@0.75 给出的 158 张里 146 张一致
  - 肉眼抽查:>=0.95 基本都对,0.8~0.85 开始出错 -> 门槛取 0.9

- 只补不删:门槛以上的角色写 character/<角色>,并按 selected_tags.csv 的 ips 列写 copyright/<作品>
- 识别结果缓存进 pixai_cache.json(图 -> [[角色, 概率], ...] 只存 >=0.5);
  再跑只处理缓存里没有的图,所以每日增量是秒级
- 加了什么记进 pixai_added.json,--undo 只删 PixAI 加的标签
- 默认 DRY-RUN;--confirm 才写 sidecar,写完触发 immich 边车 check

用法:
    python pixai_characters.py                 # 推理新图(写缓存)+ dry-run 统计
    python pixai_characters.py --confirm       # 写入 sidecar + 触发 immich
    python pixai_characters.py --new-only --confirm   # 每日增量(daily.bat 用):只处理新图
    python pixai_characters.py --undo [--confirm]
    python pixai_characters.py --threshold 0.95
"""
import os
import sys
import json
import time
import collections

from backfill_concepts import read_taglists, _argfile_run, WRITE_BATCH, DONE_LIST

from pixai_tagger import MODEL_DIR as PIXAI_DIR
from config import WORK_DIR as WORK
CACHE = os.path.join(WORK, "pixai_cache.json")
ADDED = os.path.join(WORK, "pixai_added.json")
THRESHOLD = 0.9
CACHE_MIN = 0.5
SAVE_EVERY = 500


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def list_images():
    seen, out = set(), []
    for p in (l.strip() for l in open(DONE_LIST, encoding="utf-8")):
        if p and norm(p) not in seen and os.path.exists(p + ".xmp"):
            seen.add(norm(p))
            out.append(p)
    return out


def infer_new(imgs, cache):
    """推理缓存里没有的图,返回这次新推理的图列表"""
    todo = [p for p in imgs if norm(p) not in cache]
    print(f"图 {len(imgs)} 张,缓存已有 {len(imgs) - len(todo)},需要推理 {len(todo)}")
    if not todo:
        return []
    from pixai_tagger import PixaiTagger
    t = PixaiTagger()
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        try:
            ch = t.predict(p, CACHE_MIN)["character"]
            cache[norm(p)] = [[c, round(q, 4)] for c, q in ch]
        except Exception as e:
            cache[norm(p)] = []
            print(f"  推理失败 {os.path.basename(p)}: {str(e)[:80]}")
        if i % SAVE_EVERY == 0 or i == len(todo):
            save(CACHE, cache)
            el = time.time() - t0
            print(f"  推理 {i}/{len(todo)}  {i / el:.1f} 张/s  剩余约 {(len(todo) - i) / (i / el) / 60:.0f} 分钟", flush=True)
    return todo


def tags_for(chars, threshold, ips):
    out = []
    for c, q in chars:
        if q < threshold:
            continue
        out.append("character/" + c.replace("/", "_"))
        out += ["copyright/" + ip.replace("/", "_") for ip in ips.get(c, [])]
    from zh_names import name_tags
    out += name_tags(out)
    return list(dict.fromkeys(out))


def write(todo, undo):
    items = list(todo.items())
    updated = 0
    for i in range(0, len(items), WRITE_BATCH):
        batch = items[i:i + WRITE_BATCH]
        lines = []
        for s, tags in batch:
            lines.append("-overwrite_original")
            for tg in tags:
                lines.append(f"-XMP-digiKam:TagsList-={tg}")
                if not undo:
                    lines.append(f"-XMP-digiKam:TagsList+={tg}")
            lines += [s, "-execute"]
        out, err = _argfile_run(lines)
        updated += (out + err).count("1 image files updated")
        print(f"  写入 {min(i + WRITE_BATCH, len(items))}/{len(items)}  已更新 {updated}", flush=True)
    return updated


def main():
    args = sys.argv[1:]
    confirm, undo = "--confirm" in args, "--undo" in args
    thr = float(args[args.index("--threshold") + 1]) if "--threshold" in args else THRESHOLD
    added = load(ADDED)

    if undo:
        todo = {s: tags for s, tags in added.items() if tags}
        n = sum(len(v) for v in todo.values())
        print(f"撤销: {len(todo)} 个 sidecar,共删除 {n} 个 PixAI 加的标签  {'[写入]' if confirm else '[DRY-RUN]'}")
        if confirm and todo:
            write(todo, undo=True)
            save(ADDED, {})
        return

    imgs = list_images()
    cache = load(CACHE)
    new = infer_new(imgs, cache)
    if "--new-only" in args:   # 每日增量:只处理这次新推理的图,不把用户在 immich 手动删掉的角色加回来
        imgs = new

    import csv
    ips = {}
    with open(os.path.join(PIXAI_DIR, "selected_tags.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["category"] == "4" and r["ips"] not in ("", "[]"):
                ips[r["name"]] = json.loads(r["ips"])

    cand = {p + ".xmp": tags_for(cache.get(norm(p), []), thr, ips) for p in imgs}
    cand = {s: t for s, t in cand.items() if t}
    print(f"门槛 {thr}: 有 PixAI 角色的图 {len(cand)} 张,读取现有标签...")
    have = read_taglists(list(cand))
    todo = {}
    for s, tags in cand.items():
        new = [t for t in tags if t not in set(have[s])]
        if any(t.startswith("character/") for t in new):
            todo[s] = new
    newchar_imgs = sum(not any(t.startswith("character/") for t in have[s]) for s in todo)
    per = collections.Counter(t for v in todo.values() for t in v if t.startswith("character/"))
    print(f"需要改 {len(todo)} 个 sidecar(其中原本完全没有角色的 {newchar_imgs} 张),"
          f"新增 {sum(len(v) for v in todo.values())} 个标签,涉及 {len(per)} 个角色")
    print("  最多的角色:", ", ".join(f"{c[10:]}({n})" for c, n in per.most_common(15)))
    for s, tags in list(todo.items())[:3]:
        print(f"  例: {os.path.basename(s)} -> {tags}")
    if not todo:
        print("没有需要补的角色。")
        return
    if not confirm:
        print(f"[DRY-RUN] 未修改。确认后: python pixai_characters.py --confirm")
        return
    write(todo, undo=False)
    for s, tags in todo.items():
        added[s] = list(dict.fromkeys(added.get(s, []) + tags))
    save(ADDED, added)
    from backfill_concepts import trigger_immich
    trigger_immich()


if __name__ == "__main__":
    main()
