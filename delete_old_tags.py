# -*- coding: utf-8 -*-
"""
删除 immich 里的 WD14 平铺旧标签,保留 camie 层级标签。
判定:value 的顶层段属于 camie 根 -> 保留;否则 -> 删。

默认 DRY-RUN(只列出、不删)。核对无误后加 --confirm 才真删。
用法:
  python delete_old_tags.py            # dry-run:列出将删哪些,写两份清单
  python delete_old_tags.py --confirm  # 真删
"""
import sys
import json
import urllib.request

from config import IMMICH_URL, IMMICH_API_KEY, DEL_LIST, KEEP_LIST

# camie 写入的根类别 + zh:value 顶层段属于这些 -> 保留;其余一律视为 WD14 旧标签删除
CAMIE_ROOTS = {"character", "copyright", "artist", "general", "rating", "zh"}



def api(method, path, data=None):
    url = f"{IMMICH_URL}/api{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("x-api-key", IMMICH_API_KEY)
    req.add_header("Accept", "application/json")
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)


def classify(tags):
    keep, delete = [], []
    for t in tags:
        val = t.get("value") or t.get("name") or ""
        top = val.split("/", 1)[0]
        (keep if top in CAMIE_ROOTS else delete).append(t)
    return keep, delete


def main():
    confirm = "--confirm" in sys.argv

    _, tags = api("GET", "/tags")
    keep, delete = classify(tags)
    print(f"总标签 {len(tags)}  |  保留(camie) {len(keep)}  |  待删(WD14平铺) {len(delete)}")

    # 写两份清单供过目
    with open(DEL_LIST, "w", encoding="utf-8") as f:
        for t in delete:
            f.write((t.get("value") or "") + "\n")
    with open(KEEP_LIST, "w", encoding="utf-8") as f:
        for t in keep:
            f.write((t.get("value") or "") + "\n")
    print(f"待删完整清单 -> {DEL_LIST}")
    print(f"保留完整清单 -> {KEEP_LIST}")

    print("\n待删示例(前 40):")
    for t in delete[:40]:
        print("  -", t.get("value"))
    print("\n保留示例(前 20,确认 camie 标签都在这边):")
    for t in keep[:20]:
        print("  +", t.get("value"))

    if not confirm:
        print("\n[DRY-RUN] 未删除任何东西。")
        print(f"请打开 {DEL_LIST} 核对——确认全是该删的 WD14 旧标签 / 乱码,")
        print("没有误伤你想保留的标签后,再真删:")
        print("  python delete_old_tags.py --confirm")
        return

    print(f"\n[CONFIRM] 开始删除 {len(delete)} 个标签(只删标签,不动任何图片)...")
    ok = err = 0
    for i, t in enumerate(delete, 1):
        try:
            api("DELETE", f"/tags/{t['id']}")
            ok += 1
        except Exception as e:
            err += 1
            print(f"  删除失败 {t.get('value')}: {e}")
        if i % 100 == 0 or i == len(delete):
            print(f"  {i}/{len(delete)}  ok={ok} err={err}")
    print(f"\n完成:删除 {ok},失败 {err}")
    print("去 immich 标签页刷新,应只剩 character/copyright/artist/general/rating/zh 六棵树")


if __name__ == "__main__":
    main()
