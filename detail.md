# 播客总结系统 detail.md

> 本文件从实现阶段开始持续追加，用于记录实现日志、设计取舍、踩坑记录、性能数据与评估结果。

## 实现日志

- 2026-05-07：完成项目基础目录、后端/前端工具链与运行入口的初始化任务。
- 2026-05-07：完成后端核心链路：配置读取、SQLAlchemy 模型、Alembic 初始迁移、Repository、FastAPI app、WebSocket 进度广播、prompt loader、ASR/LLM/TTS adapter、pipeline 状态机与重启恢复。
- 2026-05-07：完成 US1：本地文件/直链/YouTube ingest，Doubao ASR、DeepSeek LLM、转写后处理、一句话摘要、三段式摘要、Markdown/JSON 导出、episode/job API、前端列表页与详情页。
- 2026-05-07：完成 US2：章节切分、章节 payload parser、quote verifier、实体抽取、pipeline 章节/quote/entity stage、Markdown/JSON 深度导出、章节跳转组件、实体面板、Range 请求验证与 quote verifier CLI。
- 2026-05-07：完成 US3：Doubao/Qwen TTS adapter、音频摘要脚本、懒触发 TTS pipeline、digest API、失败降级测试与前端音频摘要控件。
- 2026-05-07：完成 US4：SQLite 持久队列 + `asyncio.Queue` + `Semaphore(MAX_CONCURRENCY)`，batch API，前端 batch 提交，以及并发上限集成测试。
- 2026-05-07：完成交叉验证：CI workflow、coverage gate、RUN_SMOKE 门控的 smoke 脚本。
- 2026-05-12：根据用户确认，T079 的 5 集人工评估不作为本次交付门槛；保留自动化验证与生产模式构建验证作为收口标准。
- 2026-09-10：完成 FR-027 有用性评分（Phase 8 / T081–T090）：`usefulness_score.v1` prompt、`domain/usefulness_scorer.py`、`parse_usefulness`、迁移 `0003_usefulness_score`、pipeline 可选阶段、Markdown/JSON 导出、`?band=/?min_score=/?sort=` 列表参数，以及 `frontend` 与 `frontend-v2` 两个 SPA 的评分徽章与详情页评分卡。
- 2026-05-12：完成 T080 生产模式验证：`make build` 成功，`make serve` 由 FastAPI 单独服务 SPA；`/`、`/episodes/test-id`、`/api/health`、`/assets/index-*.js` 均返回 200。

## 设计取舍

- **默认云服务栈**：ASR/TTS 采用火山引擎 Doubao，LLM 采用 DeepSeek；Qwen、Anthropic、Whisper 等作为可切换 fallback。这样满足中文/英文播客场景，同时避免把 OpenAI 账号作为默认必需项。
- **SQLite + 文件系统**：数据库保存 episode/job/segment/chapter/quote/entity/artifact 元数据，音频、转写原始响应、Markdown/JSON/TTS 文件落在 `data/<episode_id>/`。单用户本地工具不引入对象存储，删除语义也更直接。
- **prompt 集中管理**：所有 LLM prompt 放在 `prompts/*.v1.md`，代码只按文件名和版本加载，避免业务代码里散落长 prompt。
- **quote 防御策略**：LLM 只能提出 candidate quote，最终持久化必须经过 `quote_verifier`，JSON 导出再次过滤 `verified=True` quote，形成双层防御。
- **并发模型**：job 仍以 SQLite 中 `queued` 状态为事实来源，内存 `asyncio.Queue` 只是运行期缓存；pipeline 在关键状态/进度 checkpoint 后立即 commit，避免 SQLite 长事务导致并发写锁。
- **评分只由模型给分，分档由代码决定**（FR-027）：LLM 只返回 `score` 和一句 `rationale`，`must_listen / worth_listening / skimmable / skippable` 四档由 `band_for()` 按分数区间确定性映射。否则同一个 78 分在不同集会被模型标成不同档，列表页的分档筛选就失去意义。
- **越界分数重试而非截断**：`parse_usefulness` 对 101、-1、78.5、"78" 一律抛 `RetriableValidationError`。把 140 悄悄改成 100 等于替模型编了一个它没给出的评分。
- **评分不吃摘要风格**：`summary_style` 指令注入 hook / 三段式 / 章节三个 prompt，但**不注入**评分 prompt——风格决定摘要怎么写，不该决定这集值多少分。
- **评分是可选阶段**：失败后整集降级为 `partial` 而不是 `failed`，其余摘要照常可读可下载；重跑失败时会把上一轮的三列一起清空，避免屏幕上留着一个已经不成立的旧分数。
- **未评分 ≠ 0 分**：接口对未评分返回 `usefulness: null`（不是 0 也不是各字段为 null 的对象），前端渲染「未评分」；`?band=` 筛选会直接排除未评分节目，因为没有一个诚实的桶可以放它们。
- **前端文案**：原 `ui-brief.md` 要求中文 UI，但用户确认最终界面使用英文；实现保持 spec 文件不变，只在代码中采用英文界面文案。

## 踩坑记录

- **新增 pipeline 阶段打乱了集成测试的 mock 顺序**：`test_us1_end_to_end` / `test_summary_style_flow` 用 `side_effect` 列表按阶段顺序喂 LLM 响应，在三段式和章节之间插入评分阶段后，章节响应被评分阶段吃掉。已在这些测试里按新顺序补上评分响应；`test_us1_resume` 用 schema 分发，只需加一个 `score` 分支。
- **迁移号被占用**：文档里原本写的 `0002_usefulness_score` 与 codex 已落地的 `0002_episode_summary_style` 冲突，实际实现为 `0003_usefulness_score`。
- **SQLite 无法给已有表补 CHECK**：`usefulness_score BETWEEN 0 AND 100` 等约束只在新建库时生效；已迁移的库靠 `parse_usefulness` + `band_for` 这两个唯一写入口保证不变量。
- **设计图命名不一致**：tasks.md 期待 `selected/list-page.png` 等文件，实际用户提供的是 `selected/前端设计图.png` 合并图。经用户确认后，按该合并图作为视觉参考继续实现。
- **coverage gate 与分步任务冲突**：新增领域模块后，在配套测试任务落地前会短暂拉低 domain coverage。处理方式是立即进入相邻测试 task，测试通过后再分别提交实现与测试 commit。
- **SQLite 并发写锁**：并发测试中发现 pipeline 在 ASR sleep 期间持有写事务，导致其它 job 更新状态时报 `database is locked`。修复为状态与进度 checkpoint 后立即 commit。
- **JSON/Markdown 共用 detail 对象**：Markdown 需要 DB chapter objects 后，旧 JSON exporter 无法序列化对象。先做兼容保护，再在 T058 实现完整 chapters/entities JSON 序列化。
- **前端路由依赖收敛**：为避免新增未在计划登记的路由库，前端使用轻量 history/popstate 路由，而不是引入 React Router 或 wouter。

## 性能数据

- 当前已验证的是自动化测试耗时，不代表云端真实吞吐：
  - `make test`：63 个 backend tests 通过，domain coverage 87.98%。
  - `make lint`：ruff + TypeScript lint 通过。
  - `make test-frontend`：Vitest 无测试文件，按 `--passWithNoTests` 通过。
  - `make verify-quotes`：seeded fixture 结果 `PASS 1 / FAIL 0`。
  - `make build`：Vite 生产构建通过，生成 `frontend/dist/index.html`、JS、CSS。
  - `make serve`：FastAPI 生产模式单独服务构建后的 SPA，根路径、详情页 fallback、API health 与静态 JS 均验证通过。
- 待实测：Apple M2 上 60 分钟真实播客样本的 ASR、LLM、TTS 分阶段耗时。

## 评估结果

- 自动化可量化结果：
  - SC-003 quote seek 后端时间戳：`test_us2_quote_jump_math.py` 验证 `start_ms=90000` 原样进入 JSON。
  - SC-004 quote verifier：`scripts/verify_quotes.py` 可离线复查所有 `verified=True` quote；fixture 当前 100% 通过。
  - SC-007 resume：`test_us1_resume.py` 验证重启恢复后复用已持久化 transcript，避免重复 ASR。
  - FR-018 concurrency：`test_us4_concurrency.py` 验证 `MAX_CONCURRENCY=2` 时 `transcribing` job 数量从未超过 2。
- 人工/真实云评估：
  - T079 的 5 集中英文人工评分已由用户明确跳过，本次不再补正式分数。
  - 后续若需要面向课程/展示补证据，可另行跑 SC-001、SC-002、SC-005 与 60 分钟性能样本。
