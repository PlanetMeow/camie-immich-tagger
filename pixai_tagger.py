# -*- coding: utf-8 -*-
"""
PixAI tagger v0.9(ONNX,deepghs 转换版)推理核心。用来补 camie 认不准的角色。

- 模型:deepghs/pixai-tagger-v0.9-onnx(HuggingFace,1.27GB,Apache-2.0),放到 config.PIXAI_MODEL_DIR
  需要的文件:model.onnx  selected_tags.csv(README 有下载说明)
- 只有两类:general(9741)和 character(3720);不输出作品/画师
- 作品从标签表 selected_tags.csv 的 ips 列反查(角色 -> 所属作品,不靠模型猜)
- 预处理按 preprocess.json:直接缩放到 448x448(bilinear),像素 (x-0.5)/0.5
- 官方门槛 thresholds.csv:general 0.3,character 0.85

用法:
    from pixai_tagger import PixaiTagger
    t = PixaiTagger()
    pred = t.predict(r"E:\\...\\img.jpg", threshold=0.1)   # {"general": [(tag, p)], "character": [(tag, p)]}
    t.copyrights_of("huohuo_(honkai:_star_rail)")         # -> ['honkai:_star_rail', ...]
单图:python pixai_tagger.py "<图片路径>"
"""
import os
import sys
import csv
import json

import numpy as np
import onnxruntime as ort
from PIL import Image

import camie_tagger  # noqa: F401  复用它的 nvidia DLL 注入(否则 cuDNN 加载失败回落 CPU)

import config

MODEL_DIR = getattr(config, "PIXAI_MODEL_DIR", os.path.join(config.WORK_DIR, "models", "pixai-tagger-v0.9"))
IMG_SIZE = 448
CAT_NAMES = {"0": "general", "4": "character"}
THRESHOLDS = {"general": 0.3, "character": 0.85}


class PixaiTagger:
    def __init__(self, model_dir=MODEL_DIR):
        self.tags, self.cats, self.ips = [], [], {}
        with open(os.path.join(model_dir, "selected_tags.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.tags.append(r["name"])
                self.cats.append(CAT_NAMES.get(r["category"], r["category"]))
                if r["category"] == "4" and r["ips"] not in ("", "[]"):
                    self.ips[r["name"]] = json.loads(r["ips"])
        self.sess = ort.InferenceSession(os.path.join(model_dir, "model.onnx"),
                                         providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name
        print(f"[pixai] providers = {self.sess.get_providers()}  tags = {len(self.tags)}")

    @staticmethod
    def preprocess(img_path):
        with Image.open(img_path) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.getchannel("A"))
                im = bg
            else:
                im = im.convert("RGB")
            im = im.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
        arr = (np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5
        return arr.transpose(2, 0, 1)[None, ...].astype(np.float32)

    def probs(self, img_path):
        return self.sess.run(["prediction"], {self.input_name: self.preprocess(img_path)})[0][0]

    def predict(self, img_path, threshold=0.1):
        p = self.probs(img_path)
        out = {"general": [], "character": []}
        for i in np.where(p >= threshold)[0]:
            out.setdefault(self.cats[i], []).append((self.tags[i], float(p[i])))
        for k in out:
            out[k].sort(key=lambda x: -x[1])
        return out

    def copyrights_of(self, character):
        return self.ips.get(character, [])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('用法: python pixai_tagger.py "<图片路径>"')
    t = PixaiTagger()
    pred = t.predict(sys.argv[1], 0.1)
    for c in pred["character"][:5]:
        print(f"  角色 {c[1]:.2f} {c[0]}  作品={t.copyrights_of(c[0])}")
    print("  general(>=0.3):", [g for g, p in pred["general"] if p >= THRESHOLDS["general"]][:25])
