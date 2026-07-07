# -*- coding: utf-8 -*-
"""
Step 5: camie 一体化批量流水线(方案 A,无 jsonl 中间产物)
  发现全部图 -> CamieTagger.predict -> build_taglist -> 写 sidecar -> 触发 immich

复用已验证模块:camie_tagger / camie_to_sidecar / sidecar_writer / tag_translations
用法:
  python camie_pipeline.py test        # 前 20 张试跑
  python camie_pipeline.py all         # 全量
  python camie_pipeline.py all 0.45    # 全量 + 自定阈值
"""
import os
import sys
import time
import json
import urllib.request

from camie_tagger import CamieTagger          # GPU 推理核心(只加载一次)
from camie_to_sidecar import tag_image, CATS_TO_WRITE
from sidecar_writer import read_sidecar_taglist

# ============ 配置 ============
from config import (SCAN_DIRS, ERROR_LOG, DONE_LIST,
                    IMMICH_URL, IMMICH_API_KEY, LIBRARY_IDS)
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
THRESHOLD = 0.5
TEST_COUNT = 20
PROGRESS_EVERY = 50
# 这些前缀出现在 sidecar 里 = 已被 camie 打过标,断点续跑时跳过
CAMIE_PREFIXES = tuple(f"{c}/" for c in CATS_TO_WRITE) + ("zh/",)
# ==============================


def collect_images():
    imgs = []
    for d in SCAN_DIRS:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for fn in files:
                    if os.path.splitext(fn)[1].lower() in EXTS:
                        imgs.append(os.path.join(root, fn))
    return imgs


def load_done():
    """已处理清单(recent 模式靠它判断新图,不靠 mtime)"""
    if os.path.exists(DONE_LIST):
        return set(l.strip() for l in open(DONE_LIST, encoding="utf-8") if l.strip())
    return set()


def append_done(paths):
    if paths:
        with open(DONE_LIST, "a", encoding="utf-8") as f:
            for p in paths:
                f.write(p + "\n")


def rebuild_done(paths):
    """all 模式跑完后重建完整清单(去重)"""
    with open(DONE_LIST, "w", encoding="utf-8") as f:
        for p in sorted(set(paths)):
            f.write(p + "\n")


def already_camie_tagged(img_path):
    """sidecar 里已有 camie 类前缀标签 -> 视为已打标(跳过,省 GPU)"""
    tags = read_sidecar_taglist(img_path)
    return any(t.startswith(CAMIE_PREFIXES) for t in tags)


def log_error(img_path, msg):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"file": img_path, "error": str(msg)[:300]},
                           ensure_ascii=False) + "\n")


def _put_job(name, force):
    url = f"{IMMICH_URL}/api/jobs/{name}"
    body = json.dumps({"command": "start", "force": force}).encode()
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("x-api-key", IMMICH_API_KEY)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def trigger_immich():
    if not IMMICH_API_KEY or IMMICH_API_KEY.startswith("在此填入"):
        print("[immich] 未配置 API key,请手动:任务 -> 边车元数据 -> 发现(全部)")
        return
    # 1. 库扫描(发现可能的新图片文件)
    for lib in LIBRARY_IDS:
        try:
            req = urllib.request.Request(f"{IMMICH_URL}/api/libraries/{lib}/scan",
                                         method="POST")
            req.add_header("x-api-key", IMMICH_API_KEY)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as r:
                print(f"[immich] 库扫描 {lib[:8]}... -> {r.status}")
        except Exception as e:
            print(f"[immich] 库扫描失败 {lib[:8]}: {e}")
    # 2. 边车 check(force=true=全部):发现+读取新 sidecar,自动衍生提取元数据
    try:
        print(f"[immich] 边车 check(全部)-> {_put_job('sidecar', True)}")
        print("[immich] 已触发,immich 将发现 sidecar 并自动提取标签")
    except Exception as e:
        print(f"[immich] 边车 check 失败: {e}  请手动跑 边车元数据->发现")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    if mode not in ("test", "all", "recent"):
        print("用法: python camie_pipeline.py [test|all|recent] [阈值]")
        print("  test   : 前 20 张(验证用)")
        print("  all    : 全库扫描(换模型/重装时用,慢),跑完重建已处理清单")
        print("  recent : 只处理不在已处理清单里的新图(日常增量,快,抗 mtime 污染)")
        return
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else THRESHOLD

    print("=" * 56)
    print(f"camie 一体化流水线  模式={mode}  阈值={thr}")
    print("=" * 56)

    all_imgs = collect_images()
    done_set = load_done() if mode == "recent" else set()
    if mode == "recent":
        all_imgs = [p for p in all_imgs if p not in done_set]
        print(f"磁盘图片总数已扫,扣除已处理清单后待处理: {len(all_imgs)} 张")
    else:
        print(f"扫描到 {len(all_imgs)} 张图")
    if mode == "test":
        all_imgs = all_imgs[:TEST_COUNT]

    if not all_imgs:
        print("没有需要处理的图。")
        trigger_immich()
        return

    # 模型只加载一次(789MB,严禁循环内重载)
    tagger = CamieTagger()

    t0 = time.time()
    done = ok = skip = err = 0
    total = len(all_imgs)
    processed = []   # 本次成功处理(打标 or 已存在标签)的图,用于写 done 清单
    for img in all_imgs:
        done += 1
        try:
            if already_camie_tagged(img):
                skip += 1
                processed.append(img)
            else:
                taglist, result = tag_image(tagger, img, thr)
                if result.startswith("+") or result == "NO_CHANGE":
                    ok += 1
                    processed.append(img)
                else:
                    err += 1
                    log_error(img, result)
        except Exception as e:
            err += 1
            log_error(img, e)

        show = (mode == "test") or (done % PROGRESS_EVERY == 0) or (done == total)
        if show:
            el = time.time() - t0
            spd = done / el if el else 0
            eta = (total - done) / spd if spd else 0
            print(f"  {done}/{total}  ok={ok} skip={skip} err={err}  "
                  f"({spd:.1f}/s, ETA {eta:.0f}s)")

    print("=" * 56)
    print(f"完成! 耗时 {time.time()-t0:.0f}s  ok={ok} skip={skip} err={err}")
    if err:
        print(f"失败 {err} 张,详见 {ERROR_LOG}")

    # 维护已处理清单(recent 模式的判据)
    if mode == "recent":
        new = [p for p in processed if p not in done_set]
        append_done(new)
        print(f"[done清单] 追加 {len(new)} 张,清单总计 {len(load_done())}")
    elif mode == "all":
        rebuild_done(processed)
        print(f"[done清单] 已重建,共 {len(processed)} 张")

    print("=" * 56)
    trigger_immich()


if __name__ == "__main__":
    main()
