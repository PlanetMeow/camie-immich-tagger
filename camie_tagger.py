# camie_tagger.py —— Step 3: camie-tagger-v2 打标核心(可复用模块)
# 用法(venv_camie):
#   python camie_tagger.py "D:\path\to\test.jpg"          # 默认阈值 0.5
#   python camie_tagger.py "D:\path\to\test.jpg" 0.35     # 自定阈值
# step 4 会 import CamieTagger 复用预处理+推理,叠加翻译和 sidecar 写入。

import os, json, glob, site
import numpy as np
import onnxruntime as ort
from PIL import Image

# ---- 让 onnxruntime / cuDNN 找到 pip 安装的 nvidia CUDA/cuDNN 子库 DLL ----
# cuDNN 9 的引擎子库(cudnn_engines_*.dll)由 cuDNN 主库在运行时动态加载,走标准 DLL 搜索;
# 必须把 site-packages\nvidia\*\bin 同时加进 DLL 搜索目录 + PATH,否则 SUBLIBRARY_LOADING_FAILED。
def _add_nvidia_dll_dirs():
    dirs = []
    for base in set(site.getsitepackages() + [site.getusersitepackages()]):
        dirs += glob.glob(os.path.join(base, "nvidia", "*", "bin"))
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
    if dirs:  # cuDNN 内部 LoadLibrary 只认 PATH,必须也塞进去
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")

_add_nvidia_dll_dirs()
try:
    ort.preload_dlls()
except Exception:
    pass

from config import MODEL_DIR

# ImageNet 归一化常数(RGB 顺序)——metadata usage.preprocessing 指定
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
IMG_SIZE = 512
CATEGORIES = ["general", "character", "copyright", "artist", "meta", "rating", "year"]


def _sigmoid(x):
    # 数值稳定版,避免大负数 exp 溢出
    return np.where(x >= 0, 1.0 / (1.0 + np.exp(-x)), np.exp(x) / (1.0 + np.exp(x)))


class CamieTagger:
    def __init__(self, model_dir=MODEL_DIR):
        onnx_path = glob.glob(os.path.join(model_dir, "**", "*.onnx"), recursive=True)[0]
        meta_path = glob.glob(os.path.join(model_dir, "**", "*metadata*.json"), recursive=True)[0]

        meta = json.load(open(meta_path, encoding="utf-8"))
        tm = meta["dataset_info"]["tag_mapping"]
        self.idx_to_tag = tm["idx_to_tag"]            # {"0": "year_2005", ...}
        self.tag_to_category = tm["tag_to_category"]  # {"year_2005": "year", ...}

        # 优先 GPU,装的是 CPU 版会自动回落
        self.sess = ort.InferenceSession(
            onnx_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )
        self.input_name = self.sess.get_inputs()[0].name
        print(f"[init] providers = {self.sess.get_providers()}")
        print(f"[init] onnx = {onnx_path}")

    def preprocess(self, img_path):
        img = Image.open(img_path).convert("RGB").resize((IMG_SIZE, IMG_SIZE), Image.BICUBIC)
        arr = np.asarray(img, dtype=np.float32) / 255.0        # HWC, [0,1]
        arr = (arr - IMAGENET_MEAN) / IMAGENET_STD             # 逐通道归一化
        arr = arr.transpose(2, 0, 1)                           # HWC -> CHW
        return arr[None, ...].astype(np.float32)               # -> NCHW (1,3,512,512)

    def predict(self, img_path, threshold=0.5):
        x = self.preprocess(img_path)
        # 只取 refined_predictions,省内存
        logits = self.sess.run(["refined_predictions"], {self.input_name: x})[0][0]  # (70527,)
        probs = _sigmoid(logits)

        idxs = np.where(probs >= threshold)[0]
        out = {c: [] for c in CATEGORIES}
        for i in idxs:
            name = self.idx_to_tag[str(int(i))]
            cat = self.tag_to_category.get(name, "unknown")
            out.setdefault(cat, []).append((name, float(probs[i])))
        for c in out:
            out[c].sort(key=lambda t: t[1], reverse=True)
        return out


# ---------------- 单图眼检 ----------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("用法: python camie_tagger.py <图片路径> [阈值]")
    img_path = sys.argv[1]
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5

    tagger = CamieTagger()
    res = tagger.predict(img_path, thr)

    print(f"\n图片: {img_path}   阈值: {thr}")
    print("=" * 60)
    # 高价值类别全打,general 取前 30,其余取前 10
    show_all = ["character", "copyright", "artist", "rating"]
    for cat in CATEGORIES:
        tags = res.get(cat, [])
        limit = len(tags) if cat in show_all else (30 if cat == "general" else 10)
        head = tags[:limit]
        line = ", ".join(f"{n}({p:.2f})" for n, p in head)
        more = "" if len(tags) <= limit else f"  ...+{len(tags)-limit}"
        print(f"\n[{cat}] ({len(tags)})")
        print(f"  {line}{more}" if head else "  -")
