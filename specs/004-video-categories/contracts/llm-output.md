# Contract: LLM 输入 / 输出 — AI 分类

**Prompts**: `prompts/category_taxonomy.v1.md`、`prompts/category_assign.v1.md`（宪法 V）
**Parser**: `backend/src/podsum/domain/categorizer.py`（宪法 III，覆盖率 ≥ 80%）

两个 prompt 都用 `lang_aware: true`：新分类名和 `reason` 使用库的主要语言。当前库全部是中文。

---

## 阶段 A：`category_taxonomy`

**Slots**

| slot | 内容 |
|---|---|
| `existing` | 已有分类，每行一个名字；没有时为 `(none)` |
| `episodes` | 每行 `e<N> <标题> — <hook 前 120 字>` |
| `max_new` | 已有分类为空时 `10`，否则 `5` |
| `min_new` | 已有分类为空时 `3`，否则 `0` |
| `lang` | `Chinese` / `English` |

**Prompt 要点**（写在 prompt 文件里，不写在代码里）

- 已有分类全部保留，名字不能改、不能合并、不能删，只能新增（FR-015）。
- 分类要能把这个库**有意义地切开**。当前库是一个集中在 AI 编程的库，「科技」这种一个就装下全部的分类没有用。尽量不让一个分类装下超过一半的视频，除非真的只有一个主题。
- 分类名短（≤ 12 个字），像文件夹名，不要带编号或 emoji。

**输出**（pydantic 校验）

```json
{
  "new_categories": [
    { "name": "个人理财", "reason": "4 条讲基金定投与资产配置" }
  ]
}
```

**解析规则**

- 名字去首尾空格后按 FR-002 校验，不合法的丢弃。
- 与已有分类或前面的新分类 `name_key` 相同的，丢弃（去重）。
- 超过 `max_new` 的，截断。
- 已有分类为空，且解析后新分类为 0 个 → 这次运行失败，原因 `no_taxonomy`。

---

## 阶段 B：`category_assign`

**Slots**

| slot | 内容 |
|---|---|
| `categories` | 最终分类表，每行 `<key> <名字>`，例如 `c1 AI 编程`、`c2 个人理财`（批内短 key） |
| `episodes` | 每条一段：`e<N>` + 标题 + hook 前 200 字 + 章节标题（前 8 个）+ 实体（前 5 个） |
| `lang` | 同上 |

**输出**

```json
{
  "assignments": [
    { "episode": "e1", "category": "c2" },
    { "episode": "e2", "category": null }
  ]
}
```

**解析规则**（FR-020）

- `episode` 不在本批编号里 → 丢弃这一项。
- 同一个 `episode` 出现多次，且给的 `category` 不一致 → 这条视频的所有项全部丢弃，记为 `no_suggestion`。重复但一致的，按一条处理。
- `category` 不在分类表里 → 视为 null。
- 本批里没被提到的视频 → `no_suggestion`。
- 整个响应不是合法 JSON、schema 校验失败，或 LLM client 重试后仍然报错 → 整批记为失败，本批视频全部 `no_suggestion`，`failed_batches += 1`。

## 运行结果的判定

| 情况 | run 状态 |
|---|---|
| 阶段 A 失败 | `failed` |
| 阶段 B 全部批次失败 | `failed` |
| 阶段 B 部分批次失败 | `ready`，`failed_batches > 0` |
| 用户取消 | `cancelled` |
