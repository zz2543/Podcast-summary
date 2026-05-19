# GotIt · Podcast-Summary · Pre 大纲（9 章结构）

**场景**：课堂/组内 pre · 约 10 页 · 8–10 分钟
**风格**：每页一个信号 · 文字克制 · 视觉为主

---

## P1 · 背景

**slide 内容**
- 1 集播客 = 40–90 分钟，听完成本高
- 用户想知道：讲了啥 / 值不值得听 / 哪里值得回头
- 现有工具：太重（Otter）/ 没有章节（YouTube 字幕）/ 信息不浓缩（生转录）
- 我们的定位：**给一个链接，10 分钟拿到 hook + 三幕 + 章节 + 引用 + 实体 + 30 秒 TTS 浓缩**

**🖼 视觉**：左 1h 波形 vs. 右 摘要卡片 + digest.mp3 播放器

---

## P2 · 我们学到的

**slide 内容**：4 个关键收获
1. **先写规范再写代码**：12 份 spec 文档 + 5 条 constitution，先 spec → plan → tasks → code
2. **AI 不是答案，是协作伙伴**：6 个 hard-won bug 没有一个 AI 一上来能告诉你，靠人读响应/读协议/读 DB
3. **trade-off 是工程的本质**：本地自用 → 刻意不上 Redis/Celery/Postgres，但每层留扩展口
4. **测试是护栏不是 KPI**：domain 模块 ≥80% 覆盖率硬门，每修一个 bug 同步加回归测试

**🖼 视觉**：4 块卡片 grid，每块一句话

---

## P3 · 功能边界（做什么 / 不做什么）

**slide 内容**：左右对照

| ✅ 做了 | ❌ 不做（v1 边界）|
|---|---|
| 本地文件 / 直链 / YouTube / Bilibili 输入 | 多用户、公网部署 |
| 中英文 ASR、Hook、三幕、章节、引用、实体 | 实时直播流转写 |
| 引用可点击跳原音频（毫秒级 seek） | 视频画面分析 |
| 30 秒 TTS 浓缩（豆包大模型 v2） | > 6 小时 / > 1 GB 输入 |
| Markdown / JSON / MP3 导出 | 商业 SaaS / 收费层 |
| WebSocket 实时进度推送 | 多语言混合内容的同语言摘要 |

**约束**：单用户 · `127.0.0.1` loopback · 单进程 asyncio · SQLite + 本地文件

**🖼 视觉**：左右两栏对比表

---

## P4 · 前端

**slide 内容**：两套并行 UI · 同一个后端

| | v1 `frontend/` (:5173) | v2 `frontend-v2/` (:5174) |
|---|---|---|
| 样式 | 纯 CSS + 渐变 | Tailwind + Apple Liquid Glass |
| 动效 | 无 | framer-motion + Aceternity |
| 风格 | 功能优先 | 内容优先 + 克制配色 |
| 用途 | 当前主力 | A/B 视觉实验 |

**详情页 4 个特别打磨的细节**
1. **Hook 大字引用** —— 30 字内一句话定位
2. **Sticky 原音频播放器** —— 滚动时永远在顶
3. **章节引用可点击** —— 时间戳由段内字符位置线性插值，点一下原音频 seek + 自动播放 + 滚动跟随
4. **AI Digest 流动彩虹按钮** —— 视觉区别于黑色原音频按钮

**🖼 视觉**：左右截图对比 + 详情页滚动 GIF

---

## P5 · 后端 · 一条 8 段流水线 + 前后端连接

**slide 内容**：顶部横向 pipeline，下面两块小卡

```
[链接/文件] → 01 fetch → 02 transcribe → 03 hook → 04 three-act
              yt-dlp     豆包 ASR        DeepSeek   DeepSeek
                                ↓
              05 chapters → 06 quote-verify → 07 entities → 08 export
              DeepSeek      自研插值          DeepSeek       md+json
                                                                ↓
                                        ＋ digest (TTS · 豆包 BigTTS 2.0)
                                          按钮触发的独立子 pipeline
```

**Engineering Decisions（讲后端的核心卖点）**
- **独立 retry**：每个 stage tenacity 指数退避，单步失败不重跑整条作业
- **进度落盘**：`stage_progress` 写 SQLite，进程重启可继续
- **事件总线**：状态变化广播到 WebSocket，前端实时看到进度
- **单进程**：asyncio 而非 Celery/Redis —— 本地够用，留扩展口

**前后端连接（Front ⇄ Back）**
- **HTTP**：`/api/episodes/*` 调度 episode 生命周期
- **WS**：`/api/ws/jobs` 单条长连接广播 stage 事件
- **Serve**：`make serve` 让 FastAPI 同时出 SPA 与产物
- **契约**：`contracts/http-api.md` + `contracts/job-events.md` + `episode-output.schema.json`

**🖼 视觉**：上半 8 段卡片流水线（按 stage 类型分色：下载/ASR=蓝、LLM=紫、自研=品红、导出=琥珀）；下半左 "Engineering Decisions"，下半右 "Front ⇄ Back"。

> 讲法：手指顺着 8 个 stage 从左扫到右一句话过完 → 左下"每步独立 retry、状态落盘、出事不重跑" → 右下"前端 HTTP 调度、WS 收进度"。

---

## P6 · 接入的外部 API（我们调了谁）

**slide 内容**：三张 provider 卡片（ASR / LLM / TTS）

**① ASR · 语音识别 ── 豆包 Seed-ASR 2.0（Volcengine / ByteDance）**
- 接口：submit → query 两步 HTTPS 轮询
- URL：`openspeech.bytedance.com/api/v3/auc/bigmodel/{submit,query}`
- 资源：`volc.seedasr.auc` · 本地上传走 flash 端点 `volc.bigasr.auc_turbo`
- 回退：本地 Whisper · Qwen ASR

**② LLM · 摘要 / 章节 / 实体 ── DeepSeek Chat**
- 模型：`deepseek-chat`（OpenAI 兼容协议）
- URL：`api.deepseek.com/v1/chat/completions`
- 用途：Hook · 三幕摘要 · 章节 outline · 实体抽取
- 回退：Qwen（`qwen-max`）· Anthropic Claude

**③ TTS · 30 秒 Digest ── 豆包 BigTTS 2.0（Seed-TTS）**
- 协议：**WebSocket 二进制双向流**（自己实现的协议层，不是 pip 包）
- URL：`wss://openspeech.bytedance.com/api/v3/tts/bidirection`
- 资源：`seed-tts-2.0`（字符版）
- 回退：Doubao TTS v1（HTTP）· Qwen CosyVoice v2

**Also used**
- **yt-dlp**：YouTube / Bilibili 下载
- **ffmpeg**：音频归一化、转 mp3
- **provider 抽象**：`create_xxx_client()` 工厂 + Protocol 接口，一行 env 切换，调用代码零感知

**🖼 视觉**：三张并排卡片，每张顶部 tag 颜色不同（ASR 天蓝 / LLM 薄荷 / TTS 品红）；底部一条 "ALSO USED" 横条。

---

## P7 · 视频

**slide 内容**
- 标题：现场 demo 视频
- 二维码占位（扫码看完整 60 秒 demo）
- 视频涵盖：提交链接 → WS 实时进度 → 详情页 hook/三幕/章节 → 点引用跳音频 → 一键 TTS digest → 下载导出

**🖼 视觉**：居中一个二维码占位框 + 下方说明文字

> **占位**：上线前替换为真实视频二维码或链接缩略图。

---

## P8 · Bug（已解决 / 未解决）

**已解决 6 个 hard-won bug**

| # | 现象 | 根因 | 学到 |
|---|---|---|---|
| 1 | TTS 401 | Auth 头要 `Bearer;<token>` 用分号 | 不是所有 API 都遵守 OAuth |
| 2 | TTS 400 "exceed max len" | v1 单次 ≤1024 字节 | 按 utf-8 字节切句拼装 |
| 3 ⚠ | BigTTS "concurrency exceeded" | resource_id 应为 `seed-tts-2.0`，不是数字编号 | 错误信息可能误导 |
| 4 | digest.mp3 为空无错 | language=mixed 路由到英文音色被静默丢弃 | 静默失败比报错可怕 |
| 5 ⚠ | 多 quote 时间戳一样 | 旧逻辑返回 segment 起点，未插值 | 数据分布要看 |
| 6 | Retry worker 崩 + 后续 PendingRollback | unique 约束撞车 | 幂等是基本素养 |

**未解决 / 后续工作**
- 5 集真实播客的人工准确率评估（本次未跑）
- 真实 60 分钟样本的 ASR/LLM/TTS 分阶段耗时（待 M2 机型 benchmark）
- 多语言混合内容的同语言摘要质量优化
- Doubao 云端 smoke fixture，降低 provider API 变化回归风险
- 前端 Playwright E2E（batch / quote seek / digest retry）

**🖼 视觉**：上半部 6 行表（#3 #5 标 ⚠）· 下半部 5 条 bullet

---

## P9 · 小组贡献表

**slide 内容**：表格

| 成员 | 角色 | 主要贡献 | 工时占比 |
|---|---|---|---|
| [姓名 A] | [角色] | [模块/任务] | [%] |
| [姓名 B] | [角色] | [模块/任务] | [%] |
| [姓名 C] | [角色] | [模块/任务] | [%] |
| [姓名 D] | [角色] | [模块/任务] | [%] |

> **占位**：成员名单、分工、工时由小组核对后填入。

**🖼 视觉**：纯表格 + 底部一行致谢

---

## 收尾一句

> AI 是工具，不是答案。这套东西是查出来的、设计出来的、写出来的。
