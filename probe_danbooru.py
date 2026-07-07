# -*- coding: utf-8 -*-
"""
Tier 0 探针:从「有作品但无角色」的图里抽样,算 MD5 查 Danbooru,看命中率。
命中率决定 Tier 0 走哪条路(MD5 精确查 vs SauceNAO 相似搜)。
在你的机器上跑(需要能访问 danbooru.donmai.us + 本地图片在)。

用法: python probe_danbooru.py [抽样数,默认50]
"""
import os
import sys
import time
import json
import random
import hashlib
import urllib.request
import urllib.parse

from config import NO_CHAR_LIST
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 50
SLEEP = 1.0  # 每次请求间隔秒,对 Danbooru 礼貌
UA = "ImageTaggerProbe/1.0 (personal library hobby project)"

# 可选:填了能提高限额(全量跑时建议;探针匿名即可)
DANBOORU_LOGIN = ""
DANBOORU_API_KEY = ""


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def query_danbooru(md5):
    params = {"tags": f"md5:{md5}", "limit": "1"}
    if DANBOORU_LOGIN and DANBOORU_API_KEY:
        params["login"] = DANBOORU_LOGIN
        params["api_key"] = DANBOORU_API_KEY
    url = "https://danbooru.donmai.us/posts.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data[0] if data else None


def main():
    if not os.path.exists(NO_CHAR_LIST):
        raise SystemExit(f"找不到 {NO_CHAR_LIST},先跑 char_stats.py")
    with open(NO_CHAR_LIST, encoding="utf-8") as f:
        imgs = [l.strip() for l in f if l.strip()]
    imgs = [p for p in imgs if os.path.exists(p)]
    print(f"候选 {len(imgs)} 张,随机抽 {SAMPLE} 张探测\n")
    sample = random.sample(imgs, min(SAMPLE, len(imgs)))

    hit = miss = err = 0
    hit_examples = []
    for i, p in enumerate(sample, 1):
        try:
            post = query_danbooru(md5_of(p))
            if post:
                hit += 1
                chars = post.get("tag_string_character", "").split()
                copies = post.get("tag_string_copyright", "").split()
                if len(hit_examples) < 12:
                    hit_examples.append((os.path.basename(p), chars, copies))
                mark = f"HIT  角色={chars or '(无)'}"
            else:
                miss += 1
                mark = "miss"
        except Exception as e:
            err += 1
            mark = f"ERR {str(e)[:40]}"
        print(f"  [{i}/{len(sample)}] {mark}")
        time.sleep(SLEEP)

    done = hit + miss
    rate = hit / done * 100 if done else 0
    print("\n" + "=" * 50)
    print(f"命中 {hit} / 有效 {done}  (错误 {err})")
    print(f"MD5 命中率: {rate:.0f}%")
    print("=" * 50)
    print("\n命中样本(Danbooru 有、camie 没认出的角色):")
    for name, chars, copies in hit_examples:
        print(f"  {name}")
        print(f"     角色: {chars or '(Danbooru 上也无角色)'}")
        print(f"     作品: {copies}")

    print("\n判读:")
    if rate >= 40:
        print("  命中率高 -> 你的图多是 booru 原图,主力走 MD5 精确查,快且准。Tier 0 可行。")
    elif rate >= 15:
        print("  命中率中 -> MD5 能覆盖一部分,其余靠 SauceNAO 兜底。Tier 0 半可行。")
    else:
        print("  命中率低 -> 图大多改过/非 booru 原图,MD5 路废,只能全靠 SauceNAO 慢跑。重新评估值不值。")


if __name__ == "__main__":
    main()
