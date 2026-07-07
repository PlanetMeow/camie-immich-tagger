# probe_camie.py —— Step 1: 探明 camie-tagger-v2 的 metadata 结构 + ONNX I/O 契约 + 输出值域
# 用法(venv_camie / Python 3.11.9):
#   python probe_camie.py "D:\你的\camie模型目录"     # 指定目录
#   python probe_camie.py                              # 不给路径则用默认目录,缺文件自动下载
# 只读诊断,不改你的任何图片/库。

import os
# HF 镜像必须在 import huggingface_hub 之前设置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import sys, json, glob
import numpy as np
import onnxruntime as ort

REPO_ID = "Camais03/camie-tagger-v2"
from config import MODEL_DIR as DEFAULT_DIR
MODEL_DIR = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR


def find_files(d):
    onnx = glob.glob(os.path.join(d, "**", "*.onnx"), recursive=True)
    meta = glob.glob(os.path.join(d, "**", "*metadata*.json"), recursive=True)
    return (onnx[0] if onnx else None), (meta[0] if meta else None)


# --- 0. 定位文件,缺了就从镜像下载(只下 onnx + metadata) ---
onnx_path, meta_path = find_files(MODEL_DIR)
if not (onnx_path and meta_path):
    print(f"[dl] 本地未找全,准备从 {os.environ['HF_ENDPOINT']} 下载到 {MODEL_DIR} ...")
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id=REPO_ID,
        allow_patterns=["*.onnx", "*metadata*.json"],
        local_dir=MODEL_DIR,
    )
    onnx_path, meta_path = find_files(MODEL_DIR)

assert onnx_path and meta_path, f"仍未找到模型/metadata,检查目录: {MODEL_DIR}"
print(f"[file] onnx = {onnx_path}")
print(f"[file] meta = {meta_path}")
print(f"[file] onnx size = {os.path.getsize(onnx_path)/1e6:.1f} MB\n")

# ============ 1. dump metadata 顶层结构 ============
print("=" * 60)
print("METADATA STRUCTURE")
print("=" * 60)
meta = json.load(open(meta_path, "r", encoding="utf-8"))
print(f"[meta] top-level type = {type(meta).__name__}")

if isinstance(meta, dict):
    for k, v in meta.items():
        t = type(v).__name__
        n = len(v) if hasattr(v, "__len__") else "-"
        print(f"  key={k!r:28} type={t:6} len={n}")
        if isinstance(v, dict):
            for sk in list(v.keys())[:3]:
                sv = repr(v[sk])
                print(f"      sample: {sk!r} -> {sv[:120]}")
        elif isinstance(v, list):
            print(f"      sample[:3]: {repr(v[:3])[:200]}")
        else:
            print(f"      value: {repr(v)[:120]}")
    # 重点信息探测
    print("\n[meta] 关键 key 探测:")
    for hint in ("categor", "thresh", "rating", "idx", "tag", "name", "year"):
        hits = [k for k in meta if hint.lower() in k.lower()]
        if hits:
            print(f"   含 {hint!r:9}: {hits}")

elif isinstance(meta, list):
    print(f"[meta] list 长度 = {len(meta)}")
    print(f"[meta] sample[:3] = {repr(meta[:3])[:300]}")

# 尝试统计各 category 的标签数(结构未知,做几种常见假设的兜底探测)
print("\n[meta] 尝试统计 category 分布(若结构匹配):")
try:
    cats = {}
    # 假设 A: meta 里有一个 list,每项含 'category' 字段
    cand_lists = [v for v in (meta.values() if isinstance(meta, dict) else [meta])
                  if isinstance(v, list) and v and isinstance(v[0], dict)]
    for lst in cand_lists:
        if "category" in lst[0]:
            for item in lst:
                cats[item.get("category")] = cats.get(item.get("category"), 0) + 1
            break
    print("   ->", cats if cats else "未自动匹配(把上面的结构发我,我来写解析)")
except Exception as e:
    print("   -> 自动统计失败:", e)

# ============ 2. ONNX I/O 契约 ============
print("\n" + "=" * 60)
print("ONNX I/O")
print("=" * 60)
sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
for i in sess.get_inputs():
    print(f"[in ] name={i.name!r:24} shape={i.shape} type={i.type}")
for o in sess.get_outputs():
    print(f"[out] name={o.name!r:24} shape={o.shape} type={o.type}")

# ============ 3. zeros 输入跑一遍,看输出值域 -> logits or probs ============
print("\n" + "=" * 60)
print("OUTPUT VALUE RANGE (zeros input)")
print("=" * 60)
inp = sess.get_inputs()[0]
side = next((d for d in inp.shape if isinstance(d, int) and d > 3), 512)
x = np.zeros((1, 3, side, side), dtype=np.float32)
outs = sess.run(None, {inp.name: x})
for o_meta, arr in zip(sess.get_outputs(), outs):
    a = np.asarray(arr)
    verdict = "概率(已sigmoid)" if (a.min() >= 0 and a.max() <= 1) else "logits(需sigmoid)"
    print(f"[val] {o_meta.name!r}: shape={a.shape} "
          f"min={a.min():.4f} max={a.max():.4f} mean={a.mean():.4f}  => 疑似 {verdict}")

print("\n[done] 把以上完整打印贴回对话。")
