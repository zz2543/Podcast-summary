# 前端重设计交接文档（Podcast Summary / "GotIt"）

> 用途：交给 Claude Design 做**全新前端界面设计**。后端与数据契约已冻结，不改。
> 生成日期：2026-09-09 ｜ 基于分支 `001-podcast-summary` 的真实代码与真实数据。

---

## 1. 产品是什么

一个**单用户、只跑在本机 loopback（127.0.0.1）上的播客摘要工具**。

用户丢进一个音频（本地文件 / 音频直链 / 视频链接），系统跑一条云端流水线：
**ASR 转写 → LLM 结构化摘要 → 章节切分 + 金句校验 + 实体抽取 → 可选 TTS 音频摘要**，
最后给出一份可读、可跳听、可导出的结构化摘要页。

核心价值排序（设计时的信息层级必须遵守这个顺序）：

0. **有用性评分（usefulness，0–100 分 + 分档 + 一句理由）** —— 决定这集值不值得花时间，在列表页是第一筛选依据。规格已定稿、后端尚未实现，见 §9.5。
1. **一句话摘要（hook）** —— 用户靠它决定要不要往下读，是详情页最醒目的元素。
2. **三段式摘要（背景 / 核心论点 / 结论）** —— 30 秒读完全片主旨。
3. **章节大纲 + 金句** —— 金句可点击跳转音频对应时间点，这是本产品最独特的交互。
4. **实体（人物 / 书籍 / 产品）** —— 侧边参考信息。
5. **音频摘要（TTS）/ 与文稿对话（Chat）** —— 增值能力。

不是什么：不是多用户 SaaS，没有登录/注册、没有个人主页、没有分享、没有评论评分、没有设置页（配置全在 `.env`）、没有移动 App 壳、没有说话人分离波形图、没有音频剪辑。

---

## 2. 现状与本次任务

- 仓库里已有**两套前端**：
  - `frontend/`（v1，React + 轻量 history 路由，功能完整但视觉朴素，端口 5173）
  - `frontend-v2/`（v2，React 19 + Vite 6 + TS + Tailwind 3 + framer-motion + react-router 7 + lucide-react，Apple 风白灰玻璃拟态 + Aceternity 风动效，端口 5174）
- **本次任务：抛开这两套的视觉，重新设计一套全新的前端界面。** 功能范围与数据契约保持不变。
- 技术约束（设计需落地到这个栈）：React 19 + TypeScript + Tailwind + Vite；动效用 framer-motion；图标用 lucide-react。桌面 Web 优先（≥1024px 为主场景），窄屏可降级但非重点。
- 界面文案：现有 v2 是**英文为主、少量中文混杂**（不一致，属于要修的问题）。请在设计中**统一一种语言**并给出完整文案表；内容本身（摘要/金句/文稿）保持来源语言（中/英/中英混杂）。

---

## 3. 页面与路由

只有两个路由（v1 规格如此，重设计可提议增改，但要说明理由）：

| 路由 | 页面 | 作用 |
|---|---|---|
| `/` | EpisodeListPage（库/首页） | 提交新节目、浏览全部节目、筛选/搜索、看实时进度、进入详情、重试/删除 |
| `/episodes/:id` | EpisodeDetailPage（阅读页） | 读结构化摘要、点金句跳听、播放原音频/音频摘要、导出、与文稿对话、删除/重试 |

顶部是一个共享的薄壳 AppShell（现状：56px 高，左侧品牌名 "GotIt"，粘顶玻璃质感）。

---

## 4. 真实数据形态（来自 22 集已处理的真实节目）

设计时必须按这些**真实量级**排版，不要按理想化的短文案排。

| 维度 | 真实范围 |
|---|---|
| 节目时长 | 28 秒 ～ 5938 秒（约 1.6 小时）；多数 10–50 分钟 |
| 语言 | `en` / `mixed`（中英混杂）为主，也有 `zh` |
| 标题长度 | 短的 20 字符，长的 45+ 字符（中文标题常被截断） |
| hook（一句话摘要） | 约 60–70 个中文字符（比 spec 里写的"≤50字"实际更长），是**1 句长句** |
| three_act 三段 | background ≈ 300+ 字符，core_argument ≈ 200 字符，conclusion ≈ 150 字符（**长度不均，不要设计等高三栏**） |
| 章节数 | 3 ～ 15 章，中位数约 9 |
| 每章 key_points | 2 ～ 3 条，每条 14–20 字符（很短，像标签） |
| 每章 quotes | 0 ～ 3 条；**整集金句总数 2 ～ 30 条** |
| 单条 quote 文本 | 50 ～ 170 字符，是**逐字原文长段**，不可截断（原文完整性是产品承诺） |
| entities | 0 ～ 40 个；kind 只有 `person` / `book` / `product` 三类；每个带 `count` 出现次数 |

真实样例（一集）：
- title：`南京大学ai专业学生大一下学期总结--也无风雨也无晴`，podcast_name：`公孙知云`，duration 1963s，language `mixed`
- hook：`一个南京大学AI专业学生回顾大一下学期,从实习碰壁转向科研,最终加入实验室,期间经历了健康危机和生活调整,收获了对耐心和平衡的感悟。`
- 12 章 / 21 条金句 / 6 个实体（1 person、1 book、4 product）
- 章节样例：`引言:学期回顾与视频动机`（00:00–06:27），key_points：`寒假留宁学习AI,学期结束完成首次投稿`、`生活中的变化与收获,视频目的为回顾分享`

**设计必须处理的极端情况**：0 章节 / 0 金句 / 0 实体的节目是真实存在的（例如某集 entities=0，某集只有 2 条金句）；同时也有 15 章 + 30 金句 + 40 实体的重节目。

---

## 5. 数据契约（TypeScript，前端直接使用）

```ts
type SourceType = "local_file" | "direct_url" | "youtube";
type EpisodeStatus = "pending" | "processing" | "done" | "partial" | "failed";
type JobState = "queued" | "fetching" | "transcribing" | "summarizing" | "tts" | "done" | "partial" | "failed";
type StageStatus = "pending" | "present" | "missing" | "failed_after_retries";

interface StageStatusMap {
  hook: StageStatus; three_act: StageStatus; chapters: StageStatus;
  entities: StageStatus; usefulness: StageStatus; tts: StageStatus;
}

// 有用性评分（FR-027）。stage_status.usefulness !== "present" 时整个对象为 null。
// 绝不要把未评分渲染成 0——0 是一个真实且有意义的分数。
interface Usefulness {
  score: number;   // 0-100 整数
  band: "must_listen" | "worth_listening" | "skimmable" | "skippable";  // 后端按分数区间确定性映射
  rationale: string;  // 一句话理由，来源语言，不截断
}

interface EpisodeSummary {
  id: string;                     // ULID
  title: string | null;           // 可能为 null → 需要 fallback 文案
  podcast_name: string | null;
  source_type: SourceType;
  duration_seconds: number | null;
  language: "zh" | "en" | "mixed" | null;
  status: EpisodeStatus;
  stage_status: StageStatusMap;   // 逐阶段状态，驱动「部分完成」的占位符
  usefulness: Usefulness | null;  // 未评分时整体为 null
  created_at: string; updated_at: string;  // ISO-8601
}

interface EpisodeDetail extends EpisodeSummary {
  source_ref: string;
  guests: string[] | null;
  prompt_versions: { one_liner: string; three_act: string; chapter_outline: string;
                     entity_extraction: string; usefulness_score: string };
  hook: string | null;
  three_act: { background: string; core_argument: string; conclusion: string } | null;
  chapters: { idx: number; title: string; start_ms: number; end_ms: number;
              key_points: string[]; quotes: { text: string; start_ms: number }[] }[];
  entities: { name: string; kind: "person" | "book" | "product"; count: number; sample_timestamps_ms?: number[] }[];
  artifact_paths?: { markdown?: string | null; json?: string | null; tts?: string | null };
}

interface Job {
  id: string; episode_id: string; state: JobState;
  stage_progress: Record<string, unknown>;   // 例：{ transcribed_until_seconds: 1800 }
  attempt: number; error: string | null;
  started_at: string | null; finished_at: string | null;
}
```

---

## 6. HTTP API（已实现，不可改）

Base：`http://127.0.0.1:8000`，无鉴权。错误统一为 `{ "error": { code, message, details } }`。
错误码：`bad_input` / `not_found` / `conflict` / `payload_too_large` / `unsupported_media` / `upstream_failed` / `internal`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/episodes` | 建单集。JSON（`direct_url`/`youtube` + `source_ref`）或 multipart（`local_file` + `file`）。可选 `summary_style` + `style_note`（见 §6 第 1 条）。201 返回 `{ episode, job }` |
| POST | `/api/episodes/batch` | 批量提交（多文件 or 多 URL，**不可混用**）。返回 `{ items: [{episode, job}] }` |
| GET | `/api/episodes?limit=&cursor=&status=&band=&min_score=&sort=` | 列表，游标分页，返回 `{ items, next_cursor }`。`sort=created_at`（默认，最新优先）或 `sort=usefulness_score`（高分优先，未评分排最后）；带 `band=` 时会排除未评分节目 |
| GET | `/api/episodes/{id}` | 详情 `EpisodeDetail` |
| DELETE | `/api/episodes/{id}` | 原子删除（DB 行 + `data/<id>/` 目录），204 |
| POST | `/api/episodes/{id}/retry` | 从最近 checkpoint 续跑，202 返回新 Job；已有活跃 job 时 409 |
| POST | `/api/episodes/{id}/digest` | 触发 TTS 音频摘要；已存在则 200 返回路径，否则 202 排队 |
| GET | `/api/episodes/{id}/files/markdown` | 下载 summary.md |
| GET | `/api/episodes/{id}/files/json` | 下载 summary.json |
| GET | `/api/episodes/{id}/files/audio` | 原音频流，**支持 HTTP Range**（金句跳听靠它） |
| GET | `/api/episodes/{id}/files/digest` | TTS 音频摘要流 |
| GET | `/api/episodes/{id}/files/transcript` | 全文文稿 `.txt` 下载 |
| POST | `/api/episodes/{id}/chat` | **SSE 流式**与文稿对话，body `{ message, history: [{role,content}] }`，逐 token 推送 `data: {"token": "..."}`，结束 `data: [DONE]`；无文稿时 422 |
| GET | `/api/jobs/{id}` | 单个 job |
| GET | `/api/health` | `{ status: "ok", version }` |

### 实时进度：WebSocket `ws://127.0.0.1:8000/api/ws/jobs`

连接后依次收到 `hello` → `snapshot`（全量 jobs），之后推送：
- `{ type: "job_update", job, episode_status }`
- `{ type: "stage_status_update", episode_id, stage, status }`

断线指数退避重连（250ms → 4s 封顶），重连后服务端重发 snapshot。
**UI 需要一个连接状态指示**（现状：绿点 "Live" / 灰点 "Offline"）。

---

## 7. 需要设计的界面清单

### 7.1 列表页 `/`

必须承载的元素：

1. **提交入口** —— 三种来源：本地文件（拖拽 + 多选，仅 mp3/m4a/wav，单文件 ≤1GB、时长 ≤6h）、音频直链（多行，一行一个）、视频链接（多行；YouTube 与 Bilibili，见 §9.5）。现状是一个模态框（SubmitModal）；重设计可以改成常驻面板或别的形态，请给出你的判断。
   - 客户端校验文案：格式不符 / 超 1GB / 链接格式无效 / 空提交。
   - **总结风格（summary style）** —— 提交区右上角一个按钮展开的受限面板：5 个预设胶囊（Default / Study notes / Business / Debate / Quick skim）+ 一个 ≤200 字的补充指令输入框 + 重置。整次提交（含批量）共用一份风格，非默认时按钮直接显示当前预设名。这是一个**受框架约束**的入口：它只影响语气、侧重与详略，不改输出结构、语言与事实；预设文案的唯一来源是 `prompts/summary_style.v1.md`，前端只负责标签。重设计可以改变它的形态，但不得退化成任意 prompt 输入框。
2. **筛选与排序** —— 状态胶囊（全部 / 处理中 / 已完成 / 部分完成 / 失败）；评分档位下拉（全部评分 / 必听 / 值得听 / 可跳读 / 可跳过）；排序下拉（最新优先 / 评分优先）。
3. **搜索** —— 对已加载的 title + podcast_name 做客户端过滤。
4. **进行中任务条（ActiveJobsStrip）** —— 展示当前排队/运行中的 job 及阶段进度。5 个阶段：fetch → transcribe → summarize → chapter+entity → tts。
5. **节目列表** —— 现状是 Bento 网格卡片；v1 规格要求"1080p 屏不滚动至少看到 5 条"。每个条目需要：来源类型图标、标题（null 时 fallback）、副信息（podcast · 来源域名 · 时长 mm:ss）、**ScoreBadge（见下）**、状态徽章、hook 预览（完成后单行截断）、处理中时的分段进度条、操作（打开 / 重试 / 删除）。

   **ScoreBadge**（紧凑评分标记，列表页及详情页以外任何出现分数的地方）：显示 0–100 数字 + 档位文字，两者永远同时出现，颜色不能是唯一信号。档位文案：`must_listen`→必听（最强调）、`worth_listening`→值得听（正向）、`skimmable`→可跳读（中性）、`skippable`→可跳过（弱化，**不要用告警红**）。`usefulness === null` 时渲染同尺寸的灰色「未评分」chip，无数字无色彩强调。hover 显示 `rationale`。
6. **"加载更多"**（游标分页）。
7. **空状态**（一条都没有时）。
8. **加载骨架屏**（不要整页 spinner）。

### 7.2 详情页 `/episodes/:id`

现状自上而下：返回链接 → HookHero → 生成音频摘要按钮 + 摘要播放器 → **粘顶的原音频播放器** → 三段式面板 → 章节时间线 → 悬浮 Dock（重试 / Markdown / JSON / 导出文稿 / 原音频 / 音频摘要 / 与文稿对话 / 删除）→ 侧滑 ChatPanel → toast。

必须承载的元素：

1. **元信息头** —— 标题、podcast_name、嘉宾、时长、来源、语言标签（中文 / English / 中英混杂）。
2. **HookCard** —— 全页最醒目的一块，字号明显大于正文；附小字 `Prompt 版本：<prompt_versions.one_liner>`（可溯源要求）。
3. **UsefulnessCard（有用性评分卡）** —— 紧邻 HookCard。分数是视觉锚点（约 40–48px 字号），"/ 100" 弱化且小得多；右侧档位文字，档位色同时给一条量度条上色；下方一句 `rationale`（不截断）；底部小字 `Prompt 版本：<prompt_versions.usefulness_score>`。措辞必须保持中立——不得暗示这集经过核实或被背书；档位标签的 tooltip：「由模型根据转写内容给出的参考评分。」`stage_status.usefulness !== "present"` 时降级为占位卡，且不阻塞页面其余部分。
4. **三段式** —— 背景 / 核心论点 / 结论，三块内容长度悬殊（324 / 203 / 146 字符量级）。
5. **章节大纲** —— 每章：序号、标题、`mm:ss–mm:ss` 时间区间、可折叠、"核心观点"要点列表、"金句"区。
   - **金句必须看起来可点**：点击后音频 seek 到 `start_ms/1000` 并播放，同时给出视觉反馈（高亮金句 + 播放器闪一下）。这是全站最需要被"发现"的交互。
   - 金句全文不截断。
6. **实体面板** —— 人物 / 书籍 / 产品三组 chip，带 `× count`；点 chip 跳到首个 `sample_timestamps_ms`。宽屏粘性右栏，窄屏折叠抽屉。（注：`EntityCloud.tsx` 已在当前工作区被删除，实体区当前处于待重设计状态。）
7. **音频播放器** —— 原音频常驻可见（现状 sticky），需要播放/暂停、进度条、`mm:ss / mm:ss`、倍速（0.75/1/1.25/1.5/2）、下载。播放"音频摘要"时要能明确区分并切回原音频。
8. **产物与操作区** —— 下载 Markdown / JSON / 文稿 txt、生成或播放音频摘要、重新处理、删除整集（需二次确认对话框，说明会连带删除音频/文稿/导出/摘要且不可撤销）。
9. **与文稿对话（Chat）** —— 流式逐 token 输出的对话面板，仅在 `status ∈ {done, partial}` 时可用。现状为侧滑面板。
10. **加载骨架 / 404 空状态**。

### 7.3 状态与边界（每一个都要有设计）

| 场景 | 要求 |
|---|---|
| 5 种 episode 状态 | pending 灰"等待中" / processing 蓝"处理中" / done 绿"已完成" / partial 琥珀"部分完成" / failed 红"失败"。**不能只靠颜色区分**（红绿色盲可辨），必须保留文字标签 |
| 阶段级缺失 | 任一 `stage_status` 为 `missing` / `failed_after_retries` 时，对应区块换成占位卡：说明哪个环节没生成 + "重试此环节"按钮。阶段名映射：hook→一句话摘要，three_act→三段式摘要，chapters→章节大纲，entities→实体识别，usefulness→有用性评分，tts→音频摘要 |
| 处理中 | 分段进度条（5 段），当前段有不确定态条纹动画，hover 显示"转写：42%" |
| WebSocket 断线 | 连接指示：绿点无标签 / 黄点"正在重连…" / 红点"实时连接断开，刷新页面重试" |
| 服务端错误 | toast（3 秒自动消失、不阻塞输入）。文案映射：400 提交内容格式不正确 / 404 节目不存在或已删除 / 409 该节目已在处理或已存在 / 413 超 1GB 或 6 小时上限 / 415 不支持的链接或文件类型 / 502 云服务暂时不可用 / 500 出错了请刷新重试 |
| 空数据 | 无节目、无章节、无金句、无实体各自的空态 |

---

## 8. 硬约束（无论视觉风格怎么变都要成立）

1. **HookCard 是详情页视觉权重最高的块**，大于三段式、大于章节正文。产品全部价值压在这一句话上。
2. **播放器在详情页始终可达**，任何模态/抽屉不得在播放时把它完全遮住。
3. **金句必须显性地"看起来能点"**——它是全站最反直觉的交互（一段引文其实是按钮）。
4. **状态不可仅用颜色编码**，必须带文字。
5. **列表密度**：1080p 屏首屏不滚动至少看到 5 个节目条目。
6. **金句、要点、三段式正文一律不截断**（除列表页的 hook 预览行）。
7. 阅读友好：这是消费长文本思想内容的产品，正文行高宽松、元信息行高紧凑；避免正文压在通栏大图上。

## 9. 软性建议（可自由推翻，但请说明理由）

- 现状风格是"Apple 白灰 + 玻璃模糊 + 微动效"（色板：bg `#FBFBFD`、surface `#FFFFFF`、elev `#F5F5F7`、border `#D2D2D7`、text `#1D1D1F`/`#6E6E73`/`#86868B`，状态色 `#34C759`/`#FF9F0A`/`#FF3B30`/`#0A84FF`）。**重设计不必沿用。**
- 未做深色模式，可以提议加。
- 音频元素（声波、圆润的播放形状）作为视觉母题是欢迎的，但非必需。

---

## 9.5 两个容易踩的现实细节（重要）

1. **`source_type: "youtube"` 实际是"视频链接"通道**：后端用 yt-dlp，除 YouTube 外也已支持 **Bilibili**（`bilibili.com` / `b23.tv`，含匿名 cookie 处理）。UI 文案不要写死 "YouTube"，用"视频链接"更准确。
2. **评分能力（FR-027）目前只有规格与 prompt 文件，后端与前端都还没实现**：`spec.md` / `contracts/` / `ui-brief.md` 已定稿，`prompts/usefulness_score.v1.md` 已存在，但 `backend/src/` 里尚无对应代码，现有 22 集真实数据全部**没有** `usefulness` 字段。所以设计必须把"未评分"当成**长期存在的一等状态**，而不是罕见边界情况。

---

## 10. 后端与运行环境（背景信息，设计不需要动）

- 后端：Python 3.11 + FastAPI + SQLAlchemy + Alembic + SQLite（`data/podsum.sqlite3`），大文件落盘 `data/<episode_id>/`（`audio.original.*`、`audio.normalized.mp3`、`transcript.raw.json`、`transcript.normalized.json`、`summary.md`、`summary.json`、`digest.mp3`）。
- 云服务栈：ASR/TTS 用火山引擎 Doubao，LLM 用 DeepSeek；Qwen / Anthropic / Whisper / Deepgram 作为可切换 fallback。
- 并发：SQLite 持久队列 + `asyncio.Queue` + `Semaphore(MAX_CONCURRENCY)`；重启后自动恢复未完成 job（复用已持久化的转写，不重复 ASR）。
- 金句双层防御：LLM 只能提候选，落库前必须经 `quote_verifier` 逐字校验，JSON 导出再过滤一次 `verified=True`。
- 生产模式：`make build` 出静态包，FastAPI 直接托管 SPA（前端路由需支持 history fallback）。
- 规格文档位置：`specs/001-podcast-summary/`（`spec.md` / `plan.md` / `data-model.md` / `contracts/` / `ui-brief.md` / `design/selected/前端设计图.png`）。

---

## 11. 请 Claude Design 交付

1. 列表页（默认态 / 空态 / 加载态 / 有处理中任务态）
2. 详情页（全阶段完成态 / 部分失败态 / 未评分态）
3. 提交入口（三种来源）
4. 音频播放器与金句跳听的交互细节
5. 章节卡片、金句卡片、实体 chip、状态徽章、ScoreBadge 四档 + 未评分、UsefulnessCard、进度条、占位卡、toast、确认删除对话框等组件规范
6. 一套完整的色板 / 字阶 / 间距 / 圆角 / 阴影 token（能直接落到 Tailwind config）
7. 统一语言的完整文案表
