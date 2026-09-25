# Data Model：视频分类

**Feature**: [spec.md](spec.md) · **Research**: [research.md](research.md) · **Migration**: `0005_categories`（down_revision = `0004_detail_and_key_moments`）

## 新表 `category`

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | String(26) | PK，ULID | |
| `name` | Text | NOT NULL | 显示名，已去首尾空格；1–30 个 Unicode 字符 |
| `name_key` | Text | NOT NULL，UNIQUE | `casefold(strip(NFKC(name)))`，用于判重（FR-002） |
| `position` | Integer | NOT NULL | 侧边栏顺序，从 0 开始；新建时取 `max + 1` |
| `origin` | String(8) | NOT NULL，CHECK IN (`user`, `ai`) | 用户新建，或经用户确认的 AI 提议 |
| `created_at` | DateTime(tz) | NOT NULL | |
| `updated_at` | DateTime(tz) | NOT NULL | |

索引：`uq_category_name_key`（唯一），`idx_category_position`。

保留名（按 `name_key` 比较）：`全部`、`未分类`、`all`、`uncategorized`。

## `episode` 新增列

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `category_id` | String(26) | NULL，FK → `category.id` | NULL 即「未分类」 |
| `category_origin` | String(8) | NULL，CHECK IN (`manual`, `auto`) | `manual` = 用户指定（留在未分类时即锁定）；`auto` = AI 放的；NULL = 从没被分过类 |
| `category_updated_at` | DateTime(tz) | NULL | 最后一次改归属的时间 |

索引：`idx_episode_category`（`category_id`）。

**不变式**

- `category_origin = 'auto'` ⇒ `category_id IS NOT NULL`。AI 不会把视频「放进未分类」，建议为 null 时保持原样。
- `category_origin = 'manual'` 且 `category_id IS NULL` 是合法状态：用户主动「移出分类」，这条视频锁在「未分类」（FR-009）。
- **锁定 ⇔ `category_id IS NULL AND category_origin = 'manual'`**，没有单独的锁定列。已在分类里的视频不需要锁：AI 本来就不碰任何已分类的视频（FR-019）。

> SQLite 没有打开外键约束（research §0），`category_id` 的 FK 只是文档意义。删除分类时由 `CategoryRepo.delete` 在同一事务里清空归属，见下文。

## 状态转换（一条视频的归属）

| 触发 | 前置 | `category_id` | `category_origin` |
|---|---|---|---|
| 新提交 / 首次入库（FR-008） | — | NULL | NULL |
| 重复提交（409） | 任意 | 不变 | 不变 |
| 手动指定分类 X（拖放 / 右键 / 详情页） | 任意 | X | `manual` |
| 手动「移出分类」 | 任意 | NULL | `manual` |
| 「交给 AI 分类」（FR-011） | `manual`（界面只对「未分类」里的提供） | 不变 | 有分类 → `auto`；在「未分类」→ NULL |
| 应用 AI 建议 → X | 非 `manual`，且仍在「未分类」（与建议生成时一致） | X | `auto` |
| 删除分类 X（FR-005） | `category_id = X` | NULL | NULL（解除锁定，回到可被 AI 处理的状态） |
| 删除视频 | — | 整行删除 | — |

每次转换都更新 `category_updated_at`。删除分类时的「解除锁定」是有意的：用户把分类删了，手动放在里面的视频不应该从此被永久锁在「未分类」、AI 也碰不到。

## AI 参与资格（FR-014 / FR-010 / FR-019）

一条视频参与本次 AI 分类，当且仅当：

1. `category_id IS NULL`：还在「未分类」。已在分类里的，不论是谁放的，都不参与（2026-09-24 用户调整，取代原先「AI 放的也重新考虑」）；
2. `category_origin` 不是 `manual`：没有被用户手动移出；并且
3. 有可用的总结：`episode.status IN ('done', 'partial')`，且 `summary_artifact.hook` 非空。

不参与的原因按上面的顺序判定，汇总进方案的 `skipped` 统计：`categorized`、`locked`、`no_summary`。

## 内存中的运行态 `CategorizeRun`（不落库）

| 字段 | 说明 |
|---|---|
| `run_id` | ULID |
| `state` | `running` → `ready` / `failed` / `cancelled` |
| `phase` | `taxonomy` / `assign` |
| `progress` | `{ "done": 已完成批次, "total": 总批次 }`；阶段 A 算 1 批 |
| `proposal` | `state = ready` 时有值，见 [contracts/http-api.md](contracts/http-api.md) |
| `error` | `state = failed` 时的原因 |
| `created_at` / `finished_at` | |

- 进程里最多一个 `running` 的 run。
- 结束的 run 保留最近 1 个，供客户端取结果。后端重启后丢失，客户端提示重新运行。

## 摘要文本的构造（领域逻辑，需单测）

| 用途 | 字段 | 截断 |
|---|---|---|
| 阶段 A 短摘要 | 标题；hook | 标题 ≤ 80 字，hook ≤ 120 字 |
| 阶段 B 长摘要 | 标题；hook；前 8 个章节标题；按出现次数取前 5 个实体 | hook ≤ 200 字，章节标题各 ≤ 40 字 |

每条摘要带一个**批内短编号**（`e1`、`e2`…）替代 ULID。这样 LLM 不用抄 26 位 id，也就不会抄错；解析时再映射回真实 id。
