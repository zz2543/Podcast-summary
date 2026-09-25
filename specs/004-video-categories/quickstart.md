# Quickstart：验证视频分类

**原则**：不碰真数据、不烧真 API 额度。沿用 002/003 的做法：fakeroot + 复制的数据库 + 假凭据。

## 1. 后端单元 / 集成测试

```bash
. .venv/bin/activate && PYTHONPATH=backend/src pytest backend/tests/unit/test_categorizer.py backend/tests/integration/test_categories_api.py backend/tests/integration/test_categorize_run.py -q
```

```bash
make test
```

期望：`make test` 的 domain 覆盖率门槛（≥ 80%，宪法 III）照样通过，`domain/categorizer.py` 单独也 ≥ 80%，全套无回归。

## 2. 迁移在真实库的副本上可升可降

```bash
cp data/podsum.sqlite3 "$SCRATCH/podsum.sqlite3"
```

对副本执行 `alembic upgrade head`，然后 `downgrade -1`，再 `upgrade head`。确认：

- 31 条剧集都在；`category_id`、`category_origin` 全为 NULL。
- `category` 表为空。

## 3. 用 fakeroot 后端过一遍接口（假 LLM）

在 fakeroot 下起 uvicorn（端口 8765），把 `app.state.llm_client` 换成返回固定 JSON 的假 client。依次执行：

1. `POST /api/categories {"name":"投资"}` → 201；再发一次 `{"name":" 投资 "}` → 409。
2. `PUT /api/episodes/{A}/category {"category_id": 投资}` → A 变成 `manual`。
3. `POST /api/categorize` → 轮询 `GET` 直到 `ready`：`changes` 里没有 A，`skipped.locked = 1`。
4. 在 `ready` 之后把 B 手动放进某个分类，再用原方案调 `POST /api/categories/apply` → B 出现在 `skipped`，原因 `locked`。
5. `DELETE /api/categories/{投资}` → `released = 1`，A 回到 `category_origin = NULL`。

## 4. 真 LLM 质量抽查（会产生少量费用，需用户同意后再跑）

用复制的库 + 真 LLM 凭据跑一次 AI 分类，只看方案，**不应用**。记录：

- 提议了几个分类，每个分类几条；
- 用户需要取消或改动的比例（对应 SC-005，目标 ≤ 20%）；
- 两阶段总耗时（SC-004：200 条内 ≤ 2 分钟；31 条预计 < 30 秒）。

## 5. macOS 客户端

先用 `design-check` 离屏渲染以下内容（亮 / 暗各一张）：

- 带分类小节的侧边栏；
- 视频卡片的右键菜单；
- AI 分类预览表（含新分类、跳过提示）。

> 实际执行时发现 `ImageRenderer` 画不了侧边栏 List、复选框、输入框、菜单这些 AppKit 控件（出来是黄块），
> 所以改为：复制一份客户端（换 bundle id / 钥匙串 service / 队列文件），连 fakeroot 后端 + 按关键词作答的假 LLM，
> 用 computer-use 在真 app 里点一遍。结果见 plan.md「已验证」。

然后连 fakeroot 后端做手动验收。这些操作需要真机和真实交互：

- [ ] 新建分类 → 把视频拖到侧边栏分类上 → 数量立即更新
- [ ] 右键「移到分类 ▸」「移出分类」「交给 AI 分类」
- [ ] 分类重命名、重名提示、删除确认文案、拖动排序后重启仍保持
- [ ] 选中分类时搜索只在分类内
- [ ] 详情页显示分类，并显示「手动 / AI」来源
- [ ] 「AI 分类」按钮：进度、取消、预览编辑、应用、关闭预览不改库
- [ ] 运行中按钮不可用
