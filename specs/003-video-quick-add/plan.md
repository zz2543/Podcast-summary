# Plan & 实现记录：视频一键送总结（Mac）

**Spec**: [spec.md](spec.md) · **Date**: 2026-09-24 · **Branch**: `002-macos-native`

## 结构

```
全局快捷键 ⌥⌘S → 浏览器当前标签页 / 剪贴板 → QuickAddCenter（落盘队列）→ POST /api/episodes → 系统通知
                                                  ↑ 后端就绪时自动续提交
                                                  └→ 记录（工具栏「快捷提交」、菜单栏最近 5 条）
```

> 2026-09-24：最初还有「浏览器书签 → `podsum://add?url=…`」入口，已实现并验证后按用户要求删除，
> 只留快捷键。一并去掉了 `CFBundleURLTypes`、`application(_:open:)` 与交还焦点的逻辑；
> `QuickAddItem.Source.bookmarklet` 保留，只为读得出之前存下的记录。

| 文件 | 职责 |
|---|---|
| `macos-client/Podsum/Data/VideoLink.swift` | 只认 B 站 / YouTube 单个视频，规整成一种写法 |
| `macos-client/Podsum/Data/QuickAddCenter.swift` | 队列 + 记录 + 提交；`~/Library/Application Support/Podsum/quick-add.json` |
| `macos-client/Podsum/Data/QuickAddSources.swift` | Carbon 全局热键、AppleScript 读标签页、`UNUserNotificationCenter` |
| `macos-client/Podsum/Views/QuickAddViews.swift` | 设置页「快捷提交」、记录弹窗、菜单栏菜单 |
| `macos-client/Podsum/PodsumApp.swift` | 模型移到 `AppDelegate`；`Window` 单窗口；`MenuBarExtra` |
| `macos-client/Podsum/Info.plist` | `NSAppleEventsUsageDescription` |

## 关键决定

- **热键用 `RegisterEventHotKey`。** 不需要辅助功能授权，按键也不会漏到前台 app。
- **前台是受支持浏览器时以标签页为准**，不是视频就报"无法识别"，不回退剪贴板（spec US1-5）；
  只有未授权 / 没有窗口时才读剪贴板。
- **一次提交一条，超时放到 900 s。** 后端要先把音频抓完才回响应，期间一个字节都不发；
  默认 30 s 会让客户端报错而后端照样建出剧集。
- **连不上后端时把条目放回队列**（探一下 `/api/health`），不记为失败；后端回来自动续。
- **"已收到"与结果共用一个通知 identifier**，结果覆盖回执，通知中心不堆中间态。
- **关窗不退出（FR-016）**：`applicationShouldTerminateAfterLastWindowClosed` → false，
  后端在 `applicationDidFinishLaunching` 启动；`Window` 场景保证只有一个主窗口。
  通知 / Dock / 菜单栏开主窗口，靠菜单栏图标与主窗口各自把 `openWindow` 交给 `UIState`。

## 后端改动

实现时用复制的真实数据库一测就暴露：旧剧集存的是 `…/video/BV1QF6EBiErM/?vd_source=…`，
而后端按字符串精确判重，且判重发生在**下载完之后**。

1. `ingest.video_identity()`：按"平台 + 视频 id（+ 分 P）"得出身份；`b23.tv` 离线展不开，返回 None。
2. `_existing_episode_id()`：先精确比对，不中再按身份比对全部视频剧集（包括旧格式行）。
3. JSON 提交在**下载前**判重，409 的 `error.details.episode_id` 给出已有剧集（`contracts/http-api.md` 已补）。
   下载后保留一次复查，防两次并发提交。
4. 客户端 `RepositoryError.conflict(message:existingEpisodeID:)` 接住它，通知点开直达那一集。

后端测试：`tests/unit/test_ingest.py`（身份等价 / 区分 / 未知）、`tests/integration/test_duplicate_link.py`。全套 206 passed。

## 已验证（2026-09-24，书签入口删除前）

下表里冷 / 热启动与焦点归还两行测的是已删除的书签入口，留作记录；
其余（识别、队列、提交、判重、记录渲染）与入口无关，对快捷键同样成立。

隔离环境：复制一份客户端，bundle id / 钥匙串 service / 队列文件都换成 `…verify`，
连 fakeroot 后端（复制的数据库 + 假凭据，端口 8765），不碰真数据、真钥匙串、真 API 额度。

| 项 | 结果 |
|---|---|
| 链接识别 20 例（B 站长链/短链/分享文案/分 P/稍后再看/番剧，YouTube 各形态，非视频页） | 全过 |
| 冷启动：Podsum 未运行时 `open podsum://add?url=…` | 启动并提交；旧格式重复链接 → 已在库里 + 剧集 id |
| 热启动：新视频 | 已加入，带回标题「Me at the zoo」 |
| 非视频页 | 无法识别，不提交 |
| 焦点归还 | 冷启动 ~1 s、热启动 ~0.2 s 回到原 app |
| 后端重复判定 | 旧格式行 0.03 s 返回 409 + `episode_id`，未触发下载 |
| 记录行（亮 / 暗） | 离屏渲染正常 |

## 未验证 —— 需要在真机上手动过一遍

这些都要占用屏幕或系统授权弹窗，没有在用户使用电脑时去做：

- [ ] 全局快捷键真的触发（Safari / Chrome / Arc / Edge 各一次，含首次「自动化」授权弹窗）
- [ ] 剪贴板路径：B 站 Mac 客户端「复制链接」→ 在非浏览器 app 前台按快捷键
- [ ] 系统通知的外观，以及点通知打开对应剧集
- [ ] 关掉主窗口后：菜单栏图标在、快捷键仍有效、点 Dock / 菜单栏「打开 Podsum」能开回主窗口
- [ ] 设置里改快捷键、改成已被占用的组合时的提示
- [ ] 默认 ⌥⌘S 与 Xcode「全部存储」冲突——常用 Xcode 的话改一个组合
