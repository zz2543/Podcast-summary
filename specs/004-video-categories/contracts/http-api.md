# Contract: HTTP API — 分类

**Feature**: 004-video-categories · 在 [001 的 HTTP 契约](../../001-podcast-summary/contracts/http-api.md) 基础上新增。
错误体、错误码、Base URL 都沿用 001。新增错误码：无（重名用 `conflict`，名字不合法用 `bad_input`）。

---

## 现有响应的扩展

`GET /api/episodes` 的每一项和 `GET /api/episodes/{id}` 新增两个键。老客户端会忽略它们：

```json
{
  "category": { "id": "01J…", "name": "AI 编程" } | null,
  "category_origin": "manual" | "auto" | null
}
```

---

## 分类管理

### GET `/api/categories`

按 `position` 升序返回，另附「未分类」数量。

```json
{
  "items": [
    { "id": "01J…", "name": "AI 编程", "position": 0, "origin": "user", "episode_count": 12 }
  ],
  "uncategorized_count": 19
}
```

### POST `/api/categories`

```json
{ "name": "投资" }
```

- `201`：返回单个分类对象（同上，`episode_count: 0`），放在末尾。
- `400 bad_input`：去空格后为空、超过 30 个字符、或是保留名。
- `409 conflict`：`name_key` 已存在，`details.category_id` 指向已有分类。

### PATCH `/api/categories/{id}`

```json
{ "name": "理财" }
```

`200` 返回更新后的分类；`400` 和 `409` 同上（与自己重名不算冲突）；`404 not_found`。

### DELETE `/api/categories/{id}`

把其中视频的归属清空（`category_id = NULL`，`category_origin = NULL`），然后删除分类。

- `200`：`{ "released": 5 }`
- `404`

### PUT `/api/categories/order`

```json
{ "ids": ["01J…", "01J…"] }
```

`ids` 必须恰好是全部分类 id 的一个排列，否则 `400 bad_input`。`200` 返回同 `GET /api/categories`。

---

## 单条视频的归属

### PUT `/api/episodes/{id}/category`

手动指定或移出分类，写入 `category_origin = manual`，即锁定。

```json
{ "category_id": "01J…" | null }
```

- `200`：返回 `{ "category": {…} | null, "category_origin": "manual" }`
- `404`：视频不存在，或 `category_id` 指向不存在的分类（`details.missing` 为 `"episode"` 或 `"category"`）。

### POST `/api/episodes/{id}/category/release`

「交给 AI 分类」：`manual` → 有分类时改为 `auto`，在「未分类」时改为 NULL。本来就不是 `manual` 时，什么也不做，照样返回 200。

- `200`：返回同上的形状。
- `404`

---

## AI 分类运行

### POST `/api/categorize`

无请求体。启动一次运行。

- `202`：`{ "run_id": "01J…", "state": "running" }`
- `409 conflict`：已有运行中的 run，`details.run_id` 指向它。
- `400 bad_input`：参与视频为 0 条，`message` 说明原因（未分类的都没有总结，或全都已在分类里 / 被手动移出）。

### GET `/api/categorize/{run_id}`

```json
{
  "run_id": "01J…",
  "state": "running" | "ready" | "failed" | "cancelled",
  "phase": "taxonomy" | "assign",
  "progress": { "done": 1, "total": 3 },
  "error": null,
  "proposal": null
}
```

`state = ready` 时，`proposal` 为：

```json
{
  "categories": [
    { "key": "c:01J…", "category_id": "01J…", "name": "AI 编程", "is_new": false },
    { "key": "n:1",    "category_id": null,    "name": "个人理财", "is_new": true,
      "reason": "库里有 4 条讲基金定投与资产配置" }
  ],
  "changes": [
    { "episode_id": "01J…", "title": "…", "to_key": "n:1" }
  ],
  "skipped": { "categorized": 12, "locked": 3, "no_summary": 1, "no_suggestion": 2 },
  "failed_batches": 0
}
```

- 只有「未分类」且未锁定的视频参与（FR-019），所以 `changes` 里每一条都是把一条未分类视频放进某个分类，不会挪动已分类的视频。
- `categorized`：已在分类里（不论谁放的），没有参与。`locked`：被手动移出，没有参与。
- `no_suggestion`：模型给了 null、返回了无效内容（FR-020），或所在批次失败。`failed_batches > 0` 时客户端在预览里提示「部分视频没拿到建议」。
- `categories` 只列 `changes` 实际用到的分类，已有分类在前。
- `404`：run 不存在（包括后端已重启）。

### DELETE `/api/categorize/{run_id}`

取消。正在进行的那一次模型调用会跑完，但结果会被丢弃。`200`：`{ "state": "cancelled" }`。已结束的 run 原样返回当前 state。

---

## 应用方案

### POST `/api/categories/apply`

无状态接口：客户端把用户在预览里保留、编辑后的结果发回来。**整个请求在一个事务里执行**，要么全部按规则处理，要么（出现 5xx 时）一条都不写。

```json
{
  "new_categories": [
    { "key": "n:1", "name": "理财" }
  ],
  "assignments": [
    { "episode_id": "01J…", "from_category_id": null, "to_key": "n:1" },
    { "episode_id": "01J…", "from_category_id": null, "to_key": "c:01J…" }
  ]
}
```

规则（research §4）：

1. 先创建 `new_categories`：
   - 名字按 FR-002 校验，不合法 → 整个请求 `400`。
   - 与已有分类的 `name_key` 相同 → 复用已有分类，不新建。
   - 新建的分类 `origin = ai`，追加在末尾。
   - 没有被任何 assignment 引用的新分类不创建（「整组拒绝」就是客户端不发这组）。
2. 再逐条处理 `assignments`。`from_category_id` 是建议生成时视频所在的分类；按 FR-019 目前恒为 null，字段保留是为了让检查规则不依赖这一点。满足全部条件才写入 `category_id = 目标`、`category_origin = auto`，否则跳过：
   - 视频存在，否则 `episode_gone`；
   - `category_origin != 'manual'`，否则 `locked`；
   - 当前 `category_id == from_category_id`，否则 `changed`；
   - 目标分类存在，否则 `category_gone`。

`200`：

```json
{
  "created": [ { "key": "n:1", "category_id": "01J…", "name": "理财", "reused": false } ],
  "applied": 14,
  "skipped": [ { "episode_id": "01J…", "reason": "locked" | "changed" | "episode_gone" | "category_gone" } ]
}
```
