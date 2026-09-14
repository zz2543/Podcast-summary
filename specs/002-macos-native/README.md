# 002 — macOS 原生客户端

把 `frontend-v2`（React + Vite，3726 行 TSX）替换为 SwiftUI 原生 Mac 客户端，后端沿用现有 Python 流水线不动。

**范围**：仅 macOS。iPhone 端已明确排除——iOS 上没有 Python 运行时、没有 yt-dlp、沙盒不允许这类下载与长期缓存。

## 为什么后端不重写

核心能力全在 Python：`yt-dlp` 抓取、ASR / LLM / TTS 三家云 SDK、SQLAlchemy + 任务队列。Swift 无等价物，重写等于推倒重来。原生化只换前端。

## 形态

单一 `.app`：SwiftUI 界面 + 内嵌 Python 环境，启动时拉起 `uvicorn` 子进程，退出时清理。取代现有的 `~/Applications/Podsum.app`（那是个 bash 启动器，起 uvicorn + vite 再开浏览器）。前端进程消失，子进程从 2 个减为 1 个。

去掉 iPhone 后多出的自由度：
- 可放开用 Mac 惯用法——真侧边栏、菜单栏 `Commands`、`Settings` 场景、toolbar、拖放、hover、右键菜单、⌘ 快捷键，无需 `#if os()` 分支
- 不需要 Apple Developer Program
- 后端恒为 localhost 子进程，没有 baseURL 配置、没有服务发现
- 可关闭 App Sandbox 直读文件系统：音频与文稿走 `file://`，`/files/*` 那 5 个端点在客户端里用不上
- `.env` 里的 provider 开关与各家 API key 做成原生 `Settings` 面板，key 存 Keychain 而非明文——这是原生化真正的增量价值

## 分阶段

**阶段 1 — 骨架** ✅ 已完成，见 `macos-client/`
单 macOS target 的 Xcode 工程 + `EpisodeRepository` 协议 + 剧集列表页。用 `MockRepository` 读本目录 fixture，**不需要后端在跑**。
已验收：窗口渲染 29 条真实剧集，侧栏筛选（全部 29 / 已完成 27 / 进行中 1 / 已评分 3）、搜索、空态、未评分态均实测通过。

```bash
open macos-client/Podsum.xcodeproj
```

**阶段 2 — 界面迁移** ✅ 已完成
StatusDot、ScoreBadge、EpisodeCard、UsefulnessCard、HookHero（并入详情页）、ThreeActPanel、ChaptersTimeline（含关键时刻与 takeaway）、实体标签、溯源信息、AudioPlayerBar（`AVPlayer`，章节刻度 + 时间戳跳转）、ChatPanel（`URLSession.bytes` 读 SSE）、SubmitSheet（拖放 + 批量）、重试 / 删除 / 生成音频摘要、ActiveJobsStrip（WebSocket 实时进度）。

### 排版与间距的依据

本机 macOS 26.5 实测 `NSFont.preferredFont` 的磅值 / 行高：

| 样式 | 磅值 | 行高 |
|---|---|---|
| largeTitle | 26 | 32 |
| title1 | 22 | 26 |
| title2 | 17 | 22 |
| title3 | 15 | 20 |
| headline / body | 13 | 16 |
| callout | 12 | 15 |
| caption | 10 | 13 |

Apple HIG 明确：**macOS 默认正文 13pt、最小 10pt**，长段落应使用宽松行距，并避免 Ultralight/Thin/Light 字重。

所以不用 `.callout`(12) / `.caption`(10) 承载正文——它们在默认值以下。阅读正文基准取 **17pt**，最小档（×0.85 ≈ 14.5pt）仍高于 13pt 默认值，不会掉进难读区间。间距统一走 `Space` 标度（4/8/12/16/20/28），HIG 的理由是对齐传达关联、留白表达分组。

### 读者可调字号（⌘+ / ⌘- / ⌘0）

HIG 明说 **macOS 不支持 Dynamic Type**，所以这件事必须 app 自己做——Safari、邮件、图书都是各自实现的。

`Typography.swift` 里 `TypeRole` 只声明基准磅值，实际字号 = 基准 × 环境里的 `textScale`；档位离散（0.85 / 1.0 / 1.15 / 1.3 / 1.5 / 1.75 / 2.0），用 `@AppStorage` 跨启动保留。行距、刻度条高度、图标尺寸、栅格列宽都跟着缩放。

**键位有个坑**：`keyboardShortcut("+", modifiers: .command)` 能让菜单显示成 ⌘+，但**不会触发**——SwiftUI 要求修饰键完全吻合，而读者按 ⌘+ 时键盘发出的是 cmd+shift+=。同理 `KeyEquivalent("+")` 配 `[.command, .shift]` 也不行，那个字符本身已隐含 shift。

可用的写法是把物理键写成 `"="`：

| 目的 | 声明 | 作用 |
|---|---|---|
| 菜单显示 ⌘+ | `"+" + .command` | 仅显示，不触发 |
| 实际接 ⌘= | `"=" + .command` | 生效 |
| 实际接 ⌘+ | `"=" + [.command, .shift]` | 生效 |

后两个挂在视图层的隐藏按钮上，菜单才不会多出重复项。以上四种按法都已实测。

### 离屏设计核对

`macos-client/design-check/` 用 `ImageRenderer` 把组件渲染成 PNG，不启动 app、不需要屏幕解锁也能看到真实渲染结果：

```bash
swiftc -O -parse-as-library \
  specs/002-macos-native/contracts/PodsumModels.swift \
  macos-client/Podsum/Design/Theme.swift macos-client/Podsum/Design/Typography.swift \
  macos-client/Podsum/Data/StringUtils.swift macos-client/Podsum/Data/AudioPlayerModel.swift \
  macos-client/Podsum/Views/AudioPlayerBar.swift macos-client/Podsum/Views/ActiveJobsStrip.swift \
  macos-client/Podsum/Views/ChapterRow.swift macos-client/design-check/main.swift \
  -o /tmp/podsum-design \
  && /tmp/podsum-design /tmp/check.png specs/002-macos-native/fixtures \
       data/01M2FKVC8GT40083QZHH6VRSMW/audio.normalized.mp3 \
  && open /tmp/check.png
```

传一个真实 mp3 进去，播放条画的就是真时长与真章节刻度（脚本会等
`AVPlayerItem` 读到时长再渲染，否则画的是占位值）。

两条限制，看图时要先排除掉：

- `ImageRenderer` 不触发 `onAppear`，带入场动画的视图要用 `animate: false` 构造。
- **AppKit 撑起来的控件画不出来**，会渲染成一块黄底 ⊘：`ProgressView`、
  `.menuStyle(.borderlessButton)` 的 `Menu` 都是。这不是布局出错——
  脚本里留了一个对照组（一个光秃秃的 `ProgressView(value: 0.5)`）专门用来确认这件事。

**阶段 3 — 接入与封装** ✅ 已完成
`LiveRepository` 换掉 Mock（View 一行没改）、`BackendController` 管 uvicorn 子进程、`Settings` 面板 + 钥匙串、`package.py` 把 Python 环境打进 `.app`。

---

## 凭据：默认全为空

**这个 app 不内置任何人的 API 凭据。** 所有字段初始为空，填好之前后端起不来，
界面会明说缺哪几项（`RootView` 的 `.needsConfiguration` 分支）。

| 存哪儿 | 存什么 |
|---|---|
| 钥匙串（`Keychain.swift`，service `local.podsum.macclient`） | 各家 API key / token |
| UserDefaults | 供应商选择、接口地址、模型名、端口、目录 |

LLM 那一支叫「OpenAI 兼容接口」：**接口地址、模型名、API Key 都是自己填的**，
不限厂商（后端的环境变量名沿用 `DEEPSEEK_*` 只是历史原因，走的是标准
`/chat/completions`）。设置面板里有「测试连接」，直接打你填的那个地址——
地址和 key 是最容易敲错的地方，与其等提交一集之后在流水线里失败，不如当场问一句。

### 环境变量是怎么传的，以及为什么要写空串

后端读环境变量，`AppSettings.environment(dataDirectory:)` 负责铺。
关键的一条：**受管的每一个键都会显式写入，没填的写空串**。

不这么做的话，pydantic-settings 会去读工作目录下的 `.env`，于是面板显示为空、
后端却在用 `.env` 里别人的 key。实测确认过优先级：同时存在时环境变量胜出，
显式空串被 `_present()` 判为"没配"，不会回落到文件。

### TTS 成了可选项（后端的一处改动）

后端原本在启动时就校验三家凭据，TTS 缺一项就起不来——这意味着只想用
LLM + Whisper 的人必须先去办一个语音合成账号。加了 `TTS_ENABLED`：
关掉就跳过这段校验，`POST /{id}/digest` 返回 `400 tts_disabled`。
默认仍为 `true`，现有部署行为不变。音频摘要本来就跑在独立的流水线里
（`create_tts_pipeline`），关掉不影响转写与摘要。

---

## 打包

```bash
python3 macos-client/package.py                              # 内嵌 CPython（自包含）
python3 macos-client/package.py --python /usr/local/bin/python3   # 用本机解释器
```

产出 `macos-client/dist/Podsum.app`。内容：

```
Contents/Resources/backend/{backend,prompts,scripts,specs}   后端源码、提示词、schema
Contents/Resources/backend/vendor/                           Python 依赖
Contents/Resources/python/                                   CPython（--with-runtime 时）
```

三个踩过的坑，都写进脚本的自检里了：

1. **依赖必须用最终要跑它的解释器装。** `pydantic-core`、`yt-dlp` 带编译扩展，
   按 CPython 版本出 wheel；用 3.13 装的 vendor 在 3.12 上 import 就失败。
2. **vendor 里不能留 `podsum` 自己。** `json_export` 在 import 时读
   `specs/001-podcast-summary/contracts/episode-output.schema.json`，
   路径是从包所在位置往上数四层算的——装进 vendor 的那份算出来的位置没有 `specs/`。
   脚本装完即删掉 vendor 里的 `podsum`，让源码那份生效（`PYTHONPATH` 里它在前）。
3. **schema 要一起拷。** 少了它后端连 import 都过不去。

打完包要重签名（`codesign --sign -`），往 bundle 里塞东西会让原签名失效。

---

## 后端子进程

`BackendController` 的状态机是刻意显式的——"起不来"有四种完全不同的原因，
混成一个"失败"会让人无从下手：

| 状态 | 出口 |
|---|---|
| `.needsConfiguration([缺的字段])` | 直接打开设置 |
| `.noRuntime(找过哪些路径)` | 手动指定后端目录 / Python |
| `.failed(原因 + 日志尾巴)` | 重试，日志在 `~/Library/Logs/Podsum/backend.log` |
| `.ready(URL)` | 进主界面 |

几个决定：

- **端口上已有健康的 podsum 就直接用它**，不再起一个。这同时兜住了两种情况：
  上次退出没收干净的孤儿进程，和终端里正开着的 `make run`。
- **退出时收子进程走 `AppDelegate.applicationWillTerminate`。** SwiftUI 的 Scene
  没有这个钩子，不接的话 uvicorn 会活过 app——实测确认过：第一版就漏了，
  app 退出后端口上还留着监听进程。
- **PATH 要手工补。** 从 Finder 启动时 PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin`，
  yt-dlp 与 ffmpeg 都在 Homebrew 里，不补上抓取阶段必然失败。
  （那个 bash 启动器里也有同一段，原因相同。）

---

## 验证记录

对着**真的后端**跑，不是对着 mock：

| 验的什么 | 怎么验的 | 结果 |
|---|---|---|
| 13 项 API 行为 | 起一个隔离后端（拷贝的 DB、假凭据、独立工作目录），Swift 集成脚本直连 | 全过 |
| 模型解码 | `verify/main.swift`，6 份 fixture + Job / JobEvent / DigestResponse 内联样本 | 全过 |
| 环境变量优先级 | 工作目录放一个 `.env`，确认 app 传的值胜出、空串不回落 | 确认 |
| 子进程生命周期 | 真的 `.app` 启动 → 迁移 → 服务 → 退出 → 子进程被收 | 确认 |
| 打包产物 | 内嵌后端 + vendor，空目录冷启动建库并提供服务 | 确认 |
| 组件渲染 | `design-check/` 离屏渲染成 PNG | 见下 |

集成脚本覆盖：列表、详情、404 错误信封、WebSocket 握手、非法链接 400、
TTS 关闭时 digest 被拒、SSE 错误路径、音频 URL 回退、删除。

顺带修掉的两个真问题：

- **提交一个没有协议头的链接返回 500。** httpx 的 `UnsupportedProtocol` 从
  `ingest_direct_url` 深处冒出来，API 层的 `except (IngestError, ValueError)`
  接不住。现在在下载之前就判协议，返回 400，也顺便不再留下空的剧集目录。
- **第 1 章的起点显示成「—」。** `Fmt.timestamp` 复用了 `Fmt.duration`，
  而后者把 0 当作"不知道多长"。时间戳的 0 就是开头，第 1 章起点恰恰总是 0。


## 接缝

View 只认协议，通过 `@Environment` 注入。接后端那天 = 写一个 struct + 换一行注入点。SwiftUI Preview 永远用 Mock。

```swift
protocol EpisodeRepository: Sendable {
    func list() async throws -> [EpisodeSummary]
    func detail(id: String) async throws -> EpisodeDetail

    func create(_ submission: Submission) async throws -> [CreateEpisodeResponse]
    func retry(id: String) async throws -> Job
    func delete(id: String) async throws
    func requestDigest(id: String) async throws -> DigestResponse
    func chat(id: String, message: String, history: [ChatTurn]) -> AsyncThrowingStream<String, Error>

    func audioURL(for episode: EpisodeDetail) -> URL?
    func digestURL(for episode: EpisodeDetail) -> URL?
    func jobEvents() -> AsyncStream<JobEvent>
}
```

接上后端那天的实际代价，事后核对：**View 一行没改**，
新增 `LiveRepository`（HTTP + SSE + WebSocket）与注入点一行。
写操作与实时事件在 Mock 里是"假装"的——新提交的剧集只存在内存里，
由定时器推着走完阶段序列，好让进度条的动效在没有后端时也能验收。

`RootView` 里保留了「先看离线示例」：fixture 打在 bundle 里，
没有后端也能翻 29 集列表和 5 集详情。

音频优先走 `file://`（数据目录的绝对路径是 app 自己配的），
找不到文件才回退 `/files/audio`——连外部后端时就是这条路。

## 本目录内容

| 路径 | 说明 |
|---|---|
| `contracts/api-shapes.md` | **先读这个**。两种响应形状 + 9 条真实数据陷阱 |
| `contracts/PodsumModels.swift` | Swift `Codable` 模型：摘要产物 + 任务 / 实时事件 / 写操作响应 |
| `fixtures/` | 6 份真实 API 响应快照 |
| `verify/main.swift` | 解码验证脚本 |

客户端代码在 `macos-client/`：

| 路径 | 说明 |
|---|---|
| `Podsum/Data/` | Repository（Mock / Live）、设置、钥匙串、后端子进程、播放器、任务模型 |
| `Podsum/Views/` | 全部界面 |
| `design-check/` | 离屏渲染成 PNG，不启动 app、不需要屏幕解锁 |
| `package.py` | 打包成自包含 `.app` |
| `gen-project.py` | 重新生成工程（自动扫描 `Podsum/**/*.swift`，新增源文件后重跑即可） |

验证：

```bash
swiftc -O specs/002-macos-native/contracts/PodsumModels.swift specs/002-macos-native/verify/main.swift -o /tmp/podsum-verify && /tmp/podsum-verify
```

## 上游依赖

模型直接对应 `specs/001-podcast-summary/contracts/episode-output.schema.json`。schema 变更时须重抓 fixture 并重跑验证。
