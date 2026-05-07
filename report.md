# 播客总结系统报告

> 本文件从实现阶段开始持续更新，是面向评审者的精炼项目报告。

## 项目概览

本项目实现了一个单用户、本地回环访问的播客总结系统。用户可以提交本地音频、直链音频或 YouTube 链接，系统完成转写、结构化总结、章节拆分、原文引用校验、实体统计、Markdown/JSON 导出，并支持按需生成音频摘要。

系统默认云服务组合为火山引擎 Doubao ASR、DeepSeek LLM 与火山引擎 Doubao TTS，同时保留 Qwen、Whisper、Anthropic 等可配置 fallback。运行形态面向本地 demo 与个人使用：FastAPI 后端绑定 `127.0.0.1`，SQLite 保存结构化数据，`data/<episode_id>/` 保存音频和导出文件。

## 用户与场景

目标用户是需要高频筛选播客内容的学习者或研究者。核心场景有三类：

- **快速判断是否值得听**：通过一句话 hook 和三段式摘要先判断价值。
- **深入复盘重点内容**：在详情页查看章节、要点、可跳转 quote 和实体列表。
- **沉浸式回听**：对已处理的单集生成 TTS 音频摘要，用碎片时间复习。

更完整的实现日志、踩坑记录和评估明细见 [detail.md](detail.md)。

## 核心实现摘要

| 模块 | 已实现能力 | 说明 |
| --- | --- | --- |
| 输入与持久化 | 本地文件、直链、YouTube、批量提交 | 上传前后执行格式与时长/大小限制；metadata 写入 SQLite。 |
| Pipeline | 可恢复任务状态机、并发队列、阶段降级 | required stage 失败则 job failed；optional TTS/entity 失败可降级继续。 |
| 摘要生成 | hook、三段式摘要、章节 outline | Prompt 文件集中在 `prompts/`，代码只引用 prompt role/version。 |
| 引用校验 | candidate quote 必须逐字命中 transcript | Repository 写入和 JSON 导出各做一层 verified 防御。 |
| 实体统计 | people/books/products 分类与计数 | LLM 只给候选，最终 count 由 transcript 重扫确定。 |
| 导出与回放 | Markdown、JSON、原音频 Range、TTS digest | quote timestamp 驱动前端 `<audio>` seek；digest 按需生成。 |
| 前端 | English SPA 列表页、详情页、batch、digest 控件 | 参考用户提供的 `design/selected/前端设计图.png`，界面文案按用户确认使用英文。 |

## 评估结果与图表

当前已完成自动化验证，真实 5 集中英文评估仍是 T079 的待执行项，未在本报告中伪造分数。

| 验证项 | 结果 | 含义 |
| --- | --- | --- |
| Backend tests | 60 passed | 覆盖 domain、pipeline、API、并发、digest 等关键路径。 |
| Domain coverage | 88.03% | 高于 constitution 要求的 80% coverage gate。 |
| Backend lint | passed | `ruff` 通过。 |
| Frontend check | passed | `tsc --noEmit` 与 Vitest 空测试通过。 |
| Quote verifier fixture | PASS 1 / FAIL 0 | `make verify-quotes` 可复查 DB 中 quote。 |
| Range endpoint | 206 verified | 支持音频局部加载，服务 quote 跳转体验。 |
| Concurrency | max 2 transcribing jobs | `MAX_CONCURRENCY=2` 时并发上限生效。 |

```text
Domain coverage
88.03% | ##############################------ | target 80%

Quote verification fixture
PASS   | # | 1
FAIL   |   | 0

MAX_CONCURRENCY=2
observed transcribing jobs <= 2
```

已覆盖的成功指标：

- SC-003：quote timestamp 能按毫秒值进入 JSON，前端据此 seek。
- SC-004：所有持久化 quote 可由 CLI 复查，失败时命令返回非零。
- SC-007：重启恢复复用已完成 transcript，避免重复 ASR。
- FR-018：批量任务遵守配置并发上限，单个失败不阻塞队列继续。

待补充的真实评估：

- SC-001：5 集真实播客的章节/要点人工准确率。
- SC-002：中文与英文内容的同语言摘要质量。
- SC-005：真实 TTS 音频摘要的可听性与覆盖度。
- M2 设备上 60 分钟样本的 ASR、LLM、TTS 分阶段耗时。

## 未来工作

- 补齐 T079 的 5 集中英文真实评估集，并把人工评分写回 [detail.md](detail.md) 与本报告。
- 增加前端 Vitest/Playwright 覆盖，特别是 batch submission、quote seek、digest retry 等交互。
- 为 Doubao ASR/TTS 增加真实云端 smoke fixture 与失败样例库，降低 provider API 变化带来的回归风险。
- 增加可配置 prompt version migration，让历史 episode 可明确知道由哪个 prompt 版本生成。
- 在单用户本地范围内加入更细的 job 观察面板，例如每个阶段耗时、重试次数与降级原因。
