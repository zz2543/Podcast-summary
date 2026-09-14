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

**阶段 1 — 骨架（1 天）**
单 macOS target 的 Xcode 工程 + `EpisodeRepository` 协议 + 剧集列表页。用 `MockRepository` 读本目录 fixture，**不需要后端在跑**。
验收：Mac 窗口里出现 29 条真实剧集。

**阶段 2 — 界面迁移（3–5 天）**
13 个组件按依赖顺序搬：StatusDot → ScoreBadge → EpisodeCard → HookHero → ThreeActPanel → ChaptersTimeline → AudioPlayer → ChatPanel。liquid-glass 效果换 SwiftUI 原生材质。

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
| `fixtures/` | 6 份真实 API 响应快照 |

验证：

```bash
swiftc -O specs/002-macos-native/contracts/PodsumModels.swift specs/002-macos-native/verify/main.swift -o /tmp/podsum-verify && /tmp/podsum-verify
```

## 上游依赖

模型直接对应 `specs/001-podcast-summary/contracts/episode-output.schema.json`。schema 变更时须重抓 fixture 并重跑验证。
