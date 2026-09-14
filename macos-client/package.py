#!/usr/bin/env python3
"""
打包 Podsum.app —— SwiftUI 界面 + 内嵌后端。

产物：macos-client/dist/Podsum.app，双击即用，取代 ~/Applications/Podsum.app
那个 bash 启动器（它起 uvicorn + vite 再开浏览器，这里只剩一个 uvicorn 子进程）。

内嵌什么：
    Contents/Resources/backend/{backend,prompts,scripts}   后端源码与提示词
    Contents/Resources/backend/vendor/                     Python 依赖
    Contents/Resources/python/                             Python 运行时（可选）

**依赖必须用最终要跑它的那个解释器装。** pydantic-core、yt-dlp 这些带
编译扩展的包是按 CPython 版本出 wheel 的，用 3.13 装的 vendor 在 3.12 上
直接 import 失败。所以：

    --with-runtime         下载 python-build-standalone 内嵌进 app，用它装依赖
                           （唯一真正自包含的做法，装完不依赖本机装没装 Python）
    --python <解释器路径>   用本机这个解释器装依赖；app 运行时也会找到同一个

不带任何参数时默认 --with-runtime。

    python3 macos-client/package.py
    python3 macos-client/package.py --python /usr/local/bin/python3
    python3 macos-client/package.py --skip-build      # 复用上次的 Release 产物
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"
BUILD = HERE / "build"

# python-build-standalone：一个可重定位的 CPython，解压即用。
# 固定版本，好让同一次提交打出来的包是同一个运行时。
PBS_TAG = "20250818"
PBS_VERSION = "3.12.11"
PBS_URL = (
    f"https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_TAG}/"
    "cpython-{version}+{tag}-{arch}-apple-darwin-install_only.tar.gz"
)


def run(cmd: list[str], **kwargs) -> None:
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kwargs)


def build_app() -> Path:
    print("1. 编译 Release")
    run([
        "xcodebuild", "-project", str(HERE / "Podsum.xcodeproj"),
        "-scheme", "Podsum", "-configuration", "Release",
        "-derivedDataPath", str(BUILD),
        "build",
    ], stdout=subprocess.DEVNULL)
    built = BUILD / "Build/Products/Release/Podsum.app"
    if not built.exists():
        sys.exit(f"编译产物不在预期位置：{built}")
    return built


def stage(built: Path) -> Path:
    print("2. 放到 dist/")
    DIST.mkdir(exist_ok=True)
    target = DIST / "Podsum.app"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(built, target, symlinks=True)
    return target


def copy_backend(app: Path) -> Path:
    print("3. 拷后端源码")
    resources = app / "Contents/Resources/backend"
    resources.mkdir(parents=True, exist_ok=True)

    # 目录结构必须和仓库根一致：alembic.ini 写的是 backend/src/...，
    # prompt_assembler 默认的 prompt_root 是相对 cwd 的 "prompts"。
    # BackendController 把 cwd 设成这个目录，所以两者都能对上。
    ignore = shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "tests", "node_modules", ".venv",
    )
    for name in ("backend", "prompts", "scripts"):
        dest = resources / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(ROOT / name, dest, ignore=ignore)

    # json_export 在 import 时就读这份 schema，路径是相对 podsum 包往上数四层
    # 算出来的。少了它，后端连 import 都过不去。
    schema_src = ROOT / "specs/001-podcast-summary/contracts"
    schema_dest = resources / "specs/001-podcast-summary/contracts"
    if schema_dest.exists():
        shutil.rmtree(schema_dest)
    schema_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(schema_src, schema_dest, ignore=ignore)

    # 顺手确认一遍 BackendController 认这个目录（它查这两个路径）
    for probe in ("backend/src/podsum/main.py", "prompts",
                  "specs/001-podcast-summary/contracts/episode-output.schema.json"):
        if not (resources / probe).exists():
            sys.exit(f"内嵌后端缺少 {probe}")
    return resources


def fetch_runtime(app: Path) -> Path:
    print("4. 下载可重定位的 CPython")
    arch = "aarch64" if platform.machine() == "arm64" else "x86_64"
    url = PBS_URL.format(version=PBS_VERSION, tag=PBS_TAG, arch=arch)
    target = app / "Contents/Resources/python"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    print("  ", url)
    archive, _ = urllib.request.urlretrieve(url)
    with tarfile.open(archive) as tar:
        tar.extractall(target.parent, filter="data")
    # 包里顶层目录叫 python/
    if not (target / "bin/python3").exists():
        sys.exit(f"解压后没找到 {target}/bin/python3")
    os.unlink(archive)
    return target / "bin/python3"


def install_deps(resources: Path, python: Path) -> None:
    print(f"5. 用 {python} 装依赖到 vendor/")
    vendor = resources / "vendor"
    if vendor.exists():
        shutil.rmtree(vendor)
    run([
        str(python), "-m", "pip", "install",
        "--target", str(vendor),
        "--disable-pip-version-check", "--no-input",
        str(resources / "backend"),
    ], stdout=subprocess.DEVNULL)

    # 只留依赖，podsum 本身从源码那份走（PYTHONPATH 里 backend/src 在前）。
    # 两份 podsum 并存会咬人：json_export 的 schema 路径是从包所在位置
    # 往上数四层算的，装进 vendor 的那份算出来的位置根本没有 specs/。
    for leftover in list(vendor.glob("podsum")) + list(vendor.glob("podsum-*.dist-info")):
        shutil.rmtree(leftover)

    # 装完自查：用目标解释器真的 import 一遍。带编译扩展的包版本不匹配时
    # 会在这里就报错，而不是等用户双击 app 之后看一段 traceback。
    # sys.path 的顺序照抄 BackendController 拼的 PYTHONPATH：源码在前，vendor 在后
    run([
        str(python), "-c",
        "import sys; sys.path[:0] = sys.argv[1:3]; "
        "import fastapi, uvicorn, pydantic_core, sqlalchemy, yt_dlp, podsum.main; "
        "print('  ✓ 内嵌后端可导入')",
        str(resources / "backend/src"), str(vendor),
    ])


def sign(app: Path) -> None:
    print("6. 临时签名")
    # 往 bundle 里塞了东西，原来的签名就失效了，必须重签。
    # 用 ad-hoc（"-"）：本机自用不需要开发者账号。
    run(["codesign", "--force", "--deep", "--sign", "-", str(app)],
        stderr=subprocess.DEVNULL)


def main() -> None:
    parser = argparse.ArgumentParser(description="打包 Podsum.app")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--with-runtime", action="store_true",
                       help="下载并内嵌 CPython（默认）")
    group.add_argument("--python", metavar="PATH",
                       help="改用本机这个解释器装依赖，不内嵌运行时")
    parser.add_argument("--skip-build", action="store_true",
                        help="复用上次的 Release 产物")
    args = parser.parse_args()

    built = (BUILD / "Build/Products/Release/Podsum.app") if args.skip_build else build_app()
    if args.skip_build and not built.exists():
        sys.exit("没有可复用的 Release 产物，去掉 --skip-build")

    app = stage(built)
    resources = copy_backend(app)

    if args.python:
        python = Path(args.python)
        if not python.is_file():
            sys.exit(f"解释器不存在：{python}")
        print("   （不内嵌运行时：app 运行时会在本机找同一个解释器）")
    else:
        python = fetch_runtime(app)

    install_deps(resources, python)
    sign(app)

    size = sum(f.stat().st_size for f in app.rglob("*") if f.is_file()) / 1e6
    print(f"\n✓ {app}  {size:.0f} MB")
    print("  拖进「应用程序」即可。首次启动去「设置 › 接口」填自己的 API。")


if __name__ == "__main__":
    main()
