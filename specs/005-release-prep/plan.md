# 005 — 发布前准备（不含签名与公证）

**日期**：2026-09-25
**目标**：把 `macos-client/package.py` 打出来的 `Podsum.app` 变成可以交给别人的安装包——
在一台没装 Homebrew、没有 deno、没有本仓库的 Mac 上，拖进「应用程序」就能用；
并且 YouTube / B 站改接口之后，用户自己点一下就能把解析组件升到新版，不用等重新发包。

**不做**：Developer ID 签名、Hardened Runtime、公证（需要付费开发者账号，另议）。
所以产物仍是 ad-hoc 签名，首次打开要走「系统设置 › 隐私与安全性 › 仍要打开」，这件事写进安装说明。

---

## 摸底时确认的事实

| 事实 | 依据 |
|---|---|
| 003 / 004 的全部改动都还没提交 | `git status`：36 个已修改 + 30 余个未跟踪；HEAD 是 `99f2aea Checkpoint…` |
| 现有 `dist/Podsum.app` 签名已坏 | `codesign --verify`：*a sealed resource is missing or invalid*；bundle 里有 857 个运行期写入的 `__pycache__` |
| 版本号 `0.1 (1)`，写死在 `gen-project.py` | `MARKETING_VERSION = 0.1`、`CURRENT_PROJECT_VERSION = 1` |
| 只有 arm64 | `lipo -archs` → `arm64`；PBS 运行时也只下了 aarch64 |
| ffmpeg / ffprobe 靠宿主机 | `ingest.py` 的转码与时长探测、`cover.py` 的封面转码都 `subprocess` 调它们；`BackendController` 只是把 `/opt/homebrew/bin` 补进 PATH |
| **YouTube 解析还隐式依赖 deno** | yt-dlp 用 `remote_components={"ejs:github"}` 解 YouTube 的 JS 挑战，需要一个 JS 运行时；本机 `/opt/homebrew/bin/deno` 恰好有，别人的机器多半没有。**尚未实测缺 deno 时的表现**（需要连 YouTube，见「待你决定」） |
| vendor 里的 yt-dlp 没装 `[default]` extra | 缺 `yt_dlp_ejs`、`brotli`、`mutagen`、`pycryptodomex`；EJS 组件每次运行从 GitHub 现拉 |
| yt-dlp 封死在 bundle 里，用户无法升级 | vendor 版本 `2026.8.19`；研究文档记录过 7 月版对 YouTube 全部 403 |
| 后端测试全绿 | `make test` → 264 passed，domain 覆盖率 93.6% |

---

## 工作项

### A. 基线提交
把 003 / 004 现有改动作为独立提交落地，之后本计划的每一项各自一个提交，出问题好回退。
提交前跑一遍 `make test` 与 Release 编译。

### B. 字节码与签名不再被运行期改坏
- `package.py`：装完依赖后用**目标解释器**跑 `compileall --invalidation-mode unchecked-hash`，
  覆盖 `backend/src`、`vendor`、`python/lib`，再签名。`unchecked-hash` 让解释器不再按 mtime 判断重写。
- `BackendController.environment()`：加 `PYTHONDONTWRITEBYTECODE=1`，运行期不往 bundle 里写任何东西。
- 签名改为 `--deep` 之后再跑 `codesign --verify --deep --strict` 作为打包的最后一步自检，失败即退出。

**验收**：打包 → 启动（隔离环境）→ 提交 / 查询若干次 → 退出 → `codesign --verify --deep --strict` 仍通过，
bundle 内 `find -name __pycache__ -newer` 为空。

### C. 版本号
- 仓库根新增 `VERSION`（首发 `0.2.0`）。`gen-project.py` 读它写 `MARKETING_VERSION`；
  `CURRENT_PROJECT_VERSION` 用 `git rev-list --count HEAD`，单调递增。
- 「设置 › 通用」底部显示 `Podsum 0.2.0 (build N)`。
- DMG 文件名带版本与架构：`Podsum-0.2.0-arm64.dmg`。

### D. 外部依赖随包带齐 + 启动自检
1. **ffmpeg / ffprobe**：静态编译的可执行文件放进 `Contents/Resources/bin/`，
   `BackendController` 把这个目录放在 PATH **最前面**。来源见「待你决定」。
2. **JS 运行时**：vendor 改装 `yt-dlp[default,deno]`——PyPI 上的 `deno` 包自带对应平台的 deno 二进制，
   不用另外下载；`[default]` 顺带装上本地 `yt_dlp_ejs`，不再依赖每次去 GitHub 拉组件。
   打包时核对 yt-dlp 能找到这份 deno；找不到就同样放进 `Resources/bin/`。
3. **启动自检**：`resolveRuntime()` 之后检查 `ffmpeg`、`ffprobe`、`deno` 在拼好的 PATH 上都可执行；
   缺哪个就进 `.noRuntime`，界面说清楚缺什么、找过哪里（沿用现有状态机，不新增状态）。
4. `package.py` 的 import 自检扩展为：`ffmpeg -version`、`ffprobe -version`、`deno --version`、
   以及用内嵌解释器 + 内嵌 PATH 真的转码一段本地测试音频（不联网）。

**验收**：用只含 `/usr/bin:/bin:/usr/sbin:/sbin` 的 PATH 启动打包产物（模拟一台没有 Homebrew 的 Mac），
提交一个本地音频文件走完转码；自检能正确报出人为删掉的某个组件。

### E. 「更新解析组件」按钮（设置 › 服务）
**机制**：包内的 yt-dlp 只作保底；用户更新的版本装在 bundle 外面，优先加载。

- 位置：`~/Library/Application Support/Podsum/components/`。不碰 `.app`，签名不受影响，
  升级 app 时也不会被覆盖。
- `PYTHONPATH` 顺序：`backend/src` → **components** → `vendor`。
- 更新动作（新文件 `Data/ComponentUpdater.swift`）：
  1. 用后端同一个解释器执行 `pip install --upgrade --no-deps --target <临时目录> yt-dlp yt-dlp-ejs`；
     `--no-deps` 是为了只换解析器本身，不让它顺带升级 requests 之类、遮住 vendor 里经过验证的版本。
  2. 用「临时目录 + vendor」跑一次 `import yt_dlp, yt_dlp_ejs` 并读出版本号；失败则丢弃临时目录，原组件不动。
  3. 成功才原子替换 `components/`，然后提示「重启后端后生效」并提供按钮。
- 界面：一行显示「当前使用 yt-dlp 2026.x.y（内置 / 已更新）」；按钮「检查并更新」；
  已更新时多一个「恢复内置版本」（删掉 `components/`）。进行中显示进度与 pip 输出尾巴，失败给出原因。
- pip 遵循用户自己的 `pip.conf`（国内用户可能配了镜像），不强行指定索引。
- 连外部后端（`backendMode == .external`）时按钮置灰并说明原因——那种情况下解析器不归本 app 管。

**验收**：隔离环境里把 `components/` 先装一个旧版 → 界面显示旧版 → 点更新 → 显示新版并重启后端 →
后端日志 / 一个诊断端点确认加载的是 components 里的那份 → 「恢复内置版本」回退。
断网时点更新：报错、原组件不动。

### F. Intel 版（已取消，见「决定」）
- `package.py --arch x86_64|arm64`，默认本机架构；`--all` 依次打两份。
- Swift：`xcodebuild ARCHS=<arch>`；Python：下对应架构的 PBS；依赖用该解释器装（x86_64 在本机走 Rosetta，
  pip 自然拿到 x86_64 wheel）；ffmpeg / deno 取对应架构。
- 两个 DMG 分开发，避免一个包 1.5 GB。

**验收**：`lipo -archs` 与 `file` 抽查每个 Mach-O 都是目标架构；本机用 Rosetta 跑 x86_64 版，完成 D 的验收流程。

### G. 分发格式
- `package.py` 最后一步 `hdiutil create` 出 DMG：`Podsum.app` + 指向 `/Applications` 的替身，ULFO 压缩。
- 仓库根 `INSTALL.md`（DMG 里放一份同内容的「安装说明.txt」）：拖入、首次打开被拦时怎么放行、
  首次启动去哪里填 API、钥匙串授权为什么只问一次、怎么更新解析组件。
- 发布检查更新：见「待你决定」。

### H. 真机手动验收
003 plan 列的 6 项、004 plan 列的 7 项界面操作，外加 T045（真 LLM，产生少量费用）。
这些要占用屏幕和系统授权弹窗。结果回填到各自 plan.md 的「未验证」清单。

### I. 收尾
- 更新 `specs/002-macos-native/README.md` 的「打包」一节与本文件的「验证记录」。
- 全部通过后打 tag `v0.2.0`（只在本地，推不推由你定）。

---

## 顺序

A → B → C → D → E → F → G → H → I。
D 在 E 之前：E 的「更新」要用 D 定下来的 PATH 与 PYTHONPATH 结构。
F 放在功能都稳定之后，免得两个架构来回返工。

## 验证环境

沿用 `project_macos_client_verification` 的做法：打包产物复制一份，改 bundle id / 钥匙串 service，
连 fakeroot 后端（拷贝的数据库 + 假凭据），不碰真数据、真钥匙串、真 API 额度。

## 决定（2026-09-25）

1. **ffmpeg**：随包带静态编译版（ffmpeg.martin-riedl.de，arm64），附 GPL 声明与源码链接。
2. **Intel 版**：不做。F 项取消，安装说明写明仅支持 Apple Silicon；`package.py` 在非 arm64 上直接拒绝打包。
3. **真机验收**：用 computer-use 接管屏幕完成；T045 获准运行（少量费用）。
4. **联网实测**：获准连 YouTube / B 站拉公开视频，打包时获准下载运行时、wheel 与 ffmpeg。
5. **app 更新提示**：做。设置里「检查新版本」查 GitHub Releases `zz2543/Podcast-summary` 的最新 release，
   比较版本号，有新版就打开下载页（不自动下载安装）。并入 G 项。

## 验证记录（2026-09-25）

验证副本：`dist/Podsum.app` 复制一份，bundle id 改为 `local.podsum.macclient.verify`（存储随之隔离，见 `AppStorageRoot`），
vendor 里的 yt-dlp 换成 2026.7.4 以模拟"包里的版本过期了"，拷贝的数据库，假凭据，端口 8765。

| 项 | 怎么验的 | 结果 |
|---|---|---|
| B 签名不再被运行期改坏 | 按 `BackendController` 的环境起副本内嵌后端 → 提交本地音频 + YouTube 链接 → 停 → `codesign --verify --deep --strict` | 仍通过；bundle 内没有新写入的文件 |
| B 打包自检 | `package.py` 第 9 步 | 通过 |
| C 版本号 | 设置 › 通用 | 显示 `0.2.0 (build 110)` |
| D 外部依赖 | `package.py` 自检：只含系统目录的 PATH，找 ffmpeg / ffprobe / deno，yt-dlp 能识别 deno，真转码一段生成的音频并测时长 | 通过（yt-dlp 2026.08.19，deno 2.9.7） |
| D 真实流水线 | 副本内嵌后端：本地音频、YouTube「Me at the zoo」 | 下载、转码、封面都走完，停在转写（假 key → 401，符合预期） |
| D 缺 deno 的影响 | 同一 yt-dlp，PATH 去掉 / 保留 deno 各解析一次 YouTube | 都能拿到格式；去掉时 yt-dlp 警告"无 JS 运行时已弃用、可能缺格式" |
| D ffmpeg 签名 | `codesign -dv` 包内 ffmpeg | 仍是 Developer ID（KU3N25YGLU），`--deep` 重签没有覆盖它 |
| E 查询 | 设置 › 服务 › 解析组件 | 显示 `2026.07.04（内置）` |
| E 更新 | 点「检查并更新」 | `已从 2026.07.04 更新到 2026.08.19，重启后端后生效`；装进 `yt-dlp-2026.08.19-xxxx/`，`active` 指向它；暂存目录已清 |
| E 按后端路径加载 | 同样的 PYTHONPATH 起解释器 | 导入的是 components 里的 2026.08.19 |
| E 已是最新 | 再点一次 | `已是最新（2026.08.19）`，不切换 |
| E 恢复 | 点「恢复内置版本」 | 回到 `2026.07.04（内置）`，`active` 已删，旧目录留待下次启动清理 |
| G 检查新版本 | 设置 › 通用 | `还没有发布过正式版本`（仓库公开，尚无 release，GitHub 回 404） |
| G DMG | `package.py` 第 10 步 | `Podsum-0.2.0-arm64.dmg` 246 MB（app 884 MB） |
| T045 | 见 004 plan | 已跑 |

**没验到的**

- E 的「重启后端以生效」按钮与 `pruneInactive()`：副本没有真凭据，内嵌后端过不了配置检查（钥匙串不能从命令行写，
  密码框在后台模式下不让输入，全屏点击又被程序坞的透明浮层挡住）。所以"重启后端"一步用脚本按同样的环境代替。
- E 断网时的失败路径。
- D 启动自检（`checkTools`）在界面上的呈现：同样卡在凭据检查之后。
- H 的 003 / 004 界面手动项：浏览器在 computer-use 里只有只读权限（发不了全局快捷键），右键菜单、下拉菜单、
  侧边栏拖动都需要全屏点击，而全屏点击被程序坞浮层挡住；后台拖动侧边栏行只会把侧边栏收起。清单原样留在各自 plan.md。
