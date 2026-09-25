#!/usr/bin/env python3
"""
打包 Podsum.app —— SwiftUI 界面 + 内嵌后端，并做成可分发的 DMG。

产物：
    macos-client/dist/Podsum.app
    macos-client/dist/Podsum-<版本>-arm64.dmg      （--no-dmg 时不出）

内嵌什么：
    Contents/Resources/backend/{backend,prompts,scripts}   后端源码与提示词
    Contents/Resources/backend/vendor/                     Python 依赖
    Contents/Resources/python/                             Python 运行时（可选）
    Contents/Resources/bin/{ffmpeg,ffprobe,deno}           外部可执行文件，放在子进程 PATH 最前面
    Contents/Resources/licenses/                           随包二进制的许可证声明

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
    python3 macos-client/package.py --no-dmg          # 只出 .app

只支持 Apple Silicon：内嵌的 CPython、ffmpeg、deno 都只取 arm64。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"
BUILD = HERE / "build"
CACHE = BUILD / "downloads"

# python-build-standalone：一个可重定位的 CPython，解压即用。
# 固定版本，好让同一次提交打出来的包是同一个运行时。
PBS_TAG = "20250818"
PBS_VERSION = "3.12.11"
PBS_URL = (
    f"https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_TAG}/"
    f"cpython-{PBS_VERSION}+{PBS_TAG}-aarch64-apple-darwin-install_only.tar.gz"
)

# 静态编译的 ffmpeg / ffprobe（只链系统库，Developer ID 签名）。
# 固定到一个正式版本并核对 sha256——换版本时这三行一起改。
FFMPEG_VERSION = "9.0.2"
FFMPEG_BASE = "https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2"
FFMPEG_SHA256 = {
    "ffmpeg": "c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924",
    "ffprobe": "fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6",
}

# yt-dlp 的 [default] 带上本地 yt_dlp_ejs（不必每次去 GitHub 拉 YouTube 的解题组件），
# [deno] 从 PyPI 装 deno 可执行文件——YouTube 的 JS 挑战要一个 JS 运行时，
# 没有的话 yt-dlp 会警告"已弃用、可能缺格式"。
YTDLP_REQUIREMENT = "yt-dlp[default,deno]"


def run(cmd: list[str], **kwargs) -> None:
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kwargs)


def read_version() -> tuple[str, str]:
    version = (ROOT / "VERSION").read_text().strip()
    build = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return version, build


def build_app(version: str, build: str) -> Path:
    print(f"1. 编译 Release（{version} build {build}）")
    run([
        "xcodebuild", "-project", str(HERE / "Podsum.xcodeproj"),
        "-scheme", "Podsum", "-configuration", "Release",
        "-derivedDataPath", str(BUILD),
        "ARCHS=arm64",
        f"MARKETING_VERSION={version}",
        f"CURRENT_PROJECT_VERSION={build}",
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
        "tests", "node_modules", ".venv", "*.egg-info",
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


def download(url: str, sha256: str | None = None) -> Path:
    """下到 build/downloads/ 缓存；给了 sha256 就核对，对不上直接退出。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / url.rsplit("/", 1)[-1]
    if not target.exists():
        print("   下载", url)
        # ffmpeg 的下载站对 urllib 默认的 User-Agent 回 403
        request = urllib.request.Request(url, headers={"User-Agent": "podsum-package/1.0"})
        partial = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(request) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.rename(target)
    if sha256 is not None:
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != sha256:
            target.unlink()
            sys.exit(f"{target.name} 的 sha256 不符：期望 {sha256}，实际 {actual}")
    return target


def fetch_runtime(app: Path) -> Path:
    print("4. 可重定位的 CPython")
    target = app / "Contents/Resources/python"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    archive = download(PBS_URL)
    with tarfile.open(archive) as tar:
        tar.extractall(target.parent, filter="data")
    # 包里顶层目录叫 python/
    if not (target / "bin/python3").exists():
        sys.exit(f"解压后没找到 {target}/bin/python3")
    return target / "bin/python3"


def fetch_ffmpeg(app: Path) -> None:
    print(f"5. ffmpeg / ffprobe {FFMPEG_VERSION}")
    bin_dir = app / "Contents/Resources/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, sha in FFMPEG_SHA256.items():
        archive = download(f"{FFMPEG_BASE}/{name}.zip", sha)
        with zipfile.ZipFile(archive) as zf:
            zf.extract(name, bin_dir)
        (bin_dir / name).chmod(0o755)

    licenses = app / "Contents/Resources/licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    (licenses / "FFmpeg.txt").write_text(
        f"Podsum.app/Contents/Resources/bin/ffmpeg 与 ffprobe 是 FFmpeg {FFMPEG_VERSION} 的\n"
        "静态编译版，以独立可执行文件的形式随包分发，Podsum 通过子进程调用它们。\n\n"
        "FFmpeg is licensed under the GNU General Public License, version 3 or later\n"
        "(this build is configured with --enable-gpl --enable-version3).\n\n"
        f"Binaries:       {FFMPEG_BASE}/\n"
        "Build scripts:  https://git.martin-riedl.de/ffmpeg/build-script\n"
        f"FFmpeg source:  https://ffmpeg.org/releases/ffmpeg-{FFMPEG_VERSION}.tar.xz\n"
        "License text:   https://www.gnu.org/licenses/gpl-3.0.txt\n"
    )


def install_deps(app: Path, resources: Path, python: Path) -> None:
    print(f"6. 用 {python} 装依赖到 vendor/")
    vendor = resources / "vendor"
    if vendor.exists():
        shutil.rmtree(vendor)
    run([
        str(python), "-m", "pip", "install",
        "--target", str(vendor),
        "--disable-pip-version-check", "--no-input",
        str(resources / "backend"), YTDLP_REQUIREMENT,
    ], stdout=subprocess.DEVNULL)

    # 只留依赖，podsum 本身从源码那份走（PYTHONPATH 里 backend/src 在前）。
    # 两份 podsum 并存会咬人：json_export 的 schema 路径是从包所在位置
    # 往上数四层算的，装进 vendor 的那份算出来的位置根本没有 specs/。
    for leftover in list(vendor.glob("podsum")) + list(vendor.glob("podsum-*.dist-info")):
        shutil.rmtree(leftover)

    # pip --target 把各包的命令行入口放进 vendor/bin/。其中只有 deno 是真的可执行文件，
    # 挪到 Resources/bin 跟 ffmpeg 放一起；其余是 shebang 指向打包机解释器的脚本，没用。
    scripts = vendor / "bin"
    deno = scripts / "deno"
    if not deno.is_file():
        sys.exit("vendor/bin/deno 不存在——deno wheel 没装上？")
    bin_dir = app / "Contents/Resources/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(deno, bin_dir / "deno")
    shutil.rmtree(scripts)


def self_check(app: Path, resources: Path, python: Path) -> None:
    """用目标解释器 + 子进程将要拿到的 PATH，真的跑一遍，不联网。

    带编译扩展的包版本不匹配、ffmpeg 缺编码器、deno 找不到——这些都在这里
    就报错，而不是等用户双击 app 之后看一段 traceback。
    """
    print("7. 自检")
    bin_dir = app / "Contents/Resources/bin"
    env = {
        # 与 BackendController 拼的一致：Resources/bin 在前，之后只有系统目录，
        # 模拟一台没装 Homebrew 的 Mac。
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONPATH": f"{resources / 'backend/src'}:{resources / 'vendor'}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": os.environ["HOME"],
        "LANG": "en_US.UTF-8",
    }
    script = r"""
import asyncio, shutil, sys, tempfile
from pathlib import Path

import fastapi, uvicorn, pydantic_core, sqlalchemy, yt_dlp, yt_dlp_ejs, podsum.main
from podsum.services import ingest
from yt_dlp.utils._jsruntime import DenoJsRuntime
from yt_dlp.version import __version__ as ytdlp_version

bin_dir = Path(sys.argv[1])
for tool in ("ffmpeg", "ffprobe", "deno"):
    found = shutil.which(tool)
    assert found and Path(found).parent == bin_dir, f"{tool} 没从 Resources/bin 找到：{found}"

deno = DenoJsRuntime().info
assert deno is not None, "yt-dlp 找不到 deno"

async def transcode():
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "tone.m4a", Path(tmp) / "out.mp3"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:a", "aac", str(src))
        assert await proc.wait() == 0, "ffmpeg 生成测试音频失败"
        await ingest._run_ffmpeg_normalize(src, out)
        return await ingest._probe_duration_seconds(out)

seconds = asyncio.run(transcode())
assert seconds == 3, f"转码后时长 {seconds}s，期望 3s"
print(f"  ✓ 后端可导入；yt-dlp {ytdlp_version}，deno {deno.version}；转码 + 探测时长正常")
"""
    print("  $", python, "-c <自检脚本>")
    subprocess.run([str(python), "-c", script, str(bin_dir)], env=env, check=True)


def precompile(app: Path, python: Path) -> None:
    """预先生成字节码，运行期不再往 bundle 里写。

    否则解释器首次 import 时会在 .app 里落下成百上千个 __pycache__，
    签名随之失效（codesign --verify 报 sealed resource missing or invalid）。
    unchecked-hash：解释器直接用 .pyc，不再拿源文件 mtime 去比、也就不会想着重写。
    """
    print("8. 预编译字节码")
    targets = [app / "Contents/Resources/backend"]
    runtime_lib = app / "Contents/Resources/python/lib"
    if runtime_lib.exists():
        targets.append(runtime_lib)
    # 个别第三方包里带着故意写坏的测试文件，编不过属正常，不因此中断
    subprocess.run([
        str(python), "-m", "compileall", "-q", "-j", "0",
        "--invalidation-mode", "unchecked-hash",
        *map(str, targets),
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sign(app: Path) -> None:
    print("9. 临时签名")
    # 往 bundle 里塞了东西，原来的签名就失效了，必须重签。
    # 用 ad-hoc（"-"）：没有 Developer ID，首次打开需要用户在系统设置里放行（见 INSTALL.md）。
    run(["codesign", "--force", "--deep", "--sign", "-", str(app)],
        stderr=subprocess.DEVNULL)
    result = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"签名自检失败：\n{result.stderr}")
    print("  ✓ codesign --verify --deep --strict 通过")


def make_dmg(app: Path, version: str) -> Path:
    print("10. 做 DMG")
    dmg = DIST / f"Podsum-{version}-arm64.dmg"
    if dmg.exists():
        dmg.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "Podsum"
        staging.mkdir()
        # ditto 保留扩展属性与签名，比 copytree 稳妥
        run(["ditto", str(app), str(staging / "Podsum.app")])
        (staging / "Applications").symlink_to("/Applications")
        shutil.copy(ROOT / "INSTALL.md", staging / "安装说明 Install.txt")
        run([
            "hdiutil", "create", "-volname", f"Podsum {version}",
            "-srcfolder", str(staging), "-fs", "HFS+", "-format", "ULFO",
            "-ov", str(dmg),
        ], stdout=subprocess.DEVNULL)
    return dmg


def main() -> None:
    parser = argparse.ArgumentParser(description="打包 Podsum.app")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--with-runtime", action="store_true",
                       help="下载并内嵌 CPython（默认）")
    group.add_argument("--python", metavar="PATH",
                       help="改用本机这个解释器装依赖，不内嵌运行时")
    parser.add_argument("--skip-build", action="store_true",
                        help="复用上次的 Release 产物")
    parser.add_argument("--no-dmg", action="store_true",
                        help="只出 .app，不做 DMG")
    args = parser.parse_args()

    if platform.machine() != "arm64":
        sys.exit("只支持在 Apple Silicon 上打包：内嵌的运行时、ffmpeg、deno 都只取 arm64。")

    version, build = read_version()
    built = (BUILD / "Build/Products/Release/Podsum.app") if args.skip_build else build_app(version, build)
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

    fetch_ffmpeg(app)
    install_deps(app, resources, python)
    self_check(app, resources, python)
    precompile(app, python)
    sign(app)

    size = sum(f.stat().st_size for f in app.rglob("*") if f.is_file()) / 1e6
    print(f"\n✓ {app}  {size:.0f} MB  （{version} build {build}）")
    if not args.no_dmg:
        dmg = make_dmg(app, version)
        print(f"✓ {dmg}  {dmg.stat().st_size / 1e6:.0f} MB")
    print("  拖进「应用程序」即可。首次启动去「设置 › 接口」填自己的 API。")


if __name__ == "__main__":
    main()
