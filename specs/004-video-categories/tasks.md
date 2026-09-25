---
description: "Task list for 004 video categories"
---

# Tasks: 视频分类（手动为主，AI 按需整理）

**Input**: `specs/004-video-categories/`（plan.md、spec.md、research.md、data-model.md、contracts/、quickstart.md）
**Tests**: 包含。宪法 III 要求 `domain/` 行覆盖率 ≥ 80%（`make test` 的 `--cov-fail-under=80`）；后端接口另有集成测试。客户端按 002/003 惯例，用 `design-check` 离屏渲染加手动验收，不写 XCTest。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件，不依赖未完成的任务）
- **[Story]**：所属用户故事（US1–US4，对应 spec.md）

## 全局约定（每个任务都适用）

- 后端测试命令：`. .venv/bin/activate && PYTHONPATH=backend/src pytest <path> -q`（在仓库根目录执行）。
- 集成测试照 `backend/tests/integration/test_duplicate_link.py::_app_with_episode` 的写法：用 `Base.metadata.create_all` 建临时库，`create_app(Settings(_env_file=None, …假凭据…))`，用 `TestClient` 调接口。假 LLM 挂到 `app.state.llm_client`，参考 `test_us4_concurrency.py:58`。
- 客户端**新增** `.swift` 文件后，要在 `macos-client/` 里执行 `python3 gen-project.py` 重新生成工程。契约 `specs/002-macos-native/contracts/PodsumModels.swift` 会被编进 app。
- UI 文案一律用 `tr("中文", "English")`。代码注释用英文（宪法 I）。
- 错误响应沿用 `api/episodes.py::_api_error`，错误体形状为 `{"error": {code, message, details}}`。
- SQLite 外键**没有**生效（research §0）。凡是涉及归属清理的，都要在 repo 里显式写。

---

## Phase 1: Setup

- [x] T001 在 `backend/src/podsum/config.py` 的 `Settings` 中加 `CATEGORIZE_BATCH_SIZE: int = Field(default=40, ge=5, le=100)`、`CATEGORIZE_MAX_NEW: int = Field(default=5, ge=0, le=20)`、`CATEGORIZE_MAX_INITIAL: int = Field(default=10, ge=3, le=20)`，并在 `.env.example` 末尾加一段带英文注释的对应条目（宪法 IV）。

---

## Phase 2: Foundational（所有故事的前提）

- [x] T002 在 `backend/src/podsum/persistence/models.py` 中新增 `Category` 模型，字段、约束和索引见 data-model.md：`id` ULID，`name`，`name_key` UNIQUE，`position`，`origin` CHECK IN (`user`, `ai`)，`created_at`/`updated_at`，索引 `idx_category_position`。在 `Episode` 上加 `category_id`（String(26)，`ForeignKey("category.id")`，nullable）、`category_origin`（String(8)，CHECK IN (`manual`, `auto`) 或 NULL，写进 `Episode.__table_args__`）、`category_updated_at`（DateTime(tz)，nullable），以及索引 `idx_episode_category`。再加只读关系 `Episode.category`（`relationship(lazy="joined")`，不做级联）。
- [x] T003 新建迁移 `backend/src/podsum/persistence/migrations/versions/0005_categories.py`（`down_revision = "0004_detail_and_key_moments"`）：
  - `upgrade`：先 `op.create_table("category", …)`；再用 `op.batch_alter_table("episode")` 加三列、CHECK 约束和索引（SQLite 需要 batch 模式）。
  - `downgrade`：按相反顺序删除。
  - 表头 docstring 与 0004 格式一致。
- [x] T004 [P] 新建 `backend/src/podsum/domain/categorizer.py`，先写名字相关的纯函数：
  - `normalize_display(name) -> str`：去首尾空格。
  - `name_key(name) -> str`：`unicodedata.normalize("NFKC", …).strip().casefold()`。
  - `RESERVED_KEYS = {"全部", "未分类", "all", "uncategorized"}`。
  - `validate_name(name) -> str`：返回规范后的显示名；不合法时抛 `CategoryNameError(reason)`，`reason ∈ {"empty", "too_long", "reserved"}`。上限 30 个字符，用 `len()` 按 Unicode 码点计数。
- [x] T005 [P] 新建 `backend/tests/unit/test_categorizer.py`，覆盖 T004 的全部分支：全角空格和全角字母的 NFKC 归一、大小写、首尾空格、恰好 30 字与 31 字、四个保留名（含大小写变体）、空串和纯空格。
- [x] T006 在 `backend/src/podsum/persistence/repo.py` 中新增 `CategoryRepo`：
  - `list_ordered()`；`counts() -> dict[category_id, int]`；`uncategorized_count()`（`episode.category_id IS NULL`）。
  - `get(id)`；`get_by_key(key)`。
  - `create(name, origin="user")`：`position = max + 1`；`name_key` 冲突时抛 `DuplicateCategory(existing_id)`。
  - `rename(id, name)`：与自己重名不算冲突。
  - `delete(id) -> int released`：同一事务里，先把该分类下全部视频设为 `category_id = NULL`、`category_origin = NULL`、`category_updated_at = now`，再删除分类。
  - `reorder(ids)`：`ids` 必须恰好是全部 id 的一个排列，否则抛 `ValueError`。

  并在 `EpisodeRepo` 中加：
  - `set_category_manual(episode_id, category_id | None)`：写入 `category_origin = "manual"`。
  - `release_category(episode_id)`：`manual` → 有分类时改为 `auto`，否则改为 NULL；不是 `manual` 时不做任何事。

  名字校验调用 T004。
- [x] T007 在 `backend/src/podsum/api/episodes.py` 的 `_episode_summary` 和 `_episode_detail` 中加 `"category": {"id", "name"} | None` 和 `"category_origin"`。数据从 `episode.category` 关系读取，避免逐条查询。
- [x] T008 [P] 在 `specs/002-macos-native/contracts/PodsumModels.swift` 中新增：
  - `Category`：`id`、`name`、`position`、`origin`、`episodeCount`，CodingKeys 为 snake_case。
  - `CategoryList`：`items`、`uncategorizedCount`。
  - `CategoryRef`：`id`、`name`。
  - `CategoryOrigin`：用 `Fallback`，取值 `manual` / `auto`。

  `EpisodeSummary`（以及 `EpisodeDetail`，如果它也有这些字段）加 `public var category: CategoryRef? = nil`、`public var categoryOrigin: Fallback<CategoryOrigin>? = nil`。老后端不发这两个键时要能解成 nil，写法同现有的 `hasCover`。
- [x] T009 在 `macos-client/Podsum/Data/EpisodeRepository.swift` 的 `EpisodeRepository` 协议中加以下方法，并在同文件的 `MockRepository` 里用内存数组实现：
  - `categories() async throws -> CategoryList`
  - `createCategory(name:)`、`renameCategory(id:name:)`
  - `deleteCategory(id:) async throws -> Int`
  - `reorderCategories(ids:) async throws -> CategoryList`
  - `setCategory(episodeID:categoryID:) async throws`
  - `releaseCategory(episodeID:) async throws`
- [x] T010 在 `macos-client/Podsum/Data/LiveRepository.swift` 中按 contracts/http-api.md 实现 T009 的方法。409 映射为现有的 `RepositoryError.conflict`，400 把 `message` 带出来，供 UI 显示。另外要确认 `PATCH` 和 `PUT` 能走现有的 `send(...)`，不能的话就扩展它。
- [x] T011 新建 `macos-client/Podsum/Data/CategoryStore.swift`：`@Observable @MainActor final class CategoryStore`，持有 `categories: [Category]`、`uncategorizedCount`、`lastError: String?`，提供 `refresh()` 和对 T009 各方法的包装（每次改动后都 `refresh()`）。在 `PodsumApp.swift` 创建它，注入环境的方式与 `QuickAddCenter` 相同。然后执行 `python3 gen-project.py`。

**Checkpoint**：`make test` 通过；把真实库复制一份，对副本执行 `alembic upgrade head`，然后 `downgrade -1`，再 `upgrade head`，都能成功（quickstart §2）；客户端能编译。

---

## Phase 3: User Story 1 — 像文件夹一样手动整理视频 (P1) 🎯 MVP

**Goal**：侧边栏出现「分类」小节，可以新建分类，用拖放、右键或详情页把视频放进分类，按分类筛选。

**Independent Test**：新建「投资」→ 把两条视频拖进去 → 点「投资」只看到这两条、数量显示 2，「未分类」减 2 → 重启 app 后依然如此。

- [x] T012 [P] [US1] 新建 `backend/tests/integration/test_categories_api.py`，覆盖：
  - `POST /api/categories`：201 且放在末尾；空名、31 字、保留名返回 400；`" 投资 "` 与「投资」重名返回 409，`details.category_id` 指向已有分类。
  - `GET /api/categories`：计数和 `uncategorized_count` 正确。
  - `PUT /api/episodes/{id}/category`：设置后 `category_origin == "manual"`；传 null 回到未分类但仍是 `manual`；视频或分类不存在返回 404，`details.missing` 正确。
  - `GET /api/episodes` 和 `GET /api/episodes/{id}` 带 `category` 字段。
  - 删除一条视频后，分类计数随之减少。
- [x] T013 [US1] 新建 `backend/src/podsum/api/categories.py`（`APIRouter(prefix="/api")`），实现 `GET /api/categories` 和 `POST /api/categories`；在 `backend/src/podsum/main.py` 中 `include_router`。
- [x] T014 [US1] 在 `backend/src/podsum/api/episodes.py` 中加 `PUT /api/episodes/{episode_id}/category`（body 为 `{"category_id": str | null}`），调用 `EpisodeRepo.set_category_manual`，返回 `{category, category_origin}`。
- [x] T015 [US1] 在 `macos-client/Podsum/Views/EpisodeListView.swift` 中：
  - 把 `List(selection:)` 的选中值从 `Filter` 改为新的 `enum SidebarSelection: Hashable { case status(Filter), category(String), uncategorized }`。
  - 侧边栏分两个 `Section`：状态筛选；「分类」。分类段里是各分类行（`folder` 图标 + `.badge(episodeCount)`），末尾是「未分类」（`tray` 图标）。Section 标题右侧放「＋」按钮。
  - `visible` 按选中项过滤；搜索只在当前选中范围内进行。
  - 副标题 `subtitle` 在选中分类时显示分类名。
- [x] T016 [P] [US1] 新建 `macos-client/Podsum/Views/CategoryViews.swift`，写 `CategoryNameField`：一个小的 popover 或 sheet，含输入框和「好 / 取消」按钮。输入时就在本地判断空、长度和保留名，提交后显示服务端的 409 或 400 文案。「新建分类」使用它。然后执行 `python3 gen-project.py`。
- [x] T017 [US1] 拖放：
  - `macos-client/Podsum/Views/EpisodeCard.swift`（或在 `EpisodeListView` 的卡片处）加 `.draggable(episode.id)`。
  - 在 T015 的分类行和「未分类」行上加 `.dropDestination(for: String.self)`，放下时调用 `CategoryStore.setCategory`，落到「未分类」就传 nil。成功后在本地 `episodes` 数组里更新这一条的 `category` 和 `categoryOrigin`，不整页重载。悬停时高亮目标行。
- [x] T018 [US1] 在 `EpisodeListView.swift` 的 `menu(for:)` 中加「移到分类 ▸」子菜单：列出全部分类，当前所在的打勾。视频有分类时，再加一项「移出分类」。
- [x] T019 [US1] 在 `macos-client/Podsum/Views/EpisodeDetailView.swift` 的元信息区加一个分类 `Picker`，选项为「未分类」加全部分类；改动后调用 `setCategory`，并通知列表刷新这一条（沿用现有的 `ui.refreshToken` 或回调方式）。
- [ ] T020 [US1] **（改为真机验证，见 plan.md「已验证」：ImageRenderer 画不了这些 AppKit 控件）** 在 `macos-client/design-check/main.swift` 中加一个场景：用 `PreviewFixtures` 构造 3 个分类的侧边栏，离屏渲染亮 / 暗两张 PNG 并查看效果。

**Checkpoint**：US1 独立可用、可演示。

---

## Phase 4: User Story 2 — 管理分类本身 (P1)

**Goal**：分类可以重命名、删除（确认后视频回到未分类）、拖动排序。

**Independent Test**：把「投资」改名为「理财」，视频都还在 → 删除「理财」，视频全部回到「未分类」，没有视频被删。

- [x] T021 [P] [US2] 在 `backend/tests/integration/test_categories_api.py` 中追加：
  - `PATCH`：200；与自己同名（大小写不同）返回 200；与别的分类重名返回 409；不存在返回 404。
  - `DELETE`：返回的 `released` 数量正确；其中手动锁定的视频 `category_origin` 变为 NULL（data-model「删除分类会解除锁定」）；视频本身仍在。
  - `PUT /api/categories/order`：合法排列返回 200 且顺序生效；缺 id、多 id、重复 id 都返回 400。
- [x] T022 [US2] 在 `backend/src/podsum/api/categories.py` 中实现 `PATCH /api/categories/{id}`、`DELETE /api/categories/{id}` 和 `PUT /api/categories/order`。注意路由顺序：`/categories/order` 要写在 `/categories/{id}` 之前。
- [x] T023 [US2] 在 `CategoryViews.swift` 和 `EpisodeListView.swift` 中给分类行加右键菜单：
  - 「重命名」：复用 T016 的 `CategoryNameField`。
  - 「删除」：弹 `confirmationDialog`，文案为「“理财”里的 5 条视频会回到「未分类」，视频本身不会被删除」。
  - 删除的若是当前选中的分类，选中项回到 `.status(.all)`。
- [x] T024 [US2] 在 `EpisodeListView.swift` 的分类 `ForEach` 上加 `.onMove`：先在本地重排，再调用 `reorderCategories`，失败时回滚并提示。「未分类」行不参与排序。

**Checkpoint**：US1 + US2 构成完整的手动分类 MVP。

---

## Phase 5: User Story 3 — 「AI 分类」，预览后一次整理好 (P2)

**Goal**：用户点「AI 分类」→ 看到进度 → 预览（可以取消单条、给新分类改名、拒绝整组）→ 应用。手动锁定的视频永远不会被改动。

**Independent Test**：20 条以上未分类视频 → 运行 → 在预览里取消 2 条、改一个新分类的名字 → 应用 → 只有保留的建议生效。

### 后端

- [x] T025 [P] [US3] 新建 `prompts/category_taxonomy.v1.md`：frontmatter 为 `role: category_taxonomy`、`version: v1`、`lang_aware: true`；slot 为 `{existing}`、`{episodes}`、`{min_new}`、`{max_new}`、`{lang}`。正文按 contracts/llm-output.md「阶段 A · Prompt 要点」用英文写，要求输出 JSON `{"new_categories":[{"name","reason"}]}`。格式参考 `prompts/usefulness_score.v1.md`。
- [x] T026 [P] [US3] 新建 `prompts/category_assign.v1.md`：`role: category_assign`、`version: v1`、`lang_aware: true`；slot 为 `{categories}`、`{episodes}`、`{lang}`。要求输出 `{"assignments":[{"episode","category"|null}]}`，并说明「都不合适就给 null，不要硬塞」。
- [x] T027 [US3] 在 `backend/src/podsum/domain/categorizer.py` 中追加纯逻辑：
  - **摘要**：`EpisodeDigest`（dataclass：`id`、`title`、`hook`、`chapter_titles`、`entities`、`current_category_id`、`origin`）；`short_line(d, n)` 和 `long_block(d, n)` 按 data-model「摘要文本的构造」截断，截断处加 `…`；`batches(items, size)`。
  - **slot 渲染**：`taxonomy_slots(existing_names, digests, *, max_new, min_new)` 和 `assign_slots(category_table, digests)` 返回 slot 字典，并附带短编号到真实 id 的映射。
  - **输出 schema**：`TaxonomyPayload`、`AssignPayload`（pydantic）。
  - **解析**：`parse_taxonomy(payload, existing_keys, max_new)` 和 `parse_assignments(payload, id_map, category_keys)`，全部规则见 contracts/llm-output.md，包括丢弃无效项、冲突的重复项、未知分类视为 null、未提及的记为 `no_suggestion`。
  - **方案**：`build_proposal(snapshot, suggestions, new_categories, failed_batches)` 生成 contracts/http-api.md 中 `proposal` 的 dict：列出每条建议，计算 `skipped`（`categorized` / `locked` / `no_summary` / `no_suggestion`），`categories` 只列被用到的。（2026-09-24 用户调整后不再有 `move` / `unchanged_count`。）
  - **应用判定**：`apply_decision(current_category_id, current_origin, from_category_id, episode_exists, target_exists) -> None | reason`。
- [x] T028 [P] [US3] 在 `backend/tests/unit/test_categorizer.py` 中追加 T027 的测试：
  - 截断边界；短编号映射；
  - llm-output.md 里每条解析规则各一例；
  - 空库时新分类为 0 → 抛出 `no_taxonomy`；
  - `skipped` 各项计数；
  - `apply_decision` 的五种结果。

  最后用 `pytest --cov=backend/src/podsum/domain/categorizer --cov-report=term-missing` 确认覆盖率 ≥ 80%。
- [x] T029 [US3] 新建 `backend/src/podsum/services/categorize.py`：
  - `CategorizeRun`（dataclass，字段见 data-model「内存中的运行态」）。
  - `CategorizeRunner(session_factory, settings, llm_factory, prompt_assembler)`，提供：
    - `start() -> run`：已有 running 时抛 `RunInProgress(run_id)`；参与视频为 0 时抛 `NothingToCategorize(reason)`。
    - `get(run_id)`；`cancel(run_id)`。
  - `start` 时一次性建快照：从 `episode` 出发 join `summary_artifact`、`chapter`、`entity`，条件是 `status IN ('done', 'partial')`、hook 非空、`category_origin` 不是 `manual`。**不要**扫孤儿 `summary_artifact` 行。
  - 后台 `asyncio.create_task` 依次跑阶段 A 和阶段 B。LLM 调用用 `await asyncio.to_thread(llm.complete_json, prompt, Schema)`，每批之前检查取消标记。单批出错记为失败批次后继续下一批。阶段 A 失败，或阶段 B 全部失败时，`state = failed`。
  - 只保留最近 1 个已结束的 run。
- [x] T030 [US3] 在 `backend/src/podsum/api/categories.py` 中加：
  - `POST /api/categorize`（202、409 带 `details.run_id`、400）、`GET /api/categorize/{run_id}`、`DELETE /api/categorize/{run_id}`。
  - `POST /api/categories/apply`：一个事务，先用 `validate_name` 和 `get_by_key` 处理 `new_categories`（同名复用；没有被任何 assignment 引用的不创建），再逐条用 `apply_decision` 判定并写入 `category_origin = "auto"`，返回 `created`、`applied`、`skipped`。

  在 `backend/src/podsum/main.py` 的 lifespan 中创建 `app.state.categorize_runner`，LLM 优先用 `app.state.llm_client`，没有时用 `create_llm_client(settings)`，与 `api/episodes.py:407` 的做法一致。退出时取消 running 的任务。
- [x] T031 [P] [US3] 新建 `backend/tests/integration/test_categorize_run.py`。假 LLM 根据 prompt 里的 role 返回固定 JSON，覆盖：
  - 两阶段走完拿到 `ready` 和正确的方案；
  - `manual` 视频不出现在方案里，计入 `skipped.locked`；
  - 没有 hook 的视频和孤儿 artifact 都不参与；
  - 已在分类里的视频（包括 AI 放的）不参与，计入 `skipped.categorized`（FR-019，2026-09-24 调整）；
  - 一批抛异常 → 仍是 `ready`，`failed_batches = 1`，该批视频计入 `no_suggestion`；
  - 阶段 A 抛异常 → `failed`；
  - 取消 → `cancelled`，库没有变化；
  - 运行中再次启动 → 409；参与视频为 0 → 400；
  - apply 的四种跳过原因、新分类同名复用、未被引用的新分类不创建、写入后 `category_origin == "auto"`；
  - SC-006：跑一遍现有 pipeline 测试夹具产出的新视频后，`category_id` 仍为 NULL。

  测试里通过轮询 `GET` 等待结束，设超时。
- [x] T032 [US3] 在 `specs/002-macos-native/contracts/PodsumModels.swift` 中加 `CategorizeRun`、`CategorizeProposal`（`ProposedCategory`、`ProposedChange`、`Skipped`）、`ApplyRequest`、`ApplyResult`，都用 snake_case CodingKeys。在 `EpisodeRepository` 协议、`MockRepository`（返回一份固定方案，状态先 running 再 ready）和 `LiveRepository` 中加 `startCategorize()`、`categorizeRun(id:)`、`cancelCategorize(id:)`、`applyCategorization(_:) -> ApplyResult`。
- [x] T033 [US3] 在 `macos-client/Podsum/Data/CategoryStore.swift` 中加 AI 运行状态机：`enum AIRun { idle, running(progress), preview(CategorizeProposal), applying, failed(String) }`。启动后每 1 秒轮询一次；轮询到 404 时显示「后端已重启，请重新运行」。提供 `cancelRun()` 和 `apply(edited:) -> ApplyResult`，应用后 `refresh()` 并通知列表重载。
- [x] T034 [US3] 新建 `macos-client/Podsum/Views/CategorizeSheet.swift`：
  - **运行中**：进度条（`done / total`）、阶段文案（「正在拟定分类…」「正在归类 2/3…」）和「取消」按钮。
  - **预览**：按分类分组。新分类的组头显示「新」标签、`reason` 和可编辑的名字（本地校验同 T016），以及「不要这个分类」按钮。每条视频前有勾选框。底部写「将改动 N 条 · 不会改动：已在分类里 a、被你移出 b、无总结 c、无合适分类 d」；`failed_batches > 0` 时加一行提示。
  - **应用后**：`skipped` 非空时列出原因再关闭；否则直接关闭。
  - 「取消」或关闭 sheet 时不发任何写请求（SC-003）。

  然后执行 `python3 gen-project.py`。
- [x] T035 [US3] 在 `EpisodeListView.swift` 的「分类」Section 标题右侧加「AI 分类」按钮（`sparkles` 图标，运行中 disabled，help 文案说明只在点击时运行），点击后弹出 `CategorizeSheet`。
- [ ] T036 [US3] **（同 T020，改为真机验证）** 在 `macos-client/design-check/main.swift` 中加 `CategorizeSheet` 预览态的离屏渲染（亮 / 暗），用 Mock 方案覆盖新分类和跳过提示。

**Checkpoint**：US3 在假 LLM 下端到端可用；SC-002、SC-003、SC-006 有自动化测试覆盖。

---

## Phase 6: User Story 4 — 让 AI 重新接管某条视频 (P3)

**Goal**：「交给 AI 分类」解除锁定；能看出一条视频是手动还是 AI 分的类。

**Independent Test**：手动把 A 放进「历史」→ 运行 AI 分类，A 不在方案里 → 对 A 选「交给 AI 分类」→ 再次运行，A 参与分类。

- [x] T037 [P] [US4] 在 `backend/tests/integration/test_categories_api.py` 中追加：`release` 把 `manual` 且有分类的视频改为 `auto`；把 `manual` 且在未分类的视频改为 NULL；对非 `manual` 的视频不做任何事；视频不存在返回 404。在 `test_categorize_run.py` 中追加：release 之后，这条视频会参与下一次运行。
- [x] T038 [US4] 在 `backend/src/podsum/api/episodes.py` 中加 `POST /api/episodes/{episode_id}/category/release`，调用 `EpisodeRepo.release_category`。
- [x] T039 [US4] 在 `EpisodeListView.swift` 的 `menu(for:)` 中，仅对 `categoryOrigin == .manual` 的视频显示「交给 AI 分类」。在 `EpisodeDetailView.swift` 的分类 Picker 旁显示来源：「手动 · 锁定」或「AI 管理」，旁边带一个「交给 AI 分类」小按钮。在 `EpisodeCard.swift` 上，对 `auto` 的视频在分类名旁显示一个很淡的 `sparkles` 标记（FR-012）。

---

## Phase 7: Polish & Cross-Cutting

- [x] T040 [P] 在 `specs/001-podcast-summary/contracts/http-api.md` 中加一节「Categories (feature 004)」，列出新端点，并链接到 `specs/004-video-categories/contracts/http-api.md`；在 `GET /api/episodes` 的响应形状中补上 `category` 和 `category_origin`。
- [x] T041 执行 `make test`：全套测试通过，domain 覆盖率门槛通过。
- [x] T042 按 quickstart §2 在真实库的副本上验证迁移的升级、降级、再升级，并确认 31 条剧集完好。
- [x] T043 按 quickstart §3 在 fakeroot 后端（端口 8765，假 LLM）上走一遍接口脚本，结果记入 plan.md 新增的「已验证」表。
- [x] T044 在 plan.md 末尾补「未验证 —— 需要在真机上手动过一遍」清单（照 003 的格式，内容取 quickstart §5）。
- [x] T045 **（2026-09-25 已跑，结果见 plan.md）**：按 quickstart §4，用复制的库和真 LLM 跑一次 AI 分类，只看方案不应用，把分类数、每类条数、耗时和需要改动的比例（SC-005）记入 plan.md。

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**：T002 → T003；T004 与 T005 可以和 T002/T003 并行；T006 依赖 T002 和 T004；T007 依赖 T002；T008 可以随时做；T009 → T010 → T011。
- **US1（Phase 3）** 依赖 Phase 2。**US2** 依赖 US1 的 T013、T015、T016（同一个路由文件、同一个侧边栏）。
- **US3** 后端（T025–T031）只依赖 Phase 2，可以和 US1/US2 的客户端工作并行；客户端（T032–T036）依赖 T015。
- **US4** 依赖 T006、T014、T018；可以在 US1 之后任何时候做。
- **Polish** 在所需的故事完成后进行。T045 要等用户明确同意。

```
Setup ─► Foundational ─┬─► US1 ─► US2 ─┐
                       │               ├─► Polish
                       ├─► US3(后端) ──┤
                       │      US1 ─► US3(客户端)
                       └─► US4（US1 之后）
```

## Parallel Examples

- **Phase 2**：T004 + T005（domain 和它的测试）‖ T008（Swift 契约）‖ T002 → T003（模型和迁移）。
- **US1**：T012（集成测试）‖ T016（名字输入组件）；T013 和 T014 分属两个文件，可以并行。
- **US3**：T025 ‖ T026（两份 prompt）‖ T028（单测，与 T027 边写边测）；T031 在 T029 和 T030 完成后进行。
- **跨故事**：US3 后端（T025–T031）‖ US2 客户端（T023–T024）。

## Implementation Strategy

1. **MVP = Phase 1 + 2 + US1 + US2**：完整的手动文件夹分类，不涉及 LLM。完成后先交给用户试用。
2. **加 US3**：AI 分类。先用假 LLM 把流程跑通，再在用户同意后用真 LLM 抽查一次质量（T045）。
3. **加 US4**：体量小，也可以和 US1 一起顺手做掉（T038 与 T014 在同一个文件）。
4. 每个 Checkpoint 都跑一次 `make test` 和客户端编译，不把问题带进下一个阶段。
