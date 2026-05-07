<!--
Sync Impact Report
==================
Version change: 0.0.0 → 1.0.0 (initial ratification)
Bump rationale: 首次正式批准项目宪法，建立 5 条核心原则 + 2 章附加约束 + 治理章节。
Modified principles: 无（首次创建）
Added sections:
  - Core Principles (I. 英文交付优先; II. Python 优先技术栈; III. 领域逻辑测试覆盖 (NON-NEGOTIABLE); IV. 配置外置化; V. Prompt 版本化集中管理)
  - 交付与文档约束 (Delivery & Documentation Constraints)
  - SDD 流程纪律 (Spec-Driven Development Discipline)
  - Governance
Removed sections: 无
Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (Constitution Check 区段为通用引用，无需修改)
  - ✅ .specify/templates/spec-template.md (无原则硬引用)
  - ✅ .specify/templates/tasks-template.md (无原则硬引用)
  - ✅ .specify/templates/constitution-template.md (作为模板源文件，未变动)
  - ⚠ README.md (建议补充对宪法的引用与一键启动脚本，待 feature 实施时落实)
  - ⚠ CLAUDE.md / AGENTS.md (建议在后续 feature 中加入对本宪法的硬引用)
Follow-up TODOs:
  - 无（所有占位符已填充）
-->

# 播客总结系统 Constitution

## Core Principles

### I. 英文交付优先

所有面向人类阅读的产出（报告、文档、代码注释、提交信息正文、CLI 用户提示）**必须**使用英文。

**Rationale**: 本项目为课程交付物，评审者使用英文阅读；统一语言可降低沟通成本并满足课程要求。

### II. Python 优先技术栈

主语言**必须**为 Python 3.11 或更高版本。任何引入非 Python 主进程语言的提议必须在 plan.md
的 Complexity Tracking 中显式说明并被批准；脚本类辅助工具（shell、Makefile）不在此限。

**Rationale**: 围绕 ASR、LLM 调用与文本结构化处理，Python 生态最成熟；统一语言收敛维护成本。

### III. 领域逻辑测试覆盖 (NON-NEGOTIABLE)

下列「领域逻辑层」**必须**配套 pytest 单元测试，行覆盖率 **≥ 80%**：
- 转写后处理（分段、清洗、说话人合并等）
- 摘要 prompt 组装
- 结构化输出解析（JSON/Schema 校验、错误恢复）

I/O 层（HTTP 请求、文件读写、模型推理调用）**允许**使用 mock，但其上游调用方仍须满足覆盖率门槛。
PR/合并前覆盖率不达标即视为违反宪法，需在 Complexity Tracking 中显式豁免方可合并。

**Rationale**: 领域逻辑是系统正确性的核心，回归成本高；I/O 层 mock 是为隔离外部不确定性。

### IV. 配置外置化

模型名、API Key、文件路径、阈值参数等运行时配置**必须**通过环境变量或 `.env` 文件读取，
**禁止**在源代码中硬编码任何具体凭证或部署相关常量。`.env.example` 必须随仓库提供并保持同步。

**Rationale**: 防止凭证泄漏、便于多环境切换，是安全与可移植性的最低门槛。

### V. Prompt 版本化集中管理

所有 LLM 调用使用的 prompt **必须**：
1. 存放于仓库根目录 `prompts/` 下，按用途组织文件；
2. 携带显式版本号（文件名内嵌版本，如 `summarize.v1.md`，或 frontmatter 中标注 `version`）；
3. 调用处只引用 prompt 文件，**禁止**将多行 prompt 字符串散落在业务代码内联书写。

**Rationale**: prompt 即提示工程的「源代码」，需可追溯、可对比、可回滚；散落 prompt 会导致回归与
A/B 评估失能。

## 交付与文档约束 (Delivery & Documentation Constraints)

- **一键启动**: 仓库根 `README.md` **必须**提供一键启动脚本（如 `bash run.sh` 或 `make run`），
  从干净检出到运行 demo 不得超过两条命令（含 `cp .env.example .env` 之类初始化步骤后）。
- **项目报告双文件**: 项目结束前**必须**产出两份中文报告并提交至仓库：
  - `detail.md`：保留实现细节、设计取舍、踩坑记录、性能数据等长篇内容；
  - `report.md`：面向评审者的精炼报告，从 feature 启动起即开始撰写，并随项目演进持续修订。
- **报告语言**: `detail.md` 与 `report.md` 使用中文（同 Principle I）。

## SDD 流程纪律 (Spec-Driven Development Discipline)

- **完整 SDD 流程**: 每个 feature **必须**依次走 spec → plan → tasks → implement，
  **禁止**跳过 spec 直接开始编码；紧急修复（hotfix）允许事后补 spec，但需在 PR 中显式声明。
- **关键技术选型 ≥ 2 候选**: ASR 模型、摘要策略、存储方案等关键选型必须在 `research.md`
  中列出**至少 2 个候选方案**及取舍理由（性能、成本、license、运维复杂度等维度）。
- **外部依赖登记**: 任何新增第三方依赖在引入前**必须**在 `plan.md` 中写明：
  1. **用途**（解决什么问题、能否被现有依赖替代）；
  2. **License**（确认与项目分发方式兼容）；
  3. **维护活跃度**（最近一次 release 时间、Issue 响应情况、Stars 等可观测指标）。

## Governance

- **最高效力**: 本宪法为项目最高规范，与其他文档冲突时以本宪法为准。
- **修订流程**: 任何修订须通过 `/speckit.constitution` 命令更新本文件，并在 PR 描述中说明：
  动机、变更摘要、版本号 bump 类型与影响面（含模板与文档同步状态）。
- **版本策略**: 遵循语义化版本：
  - **MAJOR**：移除/不兼容地重定义既有原则或治理条款；
  - **MINOR**：新增原则/章节，或对既有指引做实质性扩展；
  - **PATCH**：澄清措辞、修正笔误、不改变语义的细化。
- **合规审查**: 所有 PR 在 review 阶段必须核对本宪法对应原则；plan.md 的 Constitution Check
  门禁未通过不得进入 implement 阶段。豁免必须在 Complexity Tracking 中逐条记录并被显式批准。
- **运行时指引**: Agent 运行时指引以 `CLAUDE.md` / `AGENTS.md` 为准，二者不得与本宪法相悖。

**Version**: 1.0.0 | **Ratified**: 2026-05-07 | **Last Amended**: 2026-05-07
