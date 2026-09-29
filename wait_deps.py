# -*- coding: utf-8 -*-
"""
daily.bat 开跑前等依赖就绪:immich(Docker)+ 网络/代理(访问 SauceNAO,仅配置了 Tier 0 时检查)。
开机/登录后 Docker、代理客户端启动慢,不等就会全失败,且当天会被误记为已跑。

每 INTERVAL 秒检查一次,最多等 MAX_WAIT 秒。
退出码:0=都就绪  1=超时仍有未就绪(daily.bat 据此不写"今天已跑过",下次触发重试)
用法:python wait_deps.py [最多等待秒数]
"""
import sys
import time
import requests

from config import IMMICH_URL, SAUCENAO_API_KEY

IMMICH_PING = IMMICH_URL.rstrip("/") + "/api/server/ping"
NET_PROBE = "https://saucenao.com/"   # requests 自动走系统代理
CHECK_NET = bool(SAUCENAO_API_KEY)    # 不用 Tier 0 就不检查外网
INTERVAL = 30
MAX_WAIT = int(sys.argv[1]) if len(sys.argv) > 1 else 1200


def immich_ok():
    try:
        r = requests.get(IMMICH_PING, timeout=5, proxies={"http": None, "https": None})
        return r.ok and r.json().get("res") == "pong"
    except Exception:
        return False


def net_ok():
    if not CHECK_NET:
        return True
    try:
        r = requests.head(NET_PROBE, timeout=10)
        return r.status_code < 500
    except Exception:
        return False


def main():
    t0 = time.time()
    while True:
        im, nt = immich_ok(), net_ok()
        waited = int(time.time() - t0)
        status = f"immich={'OK' if im else '未就绪'}  网络/代理={'OK' if nt else '未就绪'}"
        if im and nt:
            print(f"[deps] {status}(等待 {waited}s)")
            return 0
        if waited >= MAX_WAIT:
            print(f"[deps] 等待 {waited}s 超时:{status}。本次不运行,下次触发重试。")
            return 1
        print(f"[deps] 等待中 {waited}s:{status}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
