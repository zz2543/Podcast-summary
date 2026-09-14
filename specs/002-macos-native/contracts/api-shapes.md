# Podsum API 形状与真实数据陷阱

**校准时间**：2026-09-14
**校准方式**：对本机运行中的后端 `http://127.0.0.1:8000` 抓取全部 29 个剧集的列表与详情响应，逐字段与 `specs/001-podcast-summary/contracts/episode-output.schema.json` 比对。
**配套产物**：`PodsumModels.swift`（Swift 模型）、`../fixtures/`（真实响应快照，已通过解码验证）

---

## 一、两种形状，不是一种

| 端点 | 形状 | 字段数 | 构造函数 |
|---|---|---|---|
| `GET /api/episodes` | `EpisodeSummary` | 11 | `_episode_summary` |
| `GET /api/episodes/{id}` | `EpisodeDetail` | 20 | `_episode_detail` |

列表项**不含** `hook` / `three_act` / `chapters` / `entities` / `source_ref` / `prompt_versions` / `summary_style` / `artifact_paths` / `guests`。

列表页想显示钩子文案就必须逐条拉详情——**这是 N+1**。若后续列表要展示正文摘要，正确做法是给后端 `_episode_summary` 加字段，而不是在客户端循环请求。

---

## 二、最大的坑：`data/<id>/summary.json` 不等于 API 响应

API 响应由 SQLite 渲染，不读 `summary.json`。两者已经漂移：

| 字段 | 磁盘文件 | API 响应 | 谁是真的 |
|---|---|---|---|
| `status` | 29/29 全是 `processing` | 27 `done` / 1 `partial` / 1 `processing` | **API** |
| `artifact_paths` | 三个字段恒为 `null` | 填好的相对路径 | **API** |
| `stage_status` | 多数只有 5 个 key（缺 `usefulness`） | 恒为 6 个 key | **API** |

> **结论：fixture 必须从 API 抓，绝不能从 `summary.json` 拷。**
> 本目录的 fixture 全部来自 API。

---

## 三、逐条陷阱

**1. `source_type` 不可信。**
29 个剧集全部标为 `"youtube"`，但其中大量 `source_ref` 实际是 `bilibili.com` 链接。
→ 判断来源平台请解析 `sourceRef` 的 host。

**2. 日期不是标准 ISO8601。**
实际形如 `2026-09-14T09:27:15.770252`——无时区后缀、6 位小数秒。
`JSONDecoder.DateDecodingStrategy.iso8601` 会**直接解码失败**。用 `PodsumModels.swift` 里的 `.podsum` 策略（已容纳有/无小数秒两种）。

**3. 枚举必须兜底。**
pipeline 仍在演进，新枚举值随时会出现。一个未知的 `status` 不该让整个列表崩掉。
模型里所有枚举都用 `Fallback<T>` 包装，解码永不抛错。已验证 `status:"transcoding"`、`source_type:"podcast_rss"`、`language:"ja"`、`stage_status.hook:"weird"` 全部安全降级。

**4. `usefulness` 绝大多数为 null。**
29 个里仅 3 个有评分（62 / 72 / 55）。
→ `EpisodeCard` 必须有"无评分"态，且不能是占位骨架——它是稳定终态。

**5. 老数据的可选字段。**
- `quote.takeaway`：key moments 功能上线前入库的引用为 `null`（5 份 fixture 里 3 份全 null）
- `chapter.summary`：仅在要点本身丢失因果链时才有，多数为 `null`
- `prompt_versions.usefulness_score` / `summary_style`：老数据缺这两个键

**6. `language` 标注不可靠。**
存在 `language: "en"` 但标题与正文均为中文的剧集（如 `01KRZNBZYA`）。这是已知的上游问题（见 commit `56d567d`）。
→ 不要用它决定字体、排版方向或断行策略。

**7. `artifact_paths` 是相对仓库根的路径。**
形如 `data/<ULID>/summary.md`。Swift 侧要拼上项目根目录才能落到真实文件。
`tts` 字段：5 份 fixture 里 2 份非 null。

**8. 分页尚未实现。**
`next_cursor` 恒为 `null`，`limit` 上限 200，`cursor` 参数被后端 `del` 丢弃。
→ 列表页现阶段按"一次取全部"设计，别先写分页逻辑。

**9. 存在孤儿数据。**
`data/01KZ6A2WNHGC5KDYE4S1D0GJJT/` 磁盘目录完整，但 DB 无记录，API 返回 404。
→ 任何"扫描 data 目录"的想法都不成立，剧集清单只有一个来源：API。

---

## 四、Fixture 清单

全部为真实 API 响应，已通过 `PodsumModels.swift` 解码验证。

| 文件 | 覆盖的情况 |
|---|---|
| `episodes-list.json` | 29 项全量列表，含三种 status 的真实分布 |
| `detail-done-full.json` | 最完整：`done` + usefulness 62 + 13 个 takeaway 齐全 |
| `detail-partial-tts-failed.json` | `partial` + `tts: failed_after_retries` + usefulness 缺失 |
| `detail-processing.json` | `processing` + 唯一有 `chapter.summary` 的样本 |
| `detail-done-28s.json` | 28 秒极短剧集，3 章——时长格式化与紧凑布局的下界 |
| `detail-done-legacy-null.json` | 老数据：takeaway / usefulness 全 null，96 分钟 12 章，中英混排超长标题 |

**做 UI 时对着这六份调，不要手编假数据。** 手编的数据太干净，一接真后端就崩。

---

## 五、验证方式

模型改动后重跑解码验证：

```bash
swiftc -O specs/002-macos-native/contracts/PodsumModels.swift specs/002-macos-native/verify/main.swift -o /tmp/podsum-verify && /tmp/podsum-verify
```

后端有改动时重抓 fixture，比对字段是否漂移。
