# -*- coding: utf-8 -*-
"""
Block 2: sidecar 读取 + 并集合并写入(写 immich 认的 XMP-digiKam:TagsList)
关键:所有参数(标签+路径)统一走 UTF-8 argfile + `exiftool -charset utf8 -@`,
     这是中文 Windows 上唯一可靠的方式(直接传中文命令行参数会被 GBK 腐蚀成 ????)。

- sidecar 路径: <图名.扩展名>.xmp  (immich 优先认 .png.xmp 全名追加形式)
- 只把"现有里没有的新标签"用 += 追加 -> 保留手动 tag、不重复、天然幂等
- 只动 TagsList,不碰 sidecar 里的 Rating/Description/GPS 等其他字段
- argfile 落在 EXIFTOOL 所在目录,避开中文用户名 TEMP 路径

被 block 3 import:
    from sidecar_writer import write_sidecar_taglist, read_sidecar_taglist
"""
import os
import json
import tempfile
import subprocess

from config import EXIFTOOL
WORKDIR = os.path.dirname(EXIFTOOL)  # argfile 临时文件目录(纯英文路径)


def _run_exiftool(arg_lines):
    """把参数行写进 UTF-8 argfile 再执行,返回 (stdout, stderr)"""
    fd, argfile = tempfile.mkstemp(suffix=".txt", dir=WORKDIR)
    os.close(fd)
    try:
        with open(argfile, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(arg_lines) + "\n")
        r = subprocess.run(
            [EXIFTOOL, "-charset", "utf8", "-charset", "filename=UTF8", "-@", argfile],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        return (r.stdout or ""), (r.stderr or "")
    finally:
        try:
            os.unlink(argfile)
        except Exception:
            pass


def read_sidecar_taglist(img_path):
    """读取 <img_path>.xmp 里现有的 TagsList;无 sidecar 返回 []"""
    sidecar = img_path + ".xmp"
    if not os.path.exists(sidecar):
        return []
    out, _ = _run_exiftool(["-j", "-XMP-digiKam:TagsList", sidecar])
    try:
        val = json.loads(out)[0].get("TagsList", [])
    except Exception:
        return []
    if isinstance(val, str):
        return [val]
    return list(val) if val else []


def write_sidecar_taglist(img_path, taglist):
    """
    把 taglist(层级字符串列表,如 'character/emilia_(re:zero)')并集合并进 sidecar。
    返回: '+N' / 'NO_CHANGE' / 'ERR:...'
    """
    sidecar = img_path + ".xmp"
    existing = set(read_sidecar_taglist(img_path))
    new_only = [t for t in taglist if t and t not in existing]
    if not new_only:
        return "NO_CHANGE"

    if os.path.exists(sidecar):
        lines = ["-overwrite_original"]
        lines += [f"-XMP-digiKam:TagsList+={t}" for t in new_only]
        lines += [sidecar]
    else:  # 新建 sidecar:-o 从零创建
        lines = [f"-XMP-digiKam:TagsList+={t}" for t in new_only]
        lines += ["-o", sidecar]

    out, err = _run_exiftool(lines)
    blob = out + err
    if "image files created" in blob or "image files updated" in blob:
        return f"+{len(new_only)}"
    return f"ERR:{blob.strip()[:200]}"


# ---------------- 自测:用本地 exiftool.exe 复跑全流程(含中文) ----------------
if __name__ == "__main__":
    import shutil
    d = tempfile.mkdtemp(dir=WORKDIR)  # 工作目录内,避开中文用户名 TEMP
    img = os.path.join(d, "selftest.png")
    open(img, "w").close()
    try:
        print("1. 新建 sidecar(英文层级 + 中文 zh/ 分支):",
              write_sidecar_taglist(img, [
                  "character/emilia_(re:zero)", "general/long_hair", "zh/长发"]))
        print("   ->", read_sidecar_taglist(img))

        # 模拟 immich 手动加 tag + Rating(纯 ASCII,直接传参没问题)
        subprocess.run([EXIFTOOL, "-charset", "utf8", "-overwrite_original",
                        "-XMP-digiKam:TagsList+=manual/fav", "-XMP:Rating=5",
                        img + ".xmp"], capture_output=True)
        print("2. 模拟手动加 manual/fav + Rating=5 ->", read_sidecar_taglist(img))

        print("3. 再合并(部分重复 + 新增 braid/辫子):",
              write_sidecar_taglist(img, [
                  "general/long_hair", "general/braid", "zh/辫子"]))
        print("   ->", read_sidecar_taglist(img))

        print("4. 完全重复(应幂等 NO_CHANGE):",
              write_sidecar_taglist(img, ["general/braid", "zh/辫子"]))

        rating = subprocess.run([EXIFTOOL, "-charset", "utf8", "-j", "-XMP:Rating",
                                 img + ".xmp"], capture_output=True, text=True,
                                encoding="utf-8").stdout
        print("5. Rating 是否被保住:", json.loads(rating)[0].get("Rating"))

        tl = read_sidecar_taglist(img)
        ok = ("manual/fav" in tl and "general/braid" in tl and "zh/辫子" in tl
              and "zh/长发" in tl and tl.count("general/long_hair") == 1)
        print("\n自测结果:", "PASS" if ok else "FAIL")
    finally:
        shutil.rmtree(d, ignore_errors=True)
