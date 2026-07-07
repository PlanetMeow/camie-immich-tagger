# -*- coding: utf-8 -*-
"""
Tier 0:用 SauceNAO 给「有作品但 camie 没认出角色」的图补角色/作品/画师。
直接用 requests 裸调 SauceNAO /search.php(saucenao_api 库会把正常 200 误判成 status<0,弃用)。

流程:POST 本地图 -> 取相似度>=88% 的最佳 Danbooru 条目 -> 用 danbooru_id 回查 Danbooru
      拿规范标签(下划线格式,与 camie 一致)-> 并集写进 sidecar。
限流:每天最多 180 次,读 long_remaining 见底自动停;每次间隔 18 秒。
断点续跑:已处理记进 tier0_progress.json。每天跑一次,约 21 天。

依赖:requests(venv_camie 应已有;没有则 pip install requests)
用法:python tier0_saucenao.py
"""
import os
import re
import json
import time
import urllib.request

import requests
from sidecar_writer import write_sidecar_taglist

# ============ 配置 ============
from config import SAUCENAO_API_KEY, NO_CHAR_LIST as CANDIDATES, TIER0_PROGRESS as PROGRESS
SIMILARITY_THRESH = 88.0
DAILY_CAP = 180
INTERVAL = 18
LONG_MARGIN = 3
SAUCENAO_URL = "https://saucenao.com/search.php"
DANBOORU_UA = "ImageTaggerTier0/1.0 (personal hobby)"
# ==============================


def load_progress():
    if os.path.exists(PROGRESS):
        return json.load(open(PROGRESS, encoding="utf-8"))
    return {}


def save_progress(prog):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False)


def get_danbooru_id(data):
    if data.get("danbooru_id"):
        try:
            return int(data["danbooru_id"])
        except Exception:
            pass
    for u in data.get("ext_urls", []) or []:
        m = re.search(r"donmai\.us/posts/(\d+)", u)
        if m:
            return int(m.group(1))
    return None


def saucenao_search(img_path):
    """裸调 SauceNAO,返回 (header_dict, results_list)。抛异常交给上层处理。"""
    params = {"api_key": SAUCENAO_API_KEY, "output_type": "2", "numres": "8", "db": "999"}
    with open(img_path, "rb") as fh:
        resp = requests.post(SAUCENAO_URL, params=params, files={"file": fh}, timeout=40)
    resp.raise_for_status()
    j = resp.json()
    return j.get("header", {}), j.get("results", []) or []


def best_danbooru_match(results):
    for r in results:
        try:
            sim = float(r["header"]["similarity"])
        except Exception:
            continue
        if sim < SIMILARITY_THRESH:
            continue
        did = get_danbooru_id(r.get("data", {}))
        if did:
            return sim, did
    return None


def fetch_danbooru_tags(post_id):
    url = f"https://danbooru.donmai.us/posts/{post_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": DANBOORU_UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        post = json.loads(r.read())
    out = []
    for c in post.get("tag_string_character", "").split():
        out.append(f"character/{c.replace('/', '_')}")
    for c in post.get("tag_string_copyright", "").split():
        out.append(f"copyright/{c.replace('/', '_')}")
    for a in post.get("tag_string_artist", "").split():
        out.append(f"artist/{a.replace('/', '_')}")
    return out


def main():
    if not os.path.exists(CANDIDATES):
        raise SystemExit(f"找不到 {CANDIDATES},先跑 char_stats.py")
    with open(CANDIDATES, encoding="utf-8") as f:
        imgs = [l.strip() for l in f if l.strip()]
    prog = load_progress()
    todo = [p for p in imgs if p not in prog and os.path.exists(p)]
    print(f"候选 {len(imgs)}  已处理 {len(prog)}  本次待处理 {len(todo)}")
    if not todo:
        print("全部处理完毕。")
        return

    done = hit = miss = err = 0
    t0 = time.time()

    for img in todo:
        if done >= DAILY_CAP:
            print(f"\n已达今日上限 {DAILY_CAP},停止。明天再跑续跑。")
            break
        try:
            header, results = saucenao_search(img)
        except Exception as e:
            print(f"\nSauceNAO 请求失败: {e}\n停止保住进度,稍后再续。")
            break

        status = header.get("status", 0)
        if status != 0:
            print(f"\nSauceNAO header.status={status}(异常),停止。稍后再续。")
            break

        m = best_danbooru_match(results)
        if m:
            sim, did = m
            try:
                taglist = fetch_danbooru_tags(did)
                res = write_sidecar_taglist(img, taglist) if taglist else "NO_TAGS"
                chars = [t for t in taglist if t.startswith("character/")]
                prog[img] = f"hit:{sim:.0f}%:{','.join(chars)}"
                hit += 1
                print(f"  HIT {sim:.0f}%  {os.path.basename(img)}  -> {chars or taglist}  [{res}]")
            except Exception as e:
                err += 1
                prog[img] = f"hit_but_danbooru_err:{str(e)[:60]}"
                print(f"  HIT 但回查 Danbooru 失败: {e}")
        else:
            miss += 1
            prog[img] = "miss"

        save_progress(prog)
        done += 1

        lr = header.get("long_remaining")
        if lr is not None and lr <= LONG_MARGIN:
            print(f"\n日配额将尽(long_remaining={lr}),停止。明天再续。")
            break

        if done % 10 == 0:
            print(f"  ...{done} 处理  hit={hit} miss={miss} err={err}  "
                  f"(short_rem={header.get('short_remaining','?')} long_rem={lr})")
        time.sleep(INTERVAL)

    print("\n" + "=" * 50)
    print(f"本次:处理 {done}  命中 {hit}  未命中 {miss}  错误 {err}  耗时 {time.time()-t0:.0f}s")
    print(f"累计已处理 {len(prog)} / {len(imgs)}")
    if hit:
        print("有新命中。去 immich 跑「边车元数据→发现」导入补的角色标签。")
    if len(prog) < len(imgs):
        print("没跑完。明天再跑同一条命令,自动续跑。")


if __name__ == "__main__":
    main()
