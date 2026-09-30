# -*- coding: utf-8 -*-
"""
daily.bat 用:运行一条命令,输出同时实时显示在 cmd 窗口 + 追加到日志文件(UTF-8)。
cmd 没有 tee;直接 >>log 会让窗口一片空白,看不出在跑还是卡死。
退出码 = 被运行命令的退出码。
用法:python tee_run.py <日志文件> <命令> [参数...]
"""
import sys
import subprocess


def main():
    if len(sys.argv) < 3:
        raise SystemExit("用法: python tee_run.py <日志文件> <命令> [参数...]")
    log, cmd = sys.argv[1], sys.argv[2:]
    with open(log, "a", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for raw in p.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            print(line, flush=True)
            f.write(line + "\n")
            f.flush()
        return p.wait()


if __name__ == "__main__":
    sys.exit(main())
