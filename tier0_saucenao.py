# -*- coding: utf-8 -*-
"""
Tier 0:用 SauceNAO 给「有作品但 camie 没认出角色」的图补角色/作品/画师。
直接用 requests 裸调 SauceNAO /search.php(saucenao_api 库会把正常 200 误判成 status<0,弃用)。

流程:POST 本地图 -> 取相似度>=88% 的最佳 Danbooru 条目
      -> 优先回查 Danbooru 拿规范标签(下划线格式,与 camie 一致)
      -> 回查失败(Cloudflare 403 / 超时)时,用 SauceNAO 结果自带的
         characters/material/creator 字段兜底写 sidecar,并把 danbooru_id 记进待重试清单
      -> 并集写进 sidecar。
待重试:每次运行先重试 tier0_danbooru_pending.json 里的 Danbooru 回查(不花 SauceNAO 配额),
        成功就把规范标签并集补进 sidecar。
熔断:Danbooru 连续失败 5 次,本次运行不再请求 Danbooru(SauceNAO 照常跑,走兜底)。
限流:每天最多 180 次,读 long_remaining 见底自动停;每次间隔 18 秒。
断点续跑:已处理记进 tier0_progress.json。

progress 取值:
  hit:<sim>%:<chars>                  Danbooru 规范标签已写入
  hit_sn:<sim>%:<chars>               SauceNAO 字段兜底已写入,Danbooru 待重试
  hit_pending_danbooru:<sim>%         SauceNAO 无标签字段,Danbooru 待重试(还没写 sidecar)
  miss                                未命中
  skip_camera                         相机实拍照片（EXIF 有 Make/Model），不送 SauceNAO（2026-10-05 加）
  hit_but_danbooru_err:...            旧版本遗留(没存 danbooru_id,只能用 fix_tier0_progress.py 重新排队)

依赖:requests(venv_camie 应已有;没有则 pip install requests)
用法:python tier0_saucenao.py
"""
import os
import re
import json
import time
import io

import requests
from PIL import Image
from sidecar_writer import write_sidecar_taglist

# ============ 配置 ============
import config
from config import SAUCENAO_API_KEY, NO_CHAR_LIST as CANDIDATES, TIER0_PROGRESS as PROGRESS
# 旧 config.py 没有 TIER0_PENDING 时用默认路径
PENDING = getattr(config, "TIER0_PENDING", os.path.join(config.WORK_DIR, "tier0_danbooru_pending.json"))
SIMILARITY_THRESH = 88.0
DAILY_CAP = 180
INTERVAL = 18
LONG_MARGIN = 3
SAUCENAO_URL = "https://saucenao.com/search.php"
DANBOORU_UA = "ImageTaggerTier0/1.0 (personal hobby)"
DANBOORU_TIMEOUT = 15
DANBOORU_FAIL_LIMIT = 5     # 连续失败几次后本次运行不再请求 Danbooru
DANBOORU_RETRY_INTERVAL = 1  # 重试待回查清单时每次间隔秒
SAUCENAO_RETRIES = 3        # SauceNAO 请求失败(代理掉线等)先重试几次再停
SAUCENAO_RETRY_WAIT = 60    # 重试间隔秒
UPLOAD_MAX_SIDE = 700       # 上传前缩到长边 700px:代理传 >300KB 的文件经常断开,SauceNAO 本身也只看缩略图
UPLOAD_JPEG_QUALITY = 85
# 队列优先级(可选,在 config.py 里设 TIER0_PRIORITY):按路径正则,第一条匹配的生效;
# 数字小的先搜,None = 不搜(不记进度,改规则即可恢复)。空列表 = 按队列原顺序。
# 作者库实测:插画根目录命中 27%,画册扫描 / AI 生成图约 0%,值得排到最后或不搜。
PRIORITY = getattr(config, "TIER0_PRIORITY", [])
DEFAULT_PRIORITY = getattr(config, "TIER0_DEFAULT_PRIORITY", 2)
# ==============================


def load_json(path):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return {}


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


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


Image.MAX_IMAGE_PIXELS = None  # 大图只是缩小上传,不需要解压炸弹保护


def upload_bytes(img_path):
    """返回 (文件名, 字节):缩成长边 UPLOAD_MAX_SIDE 的 JPEG(透明铺白底);打不开就原样上传"""
    try:
        with Image.open(img_path) as im:
            im.thumbnail((UPLOAD_MAX_SIDE, UPLOAD_MAX_SIDE))
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.getchannel("A"))
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=UPLOAD_JPEG_QUALITY)
            return "upload.jpg", buf.getvalue()
    except Exception:
        with open(img_path, "rb") as fh:
            return os.path.basename(img_path), fh.read()


def saucenao_search(img_path):
    """裸调 SauceNAO,返回 (header_dict, results_list)。抛异常交给上层处理。"""
    params = {"api_key": SAUCENAO_API_KEY, "output_type": "2", "numres": "8", "db": "999"}
    name, data = upload_bytes(img_path)
    resp = requests.post(SAUCENAO_URL, params=params, files={"file": (name, data)}, timeout=40)
    resp.raise_for_status()
    j = resp.json()
    return j.get("header", {}), j.get("results", []) or []


def redact(msg):
    """报错信息里带完整请求 URL(含 api_key),打印/写日志前打码"""
    msg = str(msg)
    if SAUCENAO_API_KEY:
        msg = msg.replace(SAUCENAO_API_KEY, "***")
    return re.sub(r"api_key=[^&\s'\"]+", "api_key=***", msg)


def saucenao_search_retry(img_path):
    """失败先重试 SAUCENAO_RETRIES 次(间隔 SAUCENAO_RETRY_WAIT 秒),仍失败再抛出"""
    for attempt in range(SAUCENAO_RETRIES + 1):
        try:
            return saucenao_search(img_path)
        except Exception as e:
            if attempt == SAUCENAO_RETRIES:
                raise
            print(f"  SauceNAO 请求失败(第 {attempt + 1} 次),{SAUCENAO_RETRY_WAIT}s 后重试: {redact(e)}",
                  flush=True)
            time.sleep(SAUCENAO_RETRY_WAIT)


def best_danbooru_match(results):
    """返回 (相似度, danbooru_id, 该条 data) 或 None"""
    for r in results:
        try:
            sim = float(r["header"]["similarity"])
        except Exception:
            continue
        if sim < SIMILARITY_THRESH:
            continue
        data = r.get("data", {}) or {}
        did = get_danbooru_id(data)
        if did:
            return sim, did, data
    return None


def _norm_tag(name):
    return name.strip().replace(" ", "_").replace("/", "_")


def tags_from_saucenao(data):
    """
    SauceNAO 的 Danbooru 条目自带标签字段,格式是 Danbooru 标签把下划线换成空格、逗号分隔:
      characters: 'magus (zenless zone zero), orphie magnusson'
      material:   'zenless zone zero'
      creator:    'hashibiro kou (garapiko p)'(部分索引是 list)
    空格换回下划线即与 Danbooru/camie 标签一致。
    """
    out = []
    for field, prefix in (("characters", "character"), ("material", "copyright"), ("creator", "artist")):
        v = data.get(field)
        if not v:
            continue
        items = v if isinstance(v, list) else str(v).split(",")
        for it in items:
            t = _norm_tag(str(it))
            if t:
                out.append(f"{prefix}/{t}")
    return out


def fetch_danbooru_tags(post_id):
    url = f"https://danbooru.donmai.us/posts/{post_id}.json"
    resp = requests.get(url, headers={"User-Agent": DANBOORU_UA}, timeout=DANBOORU_TIMEOUT)
    if resp.status_code == 403 and resp.headers.get("cf-mitigated") == "challenge":
        raise RuntimeError("403 Cloudflare challenge")
    resp.raise_for_status()
    post = resp.json()
    out = []
    for c in post.get("tag_string_character", "").split():
        out.append(f"character/{c.replace('/', '_')}")
    for c in post.get("tag_string_copyright", "").split():
        out.append(f"copyright/{c.replace('/', '_')}")
    for a in post.get("tag_string_artist", "").split():
        out.append(f"artist/{a.replace('/', '_')}")
    return out


class DanbooruBreaker:
    """连续失败计数;达到上限后本次运行跳过 Danbooru 请求"""

    def __init__(self, limit):
        self.limit = limit
        self.fails = 0
        self.last_err = ""

    @property
    def open(self):
        return self.fails >= self.limit

    def ok(self):
        self.fails = 0

    def fail(self, e):
        self.fails += 1
        self.last_err = str(e)[:80]
        if self.fails == self.limit:
            print(f"  [熔断] Danbooru 连续失败 {self.limit} 次(最近: {self.last_err}),"
                  f"本次运行不再请求 Danbooru,命中改用 SauceNAO 字段兜底。")

    def fetch(self, post_id):
        """成功返回标签列表;失败或已熔断返回 None"""
        if self.open:
            return None
        try:
            tags = fetch_danbooru_tags(post_id)
        except Exception as e:
            self.fail(e)
            return None
        self.ok()
        return tags


def chars_of(taglist):
    return [t for t in taglist if t.startswith("character/")]


def retry_pending(prog, pending, breaker):
    """重试待回查清单(只请求 Danbooru,不花 SauceNAO 配额)"""
    if not pending:
        return 0
    print(f"重试 Danbooru 待回查: {len(pending)} 条")
    fixed = 0
    for img in list(pending):
        if breaker.open:
            print(f"  已熔断,剩余 {len(pending)} 条下次再试。")
            break
        info = pending[img]
        if not os.path.exists(img):
            continue
        taglist = breaker.fetch(info["danbooru_id"])
        if taglist is None:
            continue
        res = write_sidecar_taglist(img, taglist) if taglist else "NO_TAGS"
        if res.startswith("ERR"):
            print(f"  写 sidecar 失败,保留待重试: {os.path.basename(img)} {res}")
            continue
        prog[img] = f"hit:{info['sim']:.0f}%:{','.join(chars_of(taglist))}"
        del pending[img]
        save_json(PROGRESS, prog)
        save_json(PENDING, pending)
        fixed += 1
        print(f"  补回 Danbooru 规范标签  {os.path.basename(img)}  -> {chars_of(taglist) or taglist}  [{res}]")
        time.sleep(DANBOORU_RETRY_INTERVAL)
    print(f"待回查补回 {fixed} 条,剩余 {len(pending)} 条")
    return fixed


def is_camera_photo(path):
    """EXIF 里有相机厂商/型号(Make=271, Model=272) 视为相机实拍。读取失败按非实拍处理（照常查）。"""
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            return bool(exif.get(271) or exif.get(272))
    except Exception:
        return False


def priority_of(path):
    p = path.replace("\\", "/")
    for pattern, tier in PRIORITY:
        if re.match(pattern, p, re.I):
            return tier
    return DEFAULT_PRIORITY


def prioritize(todo):
    """按 PRIORITY 排序(同档保持原顺序);返回 (排好的列表, 各档数量, 不搜的数量)"""
    tiers = [(priority_of(p), i, p) for i, p in enumerate(todo)]
    keep = sorted((t, i, p) for t, i, p in tiers if t is not None)
    counts = {}
    for t, _, _ in keep:
        counts[t] = counts.get(t, 0) + 1
    return [p for _, _, p in keep], counts, sum(t is None for t, _, _ in tiers)


def main():
    if not os.path.exists(CANDIDATES):
        raise SystemExit(f"找不到 {CANDIDATES},先跑 char_stats.py")
    with open(CANDIDATES, encoding="utf-8") as f:
        imgs = [l.strip() for l in f if l.strip()]
    prog = load_json(PROGRESS)
    pending = load_json(PENDING)
    breaker = DanbooruBreaker(DANBOORU_FAIL_LIMIT)

    retry_pending(prog, pending, breaker)

    todo = [p for p in imgs if p not in prog and os.path.exists(p)]
    # 相机实拍的照片（手机备份里的生活照）SauceNAO 不可能命中，跳过以免浪费每日配额。
    # App 里保存的图（小黑盒/QQ/B站等）没有相机信息，照常查。记进 progress，以后不再重复判断。
    skipped = [p for p in todo if is_camera_photo(p)]
    if skipped:
        for p in skipped:
            prog[p] = "skip_camera"
        save_json(PROGRESS, prog)
        todo = [p for p in todo if p not in set(skipped)]
        print(f"跳过相机实拍照片 {len(skipped)} 张")
    if PRIORITY:
        todo, counts, low = prioritize(todo)
        print("按优先级: " + "  ".join(f"第{t}档 {n}" for t, n in sorted(counts.items()))
              + f"  不搜(画册/AI 图等) {low}")
    print(f"候选 {len(imgs)}  已处理 {len(prog)}  本次待处理 {len(todo)}")
    if not todo:
        print("全部处理完毕。")
        return

    done = hit = hit_sn = hit_wait = miss = 0
    t0 = time.time()

    for img in todo:
        if done >= DAILY_CAP:
            print(f"\n已达今日上限 {DAILY_CAP},停止。明天再跑续跑。")
            break
        try:
            header, results = saucenao_search_retry(img)
        except Exception as e:
            print(f"\nSauceNAO 请求失败(已重试 {SAUCENAO_RETRIES} 次): {redact(e)}\n停止保住进度,稍后再续。")
            break

        status = header.get("status", 0)
        if status != 0:
            print(f"\nSauceNAO header.status={status}(异常),停止。稍后再续。")
            break

        m = best_danbooru_match(results)
        if m:
            sim, did, data = m
            taglist = breaker.fetch(did)
            if taglist is not None:
                res = write_sidecar_taglist(img, taglist) if taglist else "NO_TAGS"
                prog[img] = f"hit:{sim:.0f}%:{','.join(chars_of(taglist))}"
                hit += 1
                print(f"  HIT {sim:.0f}%  {os.path.basename(img)}  -> {chars_of(taglist) or taglist}  [{res}]")
            else:
                pending[img] = {"danbooru_id": did, "sim": sim}
                sn_tags = tags_from_saucenao(data)
                if sn_tags:
                    res = write_sidecar_taglist(img, sn_tags)
                    prog[img] = f"hit_sn:{sim:.0f}%:{','.join(chars_of(sn_tags))}"
                    hit_sn += 1
                    print(f"  HIT {sim:.0f}%(SauceNAO 兜底,Danbooru 待重试)  {os.path.basename(img)}"
                          f"  -> {chars_of(sn_tags) or sn_tags}  [{res}]")
                else:
                    prog[img] = f"hit_pending_danbooru:{sim:.0f}%"
                    hit_wait += 1
                    print(f"  HIT {sim:.0f}%  {os.path.basename(img)}  SauceNAO 无标签字段,Danbooru 待重试")
                save_json(PENDING, pending)
        else:
            miss += 1
            prog[img] = "miss"

        save_json(PROGRESS, prog)
        done += 1

        lr = header.get("long_remaining")
        if lr is not None and lr <= LONG_MARGIN:
            print(f"\n日配额将尽(long_remaining={lr}),停止。明天再续。")
            break

        if done % 10 == 0:
            print(f"  ...{done} 处理  hit={hit} hit_sn={hit_sn} wait={hit_wait} miss={miss}  "
                  f"(short_rem={header.get('short_remaining','?')} long_rem={lr})")
        time.sleep(INTERVAL)

    print("\n" + "=" * 50)
    print(f"本次:处理 {done}  Danbooru命中 {hit}  SauceNAO兜底 {hit_sn}  仅待回查 {hit_wait}  "
          f"未命中 {miss}  耗时 {time.time()-t0:.0f}s")
    print(f"累计已处理 {len(prog)} / {len(imgs)}  Danbooru 待回查 {len(pending)}")
    if hit or hit_sn:
        print("有新命中。去 immich 跑「边车元数据→发现」导入补的角色标签。")
    if len(prog) < len(imgs):
        print("没跑完。明天再跑同一条命令,自动续跑。")


if __name__ == "__main__":
    main()
