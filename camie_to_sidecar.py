# -*- coding: utf-8 -*-
"""
Block 3 (step 4 收尾): camie 输出 -> sidecar 标签
  CamieTagger.predict -> 加 类别/ 前缀(英文层级)+ general 查中文生成 zh/ -> write_sidecar_taglist

被 step 5(批量/增量)import:
    from camie_to_sidecar import CamieTagger, tag_image
单图用法:
    python camie_to_sidecar.py "D:\path\to\img.png" [阈值]
"""
import os
import sys

from camie_tagger import CamieTagger          # block 3 复用 step3 的推理核心
from sidecar_writer import write_sidecar_taglist, read_sidecar_taglist
from tag_translations import get_translation_map

TRANS = get_translation_map()

# 写入哪些类别:默认排除 meta(highres/commentary 等低价值)和 year(camie 猜测不可靠)
# 想要的话把 "meta" / "year" 加进来即可
CATS_TO_WRITE = ["character", "copyright", "artist", "general", "rating"]


def build_taglist(pred, trans=TRANS, cats=CATS_TO_WRITE):
    """7 类预测 -> 层级 TagsList 条目列表(英文 类别/标签 + general 的 zh/中文)"""
    out = []
    for cat in cats:
        for tag, prob in pred.get(cat, []):
            safe = tag.replace("/", "_")                 # 防标签内含 / 误建层级
            if cat == "rating" and safe.startswith("rating_"):
                safe = safe[len("rating_"):]             # rating_sensitive -> rating/sensitive
            out.append(f"{cat}/{safe}")
            if cat == "general" and tag in trans:        # 仅 general 翻译
                for zh in trans[tag]:
                    out.append(f"zh/{zh}")
    seen, final = set(), []
    for t in out:
        if t not in seen:
            seen.add(t); final.append(t)
    return final


def tag_image(tagger, img_path, threshold=0.5, cats=CATS_TO_WRITE):
    """对单张图:预测 -> 构建标签 -> 写 sidecar。返回 (taglist, write_result)"""
    pred = tagger.predict(img_path, threshold)
    taglist = build_taglist(pred, TRANS, cats)
    result = write_sidecar_taglist(img_path, taglist)
    return taglist, result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('用法: python camie_to_sidecar.py "<图片路径>" [阈值]')
    img = sys.argv[1]
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5

    tagger = CamieTagger()
    taglist, result = tag_image(tagger, img, thr)

    print(f"\n图片: {img}   阈值: {thr}")
    print(f"生成 {len(taglist)} 个标签,写入结果: {result}")
    print("=" * 60)
    # 分组打印便于眼检
    groups = {}
    for t in taglist:
        top = t.split("/", 1)[0]
        groups.setdefault(top, []).append(t)
    for top in ["character", "copyright", "artist", "general", "rating", "zh"]:
        if top in groups:
            print(f"\n[{top}] ({len(groups[top])})")
            print("  " + ", ".join(groups[top]))

    print("\n" + "=" * 60)
    print("回读 sidecar 确认落盘:")
    back = read_sidecar_taglist(img)
    print(f"  sidecar 现有 {len(back)} 个标签")
    print(f"  sidecar 路径: {img}.xmp")
