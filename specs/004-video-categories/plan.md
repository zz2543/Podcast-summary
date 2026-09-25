# Implementation Plan: 视频分类（手动为主，AI 按需整理）

**Branch**: `002-macos-native`（同 003，未单独开分支） | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-video-categories/spec.md`

## Summary

在 macOS 客户端侧边栏的状态筛选下面加一个「分类」小节，像文件夹一样手动整理视频，每条视频最多一个分类。分类和归属存在后端 SQLite 里：新表 `category`，`episode` 上加三列。

「AI 分类」是用户按需触发的后台运行，分两阶段调用现有 LLM client：

1. 先定分类表；
2. 再分批给视频归类。

结果以方案的形式交给客户端预览，用户编辑后通过无状态的 apply 接口一次写入。服务端在 apply 时硬性跳过手动锁定的视频和已被改动的视频。新视频总结完成时**不会**触发任何分类。

## Technical Context

**Language/Version**: 后端 Python 3.11+；客户端 Swift 5.9 / SwiftUI（macOS 14+，002 已确立）
**Primary Dependencies**: FastAPI、SQLAlchemy 2 + alembic、pydantic（后端现有）；SwiftUI、Foundation（客户端）。**无新增依赖**。
**Storage**: 现有 SQLite `data/podsum.sqlite3`；迁移 `0005_categories`
**Testing**: pytest（`make test`，domain 覆盖率门槛 80%）；客户端用 `design-check` 离屏渲染 + fakeroot 手动验收
**Target Platform**: macOS 14+ 桌面 app + 本机 loopback 后端
**Project Type**: 桌面客户端 + 本地 Web 服务
**Performance Goals**: 手动操作即时生效（本机单次请求 < 100 ms）；AI 分类 200 条内 ≤ 2 分钟（SC-004），31 条预计 < 30 秒
**Constraints**: AI 结果在确认前零写入（SC-003）；手动锁定被 AI 改动 0 次（SC-002），由服务端保证
**Scale/Scope**: 单用户；当前 31 条，设计上限 200+ 条；分类通常 < 30 个

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|---|---|---|
| I. 英文交付优先 | ✅（沿用现状） | 代码注释、提交信息用英文；UI 文案走 `tr(中, 英)`。spec 和 plan 与 001–003 一致使用中文，这是项目现行做法 |
| II. Python 优先 | ✅ | 后端全部 Python。Swift 客户端是 002 已经确立的前提，本特性不新增语言 |
| III. 领域逻辑测试 ≥ 80% | ✅ 计划中 | 新增 `domain/categorizer.py`，负责 prompt slot 组装、LLM 输出解析、名字规范化、方案 diff，全部是纯函数，配 `tests/unit/test_categorizer.py` |
| IV. 配置外置 | ✅ | 批大小、新分类上限、摘要截断长度进 `Settings`，同步 `.env.example`：`CATEGORIZE_BATCH_SIZE=40`、`CATEGORIZE_MAX_NEW=5`、`CATEGORIZE_MAX_INITIAL=10` |
| V. Prompt 版本化 | ✅ | `prompts/category_taxonomy.v1.md`、`prompts/category_assign.v1.md`，经 `PromptAssembler` 引用；`find_inline_prompt_violations` 会检查不内联 |
| SDD：选型 ≥ 2 候选 | ✅ | research §1（调用策略 4 个）、§2（存储 4 个）、§3（运行传递 3 个） |
| SDD：新依赖登记 | ✅ | 无新依赖 |

**Post-design re-check**：Phase 1 的产出（data-model、两份契约）没有引入新语言、新依赖或内联 prompt，仍然全部通过。

## Project Structure

### Documentation (this feature)

```text
specs/004-video-categories/
├── spec.md
├── plan.md               # 本文件
├── research.md           # 选型与事实基础
├── data-model.md         # category 表、episode 新列、状态转换
├── quickstart.md         # 验证步骤
├── contracts/
│   ├── http-api.md       # 分类 CRUD、归属、AI 运行、apply
│   └── llm-output.md     # 两个 prompt 的 slot 与输出解析规则
└── checklists/requirements.md
```

### Source Code

```text
prompts/
├── category_taxonomy.v1.md          # 新增
└── category_assign.v1.md            # 新增

backend/src/podsum/
├── persistence/
│   ├── models.py                    # + Category；Episode + category_id / category_origin / category_updated_at
│   ├── repo.py                      # + CategoryRepo（CRUD、排序、删除时清归属、计数）；EpisodeRepo 设置 / 释放归属
│   └── migrations/versions/0005_categories.py
├── domain/
│   └── categorizer.py               # 新增：name_key、摘要构造、slot 渲染、解析、方案 diff、apply 规则判定
├── services/
│   └── categorize.py                # 新增：CategorizeRunner（内存运行态、两阶段、to_thread 调 LLM、取消）
├── api/
│   ├── categories.py                # 新增：/api/categories*、/api/categorize*、/api/categories/apply
│   └── episodes.py                  # 摘要 / 详情加 category 字段；PUT …/category、POST …/category/release
├── config.py                        # + CATEGORIZE_* 设置
└── main.py                          # include categories.router；app.state.categorize_runner

backend/tests/
├── unit/test_categorizer.py
├── integration/test_categories_api.py
└── integration/test_categorize_run.py   # 假 LLM：两阶段、部分失败、取消、409、锁定跳过

specs/001-podcast-summary/contracts/http-api.md     # 增加指向 004 契约的一节
specs/002-macos-native/contracts/PodsumModels.swift # + Category、CategoryOrigin、CategorizeRun、Proposal；EpisodeSummary + category

macos-client/Podsum/
├── Data/
│   ├── EpisodeRepository.swift      # 协议 + MockRepository：分类 CRUD、setCategory、release、categorize、apply
│   ├── LiveRepository.swift         # 对应 HTTP 实现
│   └── CategoryStore.swift          # 新增：@Observable，持有分类列表与计数，负责轮询 AI 运行
└── Views/
    ├── EpisodeListView.swift        # Filter → SidebarSelection；分类 Section；拖放目标；onMove 排序；按分类过滤
    ├── EpisodeCard.swift            # .draggable(episode.id)；AI 管理的视频显示一个很淡的标记
    ├── EpisodeDetailView.swift      # 分类选择 + 来源（手动 / AI）
    ├── CategoryViews.swift          # 新增：新建 / 改名弹窗、删除确认、右键「移到分类 ▸」子菜单
    └── CategorizeSheet.swift        # 新增：进度 → 预览（分组、勾选、改名、整组拒绝）→ 应用
```

**Structure Decision**: 沿用 002/003 的结构：后端的数据、领域、服务、接口四层各加一个文件，客户端的 Data 层和 Views 层各加文件。纯逻辑都放进 `domain/categorizer.py`，一是满足宪法 III，二是让 `services/categorize.py` 只剩编排。

## 关键设计

### 后端：一次 AI 运行（`services/categorize.py`）

```
POST /api/categorize
  └─ 快照：参与视频（未分类、未被手动移出、有 hook）+ 当前分类表
     └─ task: 阶段 A  taxonomy  (1 次 LLM)  → 分类表 = 已有 ∪ 新提议
              阶段 B  assign    (⌈n/40⌉ 次) → 每条 → key | null
              建议 → proposal（只会把未分类视频放进分类，不挪动已分类的）
GET  /api/categorize/{id}  ← 客户端每 1 s 轮询
POST /api/categories/apply ← 用户编辑后的结果；一个事务，逐条检查锁定 / 变更
```

- 快照在启动时一次读完，之后的 LLM 调用不再碰数据库。运行期间用户的改动由 apply 时的检查兜住。
- `complete_json` 用 `asyncio.to_thread` 调用。每批调用前检查取消标记，已发出的调用跑完后丢弃结果。
- 运行态存在 `app.state.categorize_runner`，最多一个 running，结束的 run 保留最近 1 个。

### 客户端：选中模型与刷新

- `SidebarSelection = .status(Filter) | .category(id) | .uncategorized`，取代 `Filter` 作为 `List` 的选中值。
- 分类计数来自 `GET /api/categories`，不在客户端数，因为列表最多 200 条。任何归属变更后，重新拉一次分类，并在本地更新那一条视频的 `category`，列表不用整页重载。
- 右键菜单在现有的 `menu(for:)`（`EpisodeListView.swift:216`）里加三项：「移到分类 ▸」「移出分类」「交给 AI 分类」。最后一项只对被手动移出、留在未分类的视频显示。
- 「AI 分类」按钮放在侧边栏「分类」小节标题的右侧，运行中不可用。预览是 sheet：
  - 顶部是进度和取消；
  - 完成后按分类分组，每条前面一个勾选框，新分类的名字可以直接编辑，每组有「不要这个分类」；
  - 底部写「将改动 N 条 · 跳过 M 条（原因）」，右边是「应用」和「取消」按钮。
- apply 返回的 `skipped` 非空时，用一行说明告诉用户哪些没应用、为什么。

### 为什么删除分类会解除锁定

见 [data-model.md](data-model.md)「状态转换」。用户删了分类，手动放在里面的视频如果还保持锁定，就会永远留在「未分类」、AI 也碰不到，这不符合预期。

## 实施顺序（供 /speckit-tasks 拆分）

1. **P1 · Story 1 + 2（手动分类，MVP）**
   1. 后端：迁移、模型、`CategoryRepo`、`categorizer.name_key`、分类 CRUD / 排序 / 归属接口、列表和详情加字段。补齐测试。
   2. 客户端：契约模型、Repository、`CategoryStore`、侧边栏 Section、拖放、右键、详情页、新建 / 改名 / 删除 UI。
2. **P2 · Story 3（AI 分类）**
   1. prompts 两份、`categorizer` 的解析和 diff、`CategorizeRunner`、运行和 apply 接口、测试（假 LLM）。
   2. 客户端 `CategorizeSheet`。
3. **P3 · Story 4**：release 接口（可以在 1.1 里一起做）、右键「交给 AI 分类」、来源标记。
4. 文档：001 的 http-api 加一节指向 004；002 的 `PodsumModels.swift` 契约同步；quickstart 的手动验收清单。

## Risks

| 风险 | 缓解 |
|---|---|
| 库高度集中在 AI 编程，模型给出「AI / 科技」一个大类，分类失去意义 | taxonomy prompt 明确要求切开，不让一类超过一半；SC-005 用真 LLM 抽查一次（quickstart §4，需用户同意后跑） |
| LLM 抄错 26 位 ULID | 批内短编号 `e1…`、`c1…`，解析时映射回真实 id |
| SQLite 外键没生效，删分类留下悬空 `category_id` | `CategoryRepo.delete` 在同一事务里显式清空；集成测试覆盖 |
| `summary_artifact` 有孤儿行 | 参与资格从 `episode` 出发 join，不扫 `summary_artifact` |
| 预览期间后端重启，run 丢失 | apply 是无状态的，手里的方案照样能应用；轮询拿到 404 时提示重新运行 |

## Complexity Tracking

无违反项。

---

## 实现记录（2026-09-24）

### 实现中的规则调整（用户要求）

**AI 分类只处理还没有分类的视频**：放进已有分类，或放进它提议的新分类。已在分类里的视频，不论是谁放的，都不再参与，也就没有「挪动」。
这取代了 spec 澄清里「AI 放过的视频也重新考虑」的答复。spec（US3 场景 7、US4、FR-009/010/011/012/014/017/019、SC-002）、data-model、contracts 都已同步。连带的变化有三处：
- 方案里去掉 `kind` / `unchanged_count` / `from_category_id`，`skipped` 新增 `categorized`；
- 「锁定」只剩一种情况：被手动移出、留在未分类的视频；
- 「交给 AI 分类」只对这种视频有意义，界面也只在这时提供。

### 与 tasks.md 写法不同的地方

| 项 | 实际做法 | 原因 |
|---|---|---|
| Swift 类型名 | `EpisodeCategory`，不是 `Category` | ObjectiveC 运行时有 `typealias Category`，同名会撞 |
| 手动归类 / 解锁 | `CategoryRepo.set_manual` / `release`，不在 `EpisodeRepo` 上 | 与删除分类时清归属的逻辑放在一起，都用保留 `episode.updated_at` 的 Core UPDATE：归类不算剧集本身的更新 |
| `CategoryStore` | 由 `EpisodeListView` 持有，repository 按调用传入；在 `navigationDestination` 里的详情页上直接 `.environment(...)` | 后端就绪后 repository 会换；挂在 `NavigationStack` 外层时，推进来的详情页拿不到它（真机上看到的） |
| 拖放载荷 | `"podsum-episode:<id>"` 字符串 | 不必在 Info.plist 登记自定义 UTType，也不会把别处拖进来的任意文字当成 id |
| 菜单栏 | 新增「分类」菜单：新建分类…（⇧⌘N）、AI 分类… | 侧边栏分组标题会被 AX 合并成一个 heading，里面的两个小按钮对 VoiceOver 不可达；菜单栏给出键盘 / 辅助功能都能到的入口。标题也加了 `.accessibilityElement(children: .contain)` |
| `CategorizeSheet` | 固定 580×540 | macOS sheet 的尺寸按首次显示的状态（很矮的介绍页）定下，预览到来时不会长高，结果只露出中间的滚动区，标题和「应用」按钮都被裁掉（真机上看到的） |
| 迁移 0005 | batch 重建后补回 `idx_episode_created` 的 `DESC` | batch 模式反射索引时把 `DESC` 丢了（在真实库副本上比对 schema 发现） |
| `episode-output.schema.json` | 加了 `category` / `category_origin`（API only） | 详情响应要对照它校验，`test_us1_end_to_end` 因此失败过一次 |

### 已验证

| 项 | 结果 |
|---|---|
| 后端全套 `make test` 等价命令 | 262 passed，domain 覆盖率 93.6%；`domain/categorizer.py` 99% |
| `ruff check` | 通过 |
| 迁移：真实库副本 upgrade → downgrade → upgrade | 31 条完好，`integrity_check` ok，索引与原来一致 |
| 客户端 Debug 编译 | 通过，新文件无警告 |
| 真机（隔离副本 `PodsumVerify.app` + fakeroot 后端 + 按关键词作答的假 LLM，端口 8765；不碰真数据、真钥匙串、真 API 额度） | 见下 |
| · 侧边栏「分类」小节、「未分类」计数 | 正常，和系统侧边栏风格一致 |
| · 新建分类：空名时按钮置灰、保留名「未分类」当场提示 | 正常 |
| · 把卡片拖到侧边栏分类上 | 写入 `manual`，计数即时更新 |
| · AI 分类：介绍 → 进度（拟定分类 / 归类 n/m）→ 预览 | 正常 |
| · 预览里取消一条、改新分类名、整组拒绝 | 条数 13 → 11，被拒的组变灰可「恢复」；应用后改过的名字生效，被拒的分类没有创建，合计 31 条 |
| · 规则调整后：已在分类里 14 条不参与；未分类里的 2 条被放回已有「Claude Code」，没有新建同名分类 | 正常 |
| · 关闭 / 取消预览 | 库没有任何变化 |
| · 卡片上的分类标签（你放的📁 / AI 放的✨）、详情页分类行 | 正常（详情页那一行是修了环境注入后才出现的） |

### 未验证 —— 需要在真机上手动过一遍

后台自动化只能走 AX，而右键菜单、下拉菜单、侧边栏行的拖动排序在后台都打不开；全屏点击又被程序坞的浮层挡住。所以下面这些没有实际点过：

- [ ] 卡片右键：「移到分类 ▸」（当前所在打勾）、「移出分类」、对移出的视频「交给 AI 分类」
- [ ] 分类行右键：重命名（与别的分类重名时的提示）、删除确认文案
- [ ] 拖动分类行排序，重启后保持
- [ ] 详情页分类下拉菜单切换分类，返回列表后卡片同步
- [ ] 侧边栏标题里的 ✨ 和 ＋ 用鼠标点（AX 下只能按到合并后的 heading）
- [ ] 选中分类时搜索只在分类内
- [ ] 亮色外观
- [ ] 用真 LLM 在复制的库上跑一次、只看方案（T045，会产生少量费用，需要你同意）
