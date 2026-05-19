# GotIt / Podsum — 项目展示草稿

**场景**：5-10 分钟 short talk · 13 页 · 课堂/组内
**节奏**：P1-P3 ≈ 1.5 min · P4-P5 ≈ 1.5 min · P6-P8 ≈ 2.5 min · P9-P10 ≈ 3 min · P11-P12 ≈ 1.5 min · P13 + Q&A ≈ 30s

三个必须传递的信号：

1. **完整 + 实用** —— 端到端跑通，不是 demo 玩具
2. **技术力** —— 栈广、协议深、有测试、有规范
3. **人投入大** —— bug 是人查的，架构是人设计的，AI 是工具不是产物

每页固定结构：
- **slide 内容**（投影上的字）
- **🎤 口播**（讲什么）
- **🖼 视觉建议**（截图 / 图表 / 代码片段）

---

## P1 · 封面

**slide 内容**

```
GotIt
本地端到端播客摘要工具
—— 把一小时播客压成几分钟"听得懂"的浓缩

group 1  ·  2026.05
```

**🎤 口播**：开门见山一句话："这是我自己拿来听播客的工具，今天 demo + 讲讲它的几个有点意思的工程细节。"

**🖼 视觉**：v2 前端首页大图（Apple Liquid Glass 风），右下角放一个真实 episode 卡片缩略。

---

## P2 · 想解决的问题

**slide 内容**
- 1 集播客 = 40-90 分钟
- 想知道讲了啥 / 是不是值得听 / 哪些地方值得回头
- 人脑听 30 秒摘要 ≪ 听完 1 小时
- 现有工具：太重（Otter）、不带章节（YouTube 自动字幕）、信息不浓缩（直接转录稿）

**一句话定位**："**给一个链接，10 分钟后你拿到 hook、三幕、章节、引用、命名实体，外加一段可听的 30 秒 TTS 浓缩。**"

**🎤 口播**：强调"我自己每天在用"——这是动机的可信度。

**🖼 视觉**：左右对比 —— 左：1 小时音频波形；右：摘要卡片 + 30s digest.mp3 播放器。

---

## P3 · Demo 导览（口头预告）

**slide 内容**
- ① 粘贴一个 YouTube / Bilibili / mp3 链接
- ② 看实时进度（WebSocket 推送，下载→ASR→摘要→章节→TTS）
- ③ 打开详情页：hook 大引用 + 三幕 + 章节时间轴 + 可点引用跳到原音频
- ④ 一键生成"音频概览"——AI 用豆包大模型语音朗读摘要
- ⑤ 一键下载 .md / .json / .mp3

**🎤 口播**："接下来 3 分钟我直接放屏跑一遍，跑的同时讲后面在做什么。"

**🖼 视觉**：5 个步骤大数字图标，不放截图（要去做现场 demo）。

---

## P4 · 真实界面：列表页 + 详情页

**slide 内容**：左右两栏

**左栏 · 列表页**
- 🟢🟡🔴 Apple 风克制状态点
- 实时正在跑的任务条 + 搜索 + 5 状态过滤
- 提交弹窗三 Tab：本地上传 / Audio URL / YouTube/Bilibili
- "+ GotIt" 主按钮 AI 炫彩渐变

**右栏 · 详情页（花时间最多的一页）**
1. **Hook 大字引用** —— 30 字内一句话定位
2. **Sticky 原音频播放器** —— 往下滚不消失，永远在顶
3. **章节引用块可点击** —— 时间戳由段内字符位置线性插值算出，点一下原音频立即 seek + 自动播放 + 滚动器跟随
4. **AI Digest 播放器** —— 流动彩虹按钮，区别于黑色原音频按钮

**🎤 口播**："列表页看着像 Apple 官网，状态变化是后端 WS 实时推过来的，不是轮询。详情页是我花最多时间打磨的——'读摘要 + 验证原话'这个动作是用户真的会做的。"

**🖼 视觉**：左列表全屏截图（带 4 个箭头标注）；右详情滚动 GIF（hook → 三幕 → 章节 → 点引用跳播放）。

---

## P5 · 两套前端 · 视觉实验

**slide 内容**：左右对照

| | v1 `frontend/` | v2 `frontend-v2/` |
|---|---|---|
| 端口 | 5173 | 5174 |
| 样式 | 纯 CSS + 渐变 | Tailwind + Apple Liquid Glass |
| 动效 | 无 | framer-motion + Aceternity |
| 风格 | 功能优先 | 内容优先 + 克制配色 |
| 用途 | 当前主力 | A/B 视觉测试 |

两套**共享同一个后端**、同一个 API client、同一份 WS 协议；`make run-both` 同时启。

**🎤 口播**："并行 UI 不是炫技——是为了做真实的视觉决策对比。两套同时跑，看哪个我自己用着更舒服。"

**🖼 视觉**：左右截图对比，同一条 episode 在两套 UI 里的样子。

---

## P6 · 系统架构

**slide 内容**：分层架构图

```
┌────────────────────────────────────────────┐
│ Frontend                                   │
│ ┌──────────────┐  ┌──────────────────────┐ │
│ │ v1 React+CSS │  │ v2 React+Tailwind    │ │
│ │  (5173)      │  │  +Aceternity         │ │
│ │              │  │  +Framer (5174)      │ │
│ └──────────────┘  └──────────────────────┘ │
└──────────────┬─────────────────────────────┘
               │ HTTP /api · WS /api/ws/jobs
┌──────────────▼─────────────────────────────┐
│ FastAPI (uvicorn :8000)                    │
│ ┌──────────────────────────────────────┐   │
│ │ Pipeline runner (asyncio)            │   │
│ │  • 8 stages, retry via tenacity      │   │
│ │  • stage_progress → SQLite           │   │
│ │  • event bus → WebSocket broadcast   │   │
│ └──────────────────────────────────────┘   │
└──────────────┬─────────────────────────────┘
               │
        外部服务（详见 P8 技术栈）
        yt-dlp / ffmpeg · Doubao ASR / TTS · DeepSeek LLM
```

**slide 文字补充**
- 单进程 + asyncio：本地工具不上 Celery / Redis，简单可靠
- SQLite + 文件系统：`data/<episode_id>/` 装音频和导出
- 双前端共用一个后端 + WS 协议

**🎤 口播**："工具自用 + 一台机器，所以刻意不上 Redis/Postgres。但每一层都给可扩展留了口子。"

**🖼 视觉**：上图直接用 Excalidraw 画，配色和 P7 流程图一致。

---

## P7 · 端到端 Pipeline 与 8 个 Stage

**slide 内容**：上半部流程图，下半部 stage 列表

```
[链接/文件] → fetch → transcribe → summarize_hook → summarize_three_act
            yt-dlp   Doubao ASR    DeepSeek         DeepSeek
                                       ↓
                                  chapter_outline → quote_verify → entity_extract
                                       DeepSeek      自研验证       DeepSeek
                                                                       ↓
                              [Markdown + JSON] ← export ← (按钮触发) tts
                                                              Doubao BigTTS 2.0
```

**8 个 Stage**

```
1 fetch            ── yt-dlp 下载 + ffmpeg 归一化为 mp3
2 transcribe       ── 豆包录音文件 ASR（base64 提交 + 轮询查询）
3 summarize_hook   ── 一句话 hook，JSON schema 强校验
4 summarize_three_act
5 chapter_outline  ── 章节 + 章节内 quote 候选
6 quote_verify     ── 自研：NFKC + 空白归一 + 子串匹配 + 段内字符比例插值时间戳  ⚠ 见 P10 bug #5
7 entity_extract   ── 命名实体（人/书/产品）
8 export           ── Markdown + JSON 输出
+ tts (独立)       ── 豆包大模型 v3 双向流 WebSocket 二进制协议（见 P9）
```

**三件事一次说清**
- **独立 retry**：每个 stage 用 tenacity 指数退避 + 最大次数；ASR 慢或 LLM 抽风不会让整条作业重来
- **进度落盘**：`stage_progress` 写入 SQLite，进程重启可继续
- **实时事件**：每次状态变化通过 `/api/ws/jobs` 推送给所有前端，UI 看到哪一步在跑、哪一步死了，单独点 Retry
- **TTS 独立子 pipeline**：按钮触发，不阻塞主流程

**🎤 口播**："这 8 个 stage 不是花架子——每个都有独立失败模式，UI 能看到，能单独重试。粗体那行 quote_verify 一会儿讲。"

**🖼 视觉**：流程图 + stage 列表，按 stage 类型分组配色（下载=橙、ASR=蓝、LLM=紫、TTS=金、导出=灰）。

---

## P8 · 技术栈与选型理由

**slide 内容**：网格卡片，每个一句话

| 层 | 选型 | 选它的理由 |
|---|---|---|
| 后端 | FastAPI + SQLAlchemy 2 + Alembic + Pydantic 2 | 类型严格、async 友好、迁移可控 |
| 任务编排 | asyncio + tenacity | 不引入额外队列，本地工具够用 |
| 前端 v1 | React 19 + Vite + 纯 CSS | 功能完整、最小依赖 |
| 前端 v2 | React 19 + Tailwind + framer-motion + Aceternity | 视觉对比实验 |
| ASR | 豆包流式/录音文件大模型 2.0 | 中文识别质量高、字数计费 |
| LLM | DeepSeek（默认）· Qwen · Anthropic（可切） | 性价比 + 多供应商抽象（见 P9） |
| TTS | 豆包 v1 标准 · 豆包大模型 2.0（双向流 WS） | 双轨可回退 |
| 下载 | yt-dlp + ffmpeg | YouTube / Bilibili 通吃 |
| 测试 | pytest + Vitest，domain 模块 ≥80% line+branch | 见 P12 |

**🎤 口播**：不必逐条念，强调"每一行都是有 trade-off 的选择，不是随手抓一个流行库"。

**🖼 视觉**：表格 + 每行一个小 logo。

---

## P9 · 多供应商抽象 + 一处刚啃下来的硬骨头

**slide 内容**：分两栏

**左栏 · 抽象**
- ASR：doubao / openai_whisper / qwen — 一个 env 切换
- LLM：deepseek / qwen / anthropic — 同上
- TTS：doubao legacy / doubao bigmodel / qwen — 同上
- `create_xxx_client()` 工厂 + Protocol 接口，调用方零感知

**右栏 · 啃了一周的协议**

豆包大模型 TTS 2.0 **没有 HTTP 一次性接口**，只有 WebSocket 二进制流：

```
[4-byte header: version/type/flags/serialization]
[optional 4-byte event id]
[optional session_id length + bytes]
[4-byte payload size + payload]
```

事件流：`StartConnection → StartSession → TaskRequest → FinishSession → SessionFinished`，音频通过 `AudioOnlyServer` 帧 chunked 推回。

我做了什么：
- 把官方 demo 抄进 `_doubao_bigtts_protocol.py`，把 demo 的 `X-Api-App-Key` 改回文档里正确的 `X-Api-App-Id`
- 在同步 pipeline stage 里用 thread + `asyncio.run` 桥接到 async WS 工作流
- 失败时把 server 响应前 500 字符直接写进 job error，方便排查

**🎤 口播**："我没有调一个现成的 pip 包——是自己实现的协议层。下一页讲它带来的几个真 bug。"

**🖼 视觉**：左边代码片段（factory），右边二进制帧示意图。

---

## P10 · 自己排到的 Hard-Won Bugs（**这页最重要**）

**slide 内容**：6 个真 bug，每条一行

| # | 现象 | 根因 | 修法 | 学到 |
|---|---|---|---|---|
| 1 | TTS 一直 401 | 豆包要求 `Authorization: Bearer;<token>`（分号，不是空格） | 1 行 | 不是所有 API 都遵守 OAuth |
| 2 | TTS 一直 400 "exceed max len limit" | v1 单次文本 ≤ 1024 字节 | 加 `_split_text_for_tts` 按 utf-8 字节切句拼装 | 协议藏在文档脚注里 |
| 3 ⚠️ | BigTTS 2.0 一直 "concurrency exceeded" | resource_id 用了内部数字编号 (`volc.service_type.10048`)，正确值是语义化字符串 `seed-tts-2.0` | 改 env | 错误信息不能尽信 |
| 4 | digest.mp3 为空，无错误 | episode.language="mixed" 被路由到英文音色合成中文 → server 静默丢弃 | `_voice_type` 把 mixed 归类到中文 | 静默失败比报错可怕 |
| 5 ⚠️ | 多个 quote 时间戳一样（"3 条引用都是 1:18"） | 旧逻辑返回 segment 起点，没插值 | 改 `verify_against_segments`：按字符在段内位置线性插值 | 数据分布要看，不能只看 schema |
| 6 | Retry 时 worker 崩溃 + 后续 job 全 PendingRollback | `quote_verify` 重跑时撞 `(chapter_id, idx)` unique 约束 | `delete_for_chapters` 前置清理 + 单元测试 | 幂等是基本素养 |

**🎤 口播**：直接念 1-2 个最戏剧化的（推荐 #3 和 #5）。强调："这 6 个没有一个是 AI 一上来就能告诉你的——都是我读响应、读协议、读 DB 数据查出来的。"

**🖼 视觉**：纯文字表，#3 / #5 那两行标红或加 ⚠️。

---

## P11 · SDD：先写规范再写代码

**slide 内容**

`specs/001-podcast-summary/` 下有 **12 份文档**：

```
spec.md               功能规格（用户故事 + Acceptance）
plan.md               实施计划 + 复杂度跟踪
research.md           ASR/LLM/TTS 选型权衡（≥2 候选方案）
data-model.md         实体关系
tasks.md              依赖排序的任务分解
quickstart.md         上手指南
ui-brief.md           UI 设计简报
contracts/
  http-api.md         REST API 契约
  job-events.md       WebSocket 事件 schema
  episode-output.schema.json   产物 JSON Schema
design/...            UI 设计稿目录
```

外加 **`.specify/memory/constitution.md` v1.0.0**（5 条原则）：

1. 英文交付（文档/注释/commit）
2. Python 3.11+ 主栈
3. **Domain 模块 ≥80% 覆盖率（NON-NEGOTIABLE）**
4. 配置外置（env / .env，不硬编码 secret）
5. **Prompt 集中版本化**（所有 LLM prompt 在 `prompts/` 目录，带版本号）

**🎤 口播**："不是写完代码再补文档——是先写 spec、再写 plan、再写 tasks，最后才动键盘写实现。"

**🖼 视觉**：`tree specs/` 输出截图。

---

## P12 · 测试 + 质量门

**slide 内容**

```
backend/tests/
├── unit/          12 files   — 域逻辑（解析、分段、quote 校验、提示装配）
└── integration/    8 files   — 流水线 stage + 客户端 mock + 端到端

backend/pyproject.toml:
  --cov=backend/src/podsum/domain --cov-fail-under=80
                                          ↑↑↑ CI 硬门
```

亮点：
- domain 模块**纯函数**化 → 测试时不用启数据库 / 不用 mock 外部 API
- quote_verifier 的插值 bug（P10 #5）修复**同步加了** `test_quote_inside_long_merged_segment_is_interpolated`，反向证明 fix 正确
- frontend 用 Vitest + jsdom

**🎤 口播**："修一个 bug 必带一个测试——不是 KPI，是给自己留护栏。"

**🖼 视觉**：`pytest --cov` 终端截图（绿色 80%+）。

---

## P13 · 收尾

**slide 内容**

回到一开始的三个信号：

- **完整 + 实用** —— 下载 / ASR / 摘要 / 章节 / 引用 / 实体 / TTS / 导出，每天在用
- **技术力** —— 8 stage pipeline · BigTTS 二进制协议 · 多供应商抽象 · WS 实时事件 · 双前端
- **人投入大** —— 6 个 hard-won bug · 12 份 spec 文档 · domain 80% 覆盖硬门

**一句话收**："AI 是工具，不是答案——这套东西是查出来的、设计出来的、写出来的。"

**🎤 口播**：30 秒内念完，留时间 Q&A。

**🖼 视觉**：纯黑底白字，logo + Q&A。

---

## 📋 给 Presenter 的执行清单

- [ ] 把本文件复制到 Marp / Slidev / Reveal.js 工程
- [ ] **现场录一个 60 秒 demo screencast** 嵌入 P3 / P4 作为兜底（demo 翻车时切视频）
- [ ] **截图准备**（至少 4 张）：
  - 列表页（带状态点 + 活动任务条 + "+ GotIt"）
  - 详情页 hero（hook 引用）
  - 章节时间轴 + 引用块 hover 态（带 ▶ 时间戳）
  - DB job 表里某条失败记录的 error 字段（讲 bug 时用）
- [ ] **代码片段准备**（一张图）：豆包 BigTTS 二进制帧示意图，用于 P9
- [ ] **最有杀伤力的两页**：P10（bug 表）、P11（specs/ 树）——这两页慢一点讲

---

## 🚀 导出建议

**最快路径**：本文件已经是合法 Markdown，把每个 `## P*` 当一页：

```bash
# Marp（推荐，0 配置）
npm i -g @marp-team/marp-cli
marp presentation/outline.md --pdf
# 或导出 PPTX
marp presentation/outline.md --pptx
```

只需要在文件最顶部加几行 frontmatter：

```yaml
---
marp: true
theme: default
paginate: true
---
```

然后把每个 `## P*` 标题前加 `\n---\n` 分页符（已经全部加好）。
