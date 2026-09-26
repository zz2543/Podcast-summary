#!/usr/bin/env python3
"""
打包发布版「懂听 / GotIt」—— SwiftUI 界面 + 内嵌后端，并做成可分发的 DMG。
源码、Xcode target 仍叫 Podsum；发行名只在这里落到 bundle 上。

产物（名字取自下面的 APP_NAME）：
    macos-client/dist/GotIt.app                     （中文系统的 Finder / 启动台里显示「懂听」）
    macos-client/dist/GotIt-<版本>-arm64.dmg        （--no-dmg 时不出）

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

# 发行名与 bundle id。APP_NAME 是 .app / DMG 的文件名，也是英文界面的名字；
# 中文界面叫 APP_NAME_ZH（本地化的 InfoPlist.strings）。两者与 Swift 里的 AppBrand 一致。
# 发布版用独立的 bundle id：钥匙串、Application Support（…/GotIt）、日志、偏好设置
# 都按 bundle id 隔离（见 AppStorageRoot），不会读到开发版 local.podsum.macclient 的凭据。
APP_NAME = "GotIt"
APP_NAME_ZH = "懂听"
BUNDLE_ID = "local.gotit.mac"   # 与 AppStorageRoot.releaseBundleID 一致
CACHE = BUILD / "downloads"
# xcodebuild 的中间产物是没装后端的半成品 app，和成品同一个 bundle id。
# 放进 .noindex 目录，Spotlight/启动台就不会把它列出来让人误点。
DERIVED = BUILD / "DerivedData.noindex"
BUILT_APP = DERIVED / "Build/Products/Release/Podsum.app"
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
              "LaunchServices.framework/Support/lsregister")

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

# 火山引擎 SDK 里后端真正 import 的包；自检会导入它们，漏了当场报错
VOLC_KEEP = {"volcenginesdkcore", "volcenginesdkspeechsaasprod"}

# 从内嵌 CPython 里删掉的部分（相对 Resources/python 的 glob）
RUNTIME_DROP = [
    "include", "share",
    "lib/python3.12/idlelib", "lib/python3.12/tkinter", "lib/python3.12/turtledemo",
    "lib/python3.12/ensurepip", "lib/python3.12/lib2to3", "lib/python3.12/pydoc_data",
    "lib/python3.12/lib-dynload/_tkinter.*",
    "lib/tcl8*", "lib/tk8*", "lib/itcl*", "lib/thread2*", "lib/libtcl*", "lib/libtk*",
]


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
        "-derivedDataPath", str(DERIVED),
        "ARCHS=arm64",
        f"PRODUCT_BUNDLE_IDENTIFIER={BUNDLE_ID}",
        f"MARKETING_VERSION={version}",
        f"CURRENT_PROJECT_VERSION={build}",
        "build",
    ], stdout=subprocess.DEVNULL)
    if not BUILT_APP.exists():
        sys.exit(f"编译产物不在预期位置：{BUILT_APP}")
    return BUILT_APP


def unregister(app: Path) -> None:
    """从 LaunchServices 注销，按 bundle id 启动时就不会挑中这一份。"""
    subprocess.run([LSREGISTER, "-u", str(app)], capture_output=True)


def drop_legacy_build() -> None:
    """早先 derivedDataPath 直接是 build/，那份半成品 app 还在被 Spotlight 收录。"""
    legacy = BUILD / "Build"
    if legacy.exists():
        for app in legacy.glob("Products/*/Podsum.app"):
            unregister(app)
        shutil.rmtree(legacy)
    for name in ("CompilationCache.noindex", "ModuleCache.noindex", "SDKExplicitPrecompiledModules",
                 "SDKStatCaches.noindex", "Logs", "info.plist"):
        path = BUILD / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def stage(built: Path) -> Path:
    print("2. 放到 dist/")
    DIST.mkdir(exist_ok=True)
    target = DIST / f"{APP_NAME}.app"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(built, target, symlinks=True)
    # 可执行文件、模块名仍是 Podsum；只改 Finder / 启动台 / 菜单栏 / 权限弹窗里显示的名字
    plist = target / "Contents/Info.plist"
    for key in ("CFBundleName", "CFBundleDisplayName"):
        subprocess.run(["plutil", "-replace", key, "-string", APP_NAME, str(plist)], check=True)
    # 有了这个键 Finder 才去读 lproj 里的 CFBundleDisplayName，否则一律显示文件名
    subprocess.run(["plutil", "-replace", "LSHasLocalizedDisplayName", "-bool", "YES", str(plist)],
                   check=True)
    localized = {
        "zh-Hans": (APP_NAME_ZH, "懂听读取当前标签页的地址，把你正在看的视频送去总结。"),
        "en": (APP_NAME, "GotIt reads the current tab’s address to summarize the video you’re watching."),
    }
    for lang, (name, apple_events) in localized.items():
        lproj = target / f"Contents/Resources/{lang}.lproj"
        lproj.mkdir(parents=True, exist_ok=True)
        (lproj / "InfoPlist.strings").write_text(
            f'"CFBundleName" = "{name}";\n'
            f'"CFBundleDisplayName" = "{name}";\n'
            f'"NSAppleEventsUsageDescription" = "{apple_events}";\n',
            encoding="utf-16",
        )
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

    # 后端用不到的部分：GUI（Tk）、IDLE、2to3、离线帮助、C 头文件。
    # pip 要留着——「解析组件 › 检查并更新」在运行时用它装新版 yt-dlp。
    for rel in RUNTIME_DROP:
        for path in target.glob(rel):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
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
        f"{APP_NAME}.app/Contents/Resources/bin/ffmpeg 与 ffprobe 是 FFmpeg {FFMPEG_VERSION} 的\n"
        f"静态编译版，以独立可执行文件的形式随包分发，{APP_NAME_ZH}（{APP_NAME}）通过子进程调用它们。\n\n"
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
        "--disable-pip-version-check", "--no-input", "--no-compile",
        str(resources / "backend"), YTDLP_REQUIREMENT,
    ], stdout=subprocess.DEVNULL)

    # 只留依赖，podsum 本身从源码那份走（PYTHONPATH 里 backend/src 在前）。
    # 两份 podsum 并存会咬人：json_export 的 schema 路径是从包所在位置
    # 往上数四层算的，装进 vendor 的那份算出来的位置根本没有 specs/。
    for leftover in list(vendor.glob("podsum")) + list(vendor.glob("podsum-*.dist-info")):
        shutil.rmtree(leftover)

    # volcengine-python-sdk 是火山引擎全部云服务的客户端（139 个包、预编译后 500+ MB），
    # 后端只用语音这一个（asr_client._build_volcengine_speech_api）。其余整包删掉。
    for pkg in vendor.glob("volcenginesdk*"):
        if pkg.name not in VOLC_KEEP:
            shutil.rmtree(pkg)

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
import pip  # 「检查并更新」解析组件要用
from podsum.services import ingest
from yt_dlp.utils._jsruntime import DenoJsRuntime
from yt_dlp.version import __version__ as ytdlp_version
# 与 asr_client._build_volcengine_speech_api 的 import 一致（VOLC_KEEP 删多了这里就报错）
from volcenginesdkcore import ApiClient
from volcenginesdkcore.configuration import Configuration
from volcenginesdkspeechsaasprod import SPEECHSAASPRODApi
SPEECHSAASPRODApi(ApiClient(Configuration()))

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


def strip_bytecode(app: Path) -> None:
    """包里不带字节码。

    后端子进程设了 PYTHONPYCACHEPREFIX（见 BackendController），字节码写到
    ~/Library/Caches/<app>/pycache，既不往 bundle 里写（写了签名就坏），
    也不必把 70+ MB 的 .pyc 打进包；设了这个变量后包内的 __pycache__ 本来也不会被读。
    代价是首次启动多花几秒编译。
    """
    print("8. 清掉字节码")
    n = 0
    for cache in list((app / "Contents/Resources").rglob("__pycache__")):
        shutil.rmtree(cache)
        n += 1
    print(f"  删除 {n} 个 __pycache__")


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
    dmg = DIST / f"{APP_NAME}-{version}-arm64.dmg"
    if dmg.exists():
        dmg.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / APP_NAME
        staging.mkdir()
        # ditto 保留扩展属性与签名，比 copytree 稳妥
        run(["ditto", str(app), str(staging / app.name)])
        (staging / "Applications").symlink_to("/Applications")
        shutil.copy(ROOT / "INSTALL.md", staging / "安装说明 Install.txt")
        run([
            "hdiutil", "create", "-volname", f"{APP_NAME_ZH} {APP_NAME} {version}",
            "-srcfolder", str(staging), "-fs", "HFS+", "-format", "ULFO",
            "-ov", str(dmg),
        ], stdout=subprocess.DEVNULL)
    return dmg


def main() -> None:
    parser = argparse.ArgumentParser(description=f"打包 {APP_NAME}.app（{APP_NAME_ZH}）")
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

    drop_legacy_build()
    version, build = read_version()
    built = BUILT_APP if args.skip_build else build_app(version, build)
    if args.skip_build and not built.exists():
        sys.exit("没有可复用的 Release 产物，去掉 --skip-build")

    app = stage(built)
    unregister(built)
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
    strip_bytecode(app)
    sign(app)

    size = sum(f.stat().st_size for f in app.rglob("*") if f.is_file()) / 1e6
    print(f"\n✓ {app}  {size:.0f} MB  （{version} build {build}）")
    if not args.no_dmg:
        dmg = make_dmg(app, version)
        print(f"✓ {dmg}  {dmg.stat().st_size / 1e6:.0f} MB")
        # 出了 DMG 就该从 DMG 装到「应用程序」；dist/ 里这份不再抢 bundle id
        unregister(app)
    print("  拖进「应用程序」即可。首次启动去「设置 › 接口」填自己的 API。")


if __name__ == "__main__":
    main()
