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

**阶段 2 — 界面迁移** 🚧 进行中
已完成：StatusDot、ScoreBadge、EpisodeCard、UsefulnessCard、HookHero（并入详情页）、ThreeActPanel、ChaptersTimeline（含关键时刻与 takeaway）、实体标签、溯源信息。
待做：AudioPlayer（`AVPlayer` 播本地 `file://`）、ChatPanel（`URLSession.bytes` 流式）、提交/重试/删除。

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
swiftc -O specs/002-macos-native/contracts/PodsumModels.swift \
       macos-client/Podsum/Design/Theme.swift \
       macos-client/Podsum/Views/UsefulnessCard.swift \
       macos-client/design-check/main.swift -o /tmp/podsum-design \
  && /tmp/podsum-design /tmp/cards.png && open /tmp/cards.png
```

注意 `ImageRenderer` 不触发 `onAppear`，带入场动画的视图要用 `animate: false` 构造。

**阶段 3 — 接入与封装（2 天）**
`LiveRepository` 换掉 Mock（View 一行不改）+ WebSocket 进度 + ChatPanel 流式 + Python 环境打包 + Settings 面板。

## 接缝

View 只认协议，通过 `@Environment` 注入。接后端那天 = 写一个 struct + 换一行注入点。SwiftUI Preview 永远用 Mock。

```swift
protocol EpisodeRepository {
    func list() async throws -> [EpisodeSummary]
    func detail(id: String) async throws -> EpisodeDetail
}
```

返工边界（诚实划线）：

| 部分 | 代价 |
|---|---|
| 列表、详情、三幕、章节、实体、评分、音频播放 | **零返工** |
| 实时进度（WebSocket）、ChatPanel 流式 | Mock 用 Timer 假装，接入时**换一个类** |
| 提交 / 重试 / 删除 | Mock 假装成功，接入时换实现 |

三者都在 Repository 层内部，View 不受影响。

## 本目录内容

| 路径 | 说明 |
|---|---|
| `contracts/api-shapes.md` | **先读这个**。两种响应形状 + 9 条真实数据陷阱 |
| `contracts/PodsumModels.swift` | Swift `Codable` 模型，317 行，已通过全部 fixture 解码验证 |
| `verify/main.swift` | 解码验证脚本 |

客户端代码在 `macos-client/`。新增源文件后重跑 `python3 macos-client/gen-project.py` 重新生成工程（自动扫描 `Podsum/**/*.swift`，无需手动登记）。
| `fixtures/` | 6 份真实 API 响应快照 |

验证：

```bash
swiftc -O specs/002-macos-native/contracts/PodsumModels.swift specs/002-macos-native/verify/main.swift -o /tmp/podsum-verify && /tmp/podsum-verify
```

## 上游依赖

模型直接对应 `specs/001-podcast-summary/contracts/episode-output.schema.json`。schema 变更时须重抓 fixture 并重跑验证。
