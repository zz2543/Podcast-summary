# Research：视频分类

**Feature**: [spec.md](spec.md) · **Date**: 2026-09-24

## 0. 事实基础（2026-09-24 读代码 + 只读查询真实库）

| 事实 | 来源 | 对设计的影响 |
|---|---|---|
| 库里 31 条剧集，全部 `done` | `data/podsum.sqlite3` | 首次 AI 分类约 31 条，一两批即可完成 |
| 一句话总结 `hook` 平均 155 字，最长 446 字 | `summary_artifact.hook` | 每条摘要要截断，不能整段塞进 prompt |
| 每集平均 7.3 个章节，最多 16 个；章节标题平均 25 字 | `chapter` | 章节标题是很好的主题信号，取前 8 个 |
| 标题平均 38 字，最长 81 字 | `episode.title` | 标题本身信息量足够 |
| 内容高度集中：前 8 条标题都是 AI 编程 / Claude Code / Codex | 同上 | 分类要比「科技」更细，否则一个分类装下整个库 → 写进 prompt |
| `summary_artifact` 有 52 行含 hook，而剧集只有 31 条 | 同上 | **有孤儿行**。所有读取必须从 `episode` 出发 join，不能直接扫 `summary_artifact` |
| SQLite 没有打开 `PRAGMA foreign_keys` | `grep foreign_keys backend/src` 无结果 | `ON DELETE SET NULL` 在库层**不会生效**。删除分类时由 repo 显式清空归属 |
| `LLMClient.complete_json(prompt, schema)` 是同步调用，自带 3 次重试 | `services/llm_client.py` | 在 `asyncio.to_thread` 里调用，和 pipeline 的做法一致 |
| prompt 一律经 `PromptAssembler.render(role, version, **slots)`，带 frontmatter | `domain/prompt_assembler.py`、`prompts/*.v*.md` | 新增两个 prompt 文件，满足宪法 V |
| 列表接口 `GET /api/episodes` 最多返回 200 条，客户端固定请求 200 | `api/episodes.py:147`、`LiveRepository.swift:42` | 分类数量由后端统计，不靠客户端数列表 |
| 数据库变更走 alembic，当前最新是 `0004_detail_and_key_moments` | `persistence/migrations/versions/` | 新增 `0005_categories` |
| 侧边栏是 `List(Filter.allCases, selection: $filter)`，一个平铺列表 | `EpisodeListView.swift:73` | 选中项要从 `Filter` 扩成「状态筛选 / 分类 / 未分类」三种 |

## 1. AI 分类的调用策略

**Decision**: **两阶段**。第一阶段「定分类表」，一次调用；第二阶段「逐条归类」，按每批 40 条分批调用。

- **阶段 A（taxonomy）**：输入是已有分类名 + 每条参与视频的**短摘要**（标题 + hook 截到 120 字）。输出是最终分类表：保留哪些已有分类（全部保留，AI 不能删改），再加哪些新分类（附一句说明）。
  - 库里没有分类时，新分类 3–10 个。
  - 已有分类时，新分类最多 5 个。
- **阶段 B（assign）**：分类表固定后，每批 40 条，输入是**长摘要**（标题、hook 截到 200 字、前 8 个章节标题、前 5 个实体）。输出是 `episode_id → 分类 key`，也可以给 `null`，表示都不合适。
- 视频数 ≤ 40 时，阶段 B 只有一批，总共 2 次调用。

**Rationale**:
- 先把分类表定下来，再分批归类，每批用的是**同一张表**。这样不会出现第 1 批叫「AI 编程」、第 3 批叫「AI 辅助开发」的漂移。
- 进度可以按批次汇报（FR-016），某一批失败只影响这一批的视频（spec Edge Case「部分批次成功」）。
- 阶段 A 只用短摘要：200 条 × 约 150 token ≈ 30k token，DeepSeek 的上下文放得下。

**Alternatives considered**:

| 方案 | 取舍 | 结论 |
|---|---|---|
| 单次调用：全部视频一次送进去，同时要分类表和归类 | 最简单，31 条时完全够用；但 200 条时输出很长，JSON 容易截断或出错，失败就全失败，也没有进度可报 | 否决。不过阶段 A + 一批 B 在小库上已经接近它的成本 |
| 向量 + 聚类（embedding → k-means / HDBSCAN → LLM 给每簇起名） | 大库上便宜且稳定；但要新增 embedding provider 和聚类依赖（宪法：新依赖要登记），每簇还是要 LLM 起名；「优先放进用户已有分类」很难表达 | 否决 |
| 逐条调用：每条视频一次 | 最好控制，但 200 条就是 200 次调用，慢而贵；分类表同样会漂移 | 否决 |

## 2. 分类与归属的存储

**Decision**: 新表 `category`，另在 `episode` 上加三列：`category_id`、`category_origin`（`manual` / `auto` / NULL）、`category_updated_at`。**锁定 ⇔ `category_origin = 'manual'`**，不另设布尔列。

**Rationale**:
- 一条视频至多一个分类（FR-003），用 1:0..1 的外键列最直接，列表查询不需要多一次 join。
- 用一个字段同时表达来源和锁定，避免「来源 = manual 但没锁」这种不合法组合。
- 「交给 AI 分类」（FR-011）把 `manual` 改为 `auto`，保留当前分类，语义正好是「这条由 AI 管理」。
- `category_updated_at` 用作应用 AI 方案时的乐观并发检查（见 §4）。

**Alternatives considered**:

| 方案 | 取舍 | 结论 |
|---|---|---|
| 独立关联表 `episode_category(episode_id PK, category_id, origin, …)` | 不改 `episode` 表；但每次列表都多一次 join，删除剧集时还要记得清理（外键不生效，见 §0） | 否决 |
| 多对多（标签） | spec 明确是单一归属，标签以后另做 | 否决 |
| 只存在客户端本地（JSON 文件） | 不用改后端；但换机器或重装就丢了，网页端以后也读不到（spec Assumptions） | 否决 |

## 3. 一次 AI 运行如何在前后端之间传递

**Decision**: 后端在**内存**里保存运行状态，客户端轮询。

- `POST /api/categorize` 启动，返回 `run_id`。
- `GET /api/categorize/{run_id}` 返回进度，完成后返回方案。
- `DELETE /api/categorize/{run_id}` 取消。
- 应用走**无状态**的 `POST /api/categories/apply`，客户端把用户编辑后的最终选择整个发回去。

**Rationale**:
- spec 规定方案不是持久数据（Key Entities），所以不需要建表。
- 应用接口是无状态的，即使后端在预览期间重启，客户端手里的方案照样能应用。锁定和并发由应用接口自己检查。
- 客户端每秒轮询一次，一次运行几十秒，请求量可以忽略，也不用扩展现有只服务于 job 的 WebSocket。
- 同一时间只允许一个运行中的 run（FR-016），第二次启动返回 409。

**Alternatives considered**:

| 方案 | 取舍 | 结论 |
|---|---|---|
| 一个长请求，同步返回方案 | 最简单；但没有进度，取消只能断开连接，超时不好定（003 已经踩过 URLSession 30 s 超时的坑） | 否决 |
| 复用 `job` 表和 `ws_progress` | 进度推送现成；但 `job` 表绑定 `episode_id` 且有状态 CHECK 约束，会被迫改表语义 | 否决 |
| 方案持久化进表 | 可以跨重启恢复预览；spec 不需要，还要多一套清理逻辑 | 否决 |

## 4. 应用时的并发与锁定保护

**Decision**: 客户端每条建议都带上它**生成时**看到的 `from_category_id`。服务端在同一个事务里逐条检查，满足以下全部条件才写入，否则跳过并返回原因：

1. 视频仍然存在，否则跳过，原因 `episode_gone`。
2. `category_origin != 'manual'`，否则跳过，原因 `locked`。
3. 当前 `category_id == from_category_id`，否则跳过，原因 `changed`。
4. 目标分类存在：已有分类的 id 仍在，或新分类在本次应用中创建成功。否则跳过，原因 `category_gone`。

新分类的名字按规范化 key（NFKC + 去首尾空格 + casefold）比对。与已有分类同名时直接复用已有分类，不报错（spec Edge Case）。

**Rationale**: 这样 spec 列的几种运行期冲突（手动挪了、删了视频、删了分类）都能落到明确的跳过原因，SC-002「手动归类被 AI 改动 0 次」也在服务端有硬保证，不依赖客户端。

## 5. 分类名规范化

**Decision**: 名字的唯一键 `name_key = casefold(strip(NFKC(name)))`，保存在 `category.name_key` 上并加 UNIQUE 约束。显示用原样的 `name`（只去首尾空格）。长度 1–30（按 Unicode 字符计）。保留名：`全部`、`未分类`、`All`、`Uncategorized`（与客户端两种语言的固定入口一致）。

**Rationale**: NFKC 能把全角空格、全角字母这类「看起来一样」的写法归一。唯一性放在数据库层兜底，并发新建也不会产生重名。

## 6. 客户端侧边栏选中模型

**Decision**: 把 `Filter` 换成一个枚举 `SidebarSelection { case status(Filter), category(String), uncategorized }`。`List` 分两个 `Section`：状态筛选一段，分类一段；分类段末尾固定是「未分类」。

拖放用 SwiftUI 的 `.draggable(episodeID)` 加分类行上的 `.dropDestination(for: String.self)`。分类排序用分类 Section 里 `ForEach` 的 `.onMove`。

**Rationale**: macOS 14+ 的 `List(selection:)` 支持任意 `Hashable` 作为选中值，也支持分 Section。「邮件」「备忘录」都是这个模式。

**Alternatives considered**: 保留 `Filter` 并另开一个分类选中状态，两个状态会互相打架（同时选中「已完成」和「投资」时，列表该显示什么？）。否决。

## 7. 新增依赖

**无。** 后端用现有的 SQLAlchemy、alembic、pydantic、LLM client；客户端只用 SwiftUI / Foundation。
