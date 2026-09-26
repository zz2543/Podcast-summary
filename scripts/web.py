#!/usr/bin/env python3
"""
网页版的安装与启动器，macOS / Windows / Linux 通用。只用标准库。

    python scripts/web.py install   # 建 .venv、装后端和 frontend-v2 的依赖、生成 .env
    python scripts/web.py           # 启动后端 (8000) + 网页 (5174) 并打开浏览器；Ctrl+C 一并停止

双击用的包装：start-web.command（macOS）、start-web.bat（Windows）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend-v2"
VENV = ROOT / ".venv"
IS_WINDOWS = os.name == "nt"
VENV_PYTHON = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")

HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 5174  # frontend-v2/vite.config.ts 里写死的端口（strictPort）
URL = f"http://{HOST}:{FRONTEND_PORT}"


def say(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    say(f"✗ {msg}")
    sys.exit(1)


def npm() -> str:
    # Windows 上 npm 是 npm.cmd，subprocess 不会自己补后缀
    found = shutil.which("npm")
    if not found:
        fail("找不到 npm。请先安装 Node.js 20 或更新版本：https://nodejs.org")
    return found


def backend_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend" / "src")
    env["PYTHONUTF8"] = "1"  # Windows 控制台默认 GBK，日志里的中文会乱码或报错
    return env


def check_media_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if not shutil.which(tool)]
    if missing:
        hint = "winget install Gyan.FFmpeg" if IS_WINDOWS else "brew install ffmpeg"
        say(f"! 没找到 {' / '.join(missing)}：转码和读时长要用它。安装后重开终端：{hint}")
    if not shutil.which("deno"):
        hint = "winget install DenoLand.Deno" if IS_WINDOWS else "brew install deno"
        say(f"! 没找到 deno：YouTube 视频可能下载失败（yt-dlp 需要它处理网页脚本）。建议安装：{hint}")


def install() -> None:
    if sys.version_info < (3, 11):
        fail(f"需要 Python 3.11 或更新版本，当前是 {sys.version.split()[0]}。")
    npm_path = npm()

    if not VENV_PYTHON.exists():
        say("1. 创建虚拟环境 .venv")
        venv.create(VENV, with_pip=True)
    else:
        say("1. 已有虚拟环境 .venv")

    say("2. 安装后端依赖")
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"], cwd=ROOT, check=True)
    # --upgrade 让重跑 install 顺带把 yt-dlp 升到最新：视频站改版后旧版会下载失败
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "-e", "backend", "yt-dlp[default]"],
                   cwd=ROOT, check=True)

    say("3. 安装网页依赖（frontend-v2）")
    subprocess.run([npm_path, "--prefix", str(FRONTEND), "install"], cwd=ROOT, check=True)

    env_file = ROOT / ".env"
    if not env_file.exists():
        shutil.copyfile(ROOT / ".env.example", env_file)
        say("4. 已从 .env.example 生成 .env")
    else:
        say("4. 已有 .env，保持不动")

    check_media_tools()
    say("")
    say("✓ 安装完成。下一步：")
    say(f"  1) 编辑 {env_file}，把 replace-me-* 换成你自己的 API Key（见 README「网页版」一节）")
    say("  2) 启动：python scripts/web.py（或双击 start-web.command / start-web.bat）")


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((HOST, port)) == 0


def spawn(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.Popen:
    kwargs: dict = {"cwd": ROOT, "env": env}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        # npm.cmd 底下还挂着 node，只杀外层会留下孤儿进程占着端口
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def start() -> None:
    if not VENV_PYTHON.exists() or not (FRONTEND / "node_modules").exists():
        fail("还没安装依赖。先运行：python scripts/web.py install")
    if not (ROOT / ".env").exists():
        fail("缺少 .env。先运行：python scripts/web.py install，再填好里面的 API Key")

    if port_open(BACKEND_PORT) and port_open(FRONTEND_PORT):
        say(f"服务已经在运行，直接打开 {URL}")
        webbrowser.open(URL)
        return
    for port in (BACKEND_PORT, FRONTEND_PORT):
        if port_open(port):
            fail(f"端口 {port} 被别的程序占用了，关掉它再试。")

    check_media_tools()
    say("初始化数据库…")
    subprocess.run([str(VENV_PYTHON), "scripts/init_db.py"], cwd=ROOT, env=backend_env(), check=True)

    # 不加 --reload：Windows 上开了 reload，uvicorn 会换成不支持子进程的事件循环，调 ffmpeg 会失败
    say(f"启动后端 http://{HOST}:{BACKEND_PORT}")
    backend = spawn([str(VENV_PYTHON), "-m", "uvicorn", "podsum.main:app",
                     "--host", HOST, "--port", str(BACKEND_PORT)], env=backend_env())
    say(f"启动网页 {URL}")
    frontend = spawn([npm(), "--prefix", str(FRONTEND), "run", "dev", "--",
                      "--host", HOST, "--port", str(FRONTEND_PORT)])

    procs = [backend, frontend]

    # 子进程在各自的进程组里，收不到终端的信号：关窗口（SIGHUP）或被 kill（SIGTERM）
    # 时要由这里转成 Ctrl+C 的收尾，否则两个服务会留在后台占着端口
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), interrupt)

    try:
        deadline = time.monotonic() + 90
        while not (port_open(BACKEND_PORT) and port_open(FRONTEND_PORT)):
            if any(p.poll() is not None for p in procs):
                fail("有服务启动失败，看上面的报错（多半是 .env 里的配置不对）。")
            if time.monotonic() > deadline:
                fail("等了 90 秒服务还没起来，看上面的输出排查。")
            time.sleep(0.5)
        webbrowser.open(URL)
        say("")
        say(f"✓ 已启动：{URL}")
        say("  关掉这个窗口或按 Ctrl+C 就会停止服务。")
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        say("有服务意外退出了，正在停止其余服务。")
    except KeyboardInterrupt:
        say("\n正在停止…")
    finally:
        for p in procs:
            stop(p)


def main() -> None:
    parser = argparse.ArgumentParser(description="懂听网页版：安装与启动")
    parser.add_argument("command", nargs="?", default="start", choices=["install", "start"])
    args = parser.parse_args()
    os.chdir(ROOT)  # 后端按相对路径读 .env 和 data/
    install() if args.command == "install" else start()


if __name__ == "__main__":
    main()
