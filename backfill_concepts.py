# -*- coding: utf-8 -*-
"""
给已打标的图补写中文概念标签 zh/<大类>/<概念>(见 concept_tags.py)和角色/作品中文名
zh/角色/<名>、zh/作品/<名>(见 zh_names.py),不重跑模型:
读每个 sidecar 里已有的 general/ character/ copyright/ 标签 -> 只追加缺的。

- 只增不减:不动已有标签 / 手动标签 / Rating 等字段;用 "-=x -+=x" 写法保证不重复
- 批量:一次 exiftool 调用处理 BATCH 个文件(argfile + -execute),比逐个调用快很多
- 默认 DRY-RUN;--confirm 才写;写完触发 immich「边车 check(全部)」重新读取
- --undo:删除全部概念标签(zh/<CONCEPTS 里的大类>/...),恢复原状(同样默认 dry-run)

用法:
    python backfill_concepts.py                 # dry-run 统计
    python backfill_concepts.py --confirm       # 写入 + 触发 immich
    python backfill_concepts.py --undo [--confirm]
    python backfill_concepts.py --list 文件.txt  # 只处理清单里的图(每行一个图片路径,测试用)
    python backfill_concepts.py --limit 50      # 只处理前 50 个(测试用)
"""
import os
import sys
import json
import time
import tempfile
import subprocess
import collections

from concept_tags import concept_tags, CONCEPTS
from zh_names import name_tags

from config import EXIFTOOL, DONE_LIST
WORKDIR = os.path.dirname(EXIFTOOL)          # argfile 放纯英文路径下
READ_BATCH = 500
WRITE_BATCH = 200
CATS = sorted({p.split("/", 1)[0] for p in CONCEPTS} | {"角色", "作品"})


def _argfile_run(lines, timeout=1800):
    fd, arg = tempfile.mkstemp(suffix=".txt", dir=WORKDIR)
    os.close(fd)
    try:
        with open(arg, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        r = subprocess.run([EXIFTOOL, "-charset", "utf8", "-charset", "filename=UTF8", "-@", arg],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.stdout or "", r.stderr or ""
    finally:
        os.unlink(arg)


def read_taglists(sidecars):
    out = {}
    for i in range(0, len(sidecars), READ_BATCH):
        chunk = sidecars[i:i + READ_BATCH]
        stdout, _ = _argfile_run(["-j", "-XMP-digiKam:TagsList"] + chunk)
        for d in json.loads(stdout or "[]"):
            tl = d.get("TagsList", [])
            out[os.path.normcase(os.path.normpath(d["SourceFile"]))] = [tl] if isinstance(tl, str) else (tl or [])
        print(f"  读取 {min(i + READ_BATCH, len(sidecars))}/{len(sidecars)}", flush=True)
    return {s: out.get(os.path.normcase(os.path.normpath(s)), []) for s in sidecars}


def is_concept_tag(t):
    parts = t.split("/")
    return len(parts) == 3 and parts[0] == "zh" and parts[1] in CATS


def plan(taglists, undo):
    """返回 {sidecar: [要加/删的标签]}"""
    todo = {}
    for s, tl in taglists.items():
        if undo:
            rm = [t for t in tl if is_concept_tag(t)]
            if rm:
                todo[s] = rm
        else:
            have = set(tl)
            want = concept_tags([t[8:] for t in tl if t.startswith("general/")]) + name_tags(tl)
            add = [t for t in want if t not in have]
            if add:
                todo[s] = add
    return todo


def apply(todo, undo):
    items = list(todo.items())
    updated = failed = 0
    for i in range(0, len(items), WRITE_BATCH):
        batch = items[i:i + WRITE_BATCH]
        lines = []
        for s, tags in batch:
            lines.append("-overwrite_original")
            for t in tags:
                lines.append(f"-XMP-digiKam:TagsList-={t}")
                if not undo:
                    lines.append(f"-XMP-digiKam:TagsList+={t}")
            lines += [s, "-execute"]
        out, err = _argfile_run(lines)
        blob = out + err
        u = blob.count("1 image files updated")
        updated += u
        failed += len(batch) - u
        print(f"  写入 {min(i + WRITE_BATCH, len(items))}/{len(items)}  已更新 {updated}  失败 {failed}", flush=True)
        if "Error" in err:
            print("   exiftool 报错(前 300 字):", err.strip()[:300])
    return updated, failed


def trigger_immich():
    from camie_pipeline import _put_job
    try:
        print(f"[immich] 边车 check(全部)-> {_put_job('sidecar', True)}  immich 会重新读取 sidecar 里的标签")
    except Exception as e:
        print(f"[immich] 触发失败: {e}  请手动:任务 -> 边车元数据 -> 全部")


def main():
    args = sys.argv[1:]
    confirm, undo = "--confirm" in args, "--undo" in args
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    src = args[args.index("--list") + 1] if "--list" in args else DONE_LIST

    imgs = [l.strip() for l in open(src, encoding="utf-8") if l.strip()]
    seen, sidecars = set(), []
    for p in imgs:
        s = p + ".xmp"
        k = os.path.normcase(os.path.normpath(s))
        if k not in seen and os.path.exists(s):
            seen.add(k)
            sidecars.append(s)
    if limit:
        sidecars = sidecars[:limit]
    mode = "撤销(删除概念标签)" if undo else "补写概念标签"
    print(f"模式: {mode}  {'[写入]' if confirm else '[DRY-RUN]'}  清单 {len(imgs)} 行 -> sidecar {len(sidecars)} 个")

    t0 = time.time()
    taglists = read_taglists(sidecars)
    todo = plan(taglists, undo)
    n_tags = sum(len(v) for v in todo.values())
    per = collections.Counter(t for v in todo.values() for t in v)
    print(f"需要改 {len(todo)} 个文件,共 {'删除' if undo else '新增'} {n_tags} 个标签"
          f"(平均每个 {n_tags / max(len(todo), 1):.1f}),涉及 {len(per)} 种概念  读取耗时 {time.time() - t0:.0f}s")
    for s, tags in list(todo.items())[:3]:
        print(f"  例: {os.path.basename(s)}  -> {tags[:8]}{' ...' if len(tags) > 8 else ''}")

    if not todo:
        print("没有需要修改的文件。")
        return
    if not confirm:
        print(f"[DRY-RUN] 未修改。确认后: python backfill_concepts.py {'--undo ' if undo else ''}--confirm")
        return

    t0 = time.time()
    updated, failed = apply(todo, undo)
    print(f"完成: 更新 {updated} 个,失败 {failed} 个,耗时 {time.time() - t0:.0f}s")
    if "--list" not in args:
        trigger_immich()


if __name__ == "__main__":
    main()
