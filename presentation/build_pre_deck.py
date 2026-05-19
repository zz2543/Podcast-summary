"""Build the Pre deck (9-section structure) as GotIt-Pre-deck.pptx."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

OUT = Path(__file__).resolve().parent / "GotIt-Pre-deck.pptx"

# Apple-ish palette
BG = RGBColor(0xF5, 0xF5, 0xF7)
INK = RGBColor(0x1D, 0x1D, 0x1F)
SUB = RGBColor(0x6E, 0x6E, 0x73)
ACCENT = RGBColor(0x00, 0x71, 0xE3)
WARN = RGBColor(0xE0, 0x6C, 0x00)
OK = RGBColor(0x1F, 0x8A, 0x4C)
LINE = RGBColor(0xD2, 0xD2, 0xD7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00)

FONT = "PingFang SC"
FONT_EN = "SF Pro Display"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def add_bg(slide, color=BG):
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    rect.line.fill.background()
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.shadow.inherit = False
    return rect


def add_text(slide, x, y, w, h, text, *, size=18, bold=False, color=INK,
             align=PP_ALIGN.LEFT, font=FONT):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    lines = text.split("\n") if isinstance(text, str) else text
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.name = font
        r.font.color.rgb = color
    return tb


def add_pill(slide, x, y, text, *, fill=INK, fg=WHITE, size=11):
    w = Inches(0.6 + 0.11 * len(text))
    h = Inches(0.32)
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    s.adjustments[0] = 0.5
    s.line.fill.background()
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    tf = s.text_frame
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.name = FONT
    r.font.color.rgb = fg
    return s


def add_rule(slide, x, y, w, color=LINE, weight=0.75):
    line = slide.shapes.add_connector(1, x, y, x + w, y)
    line.line.color.rgb = color
    line.line.width = Pt(weight)
    return line


def add_card(slide, x, y, w, h, *, fill=WHITE):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    s.adjustments[0] = 0.04
    s.line.color.rgb = LINE
    s.line.width = Pt(0.5)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.shadow.inherit = False
    return s


def page_header(slide, num, title, sub=None):
    add_pill(slide, Inches(0.6), Inches(0.55), f"P{num}", fill=INK, fg=WHITE)
    add_text(slide, Inches(1.35), Inches(0.5), Inches(11), Inches(0.6),
             title, size=30, bold=True, color=INK)
    if sub:
        add_text(slide, Inches(1.35), Inches(1.05), Inches(11), Inches(0.4),
                 sub, size=14, color=SUB)
    add_rule(slide, Inches(0.6), Inches(1.55), Inches(12.13))


def footer(slide, num, total=9):
    add_text(slide, Inches(0.6), Inches(7.05), Inches(6), Inches(0.3),
             "GotIt · Podcast-Summary · 2026.05", size=10, color=SUB)
    add_text(slide, Inches(7.33), Inches(7.05), Inches(5.4), Inches(0.3),
             f"{num} / {total}", size=10, color=SUB, align=PP_ALIGN.RIGHT)


# ===== Slide 0 · Cover =====
def slide_cover():
    s = prs.slides.add_slide(BLANK)
    add_bg(s, BLACK)
    # accent line
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                             Inches(0.6), Inches(3.1), Inches(0.4), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    add_text(s, Inches(0.6), Inches(2.3), Inches(12), Inches(0.6),
             "GotIt · Podcast-Summary", size=18, color=RGBColor(0xA8,0xA8,0xB0))
    add_text(s, Inches(0.6), Inches(3.3), Inches(12), Inches(1.2),
             "本地端到端播客摘要工具", size=52, bold=True, color=WHITE)
    add_text(s, Inches(0.6), Inches(4.3), Inches(12), Inches(0.6),
             "把一小时播客压成几分钟听得懂的浓缩",
             size=22, color=RGBColor(0xC8,0xC8,0xCD))
    add_text(s, Inches(0.6), Inches(6.6), Inches(12), Inches(0.4),
             "Group 1 · 2026.05 · 课堂展示",
             size=14, color=RGBColor(0x8E,0x8E,0x93))


# ===== P1 · 背景 =====
def slide_p1():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 1, "背景", "为什么做这个工具")

    bullets = [
        ("⏱  1 集 = 40–90 分钟", "听完一集成本高，时间不可逆。"),
        ("🤔  用户三问", "讲了啥？值不值得听？哪里值得回头？"),
        ("🛠  现有工具痛点", "Otter 太重 · YouTube 字幕没章节 · 生转录稿不浓缩。"),
        ("🎯  我们的定位", "给一个链接 → hook + 三幕 + 章节 + 引用 + 实体 + 30s TTS 浓缩。"),
    ]
    y = Inches(1.95)
    for title, desc in bullets:
        add_card(s, Inches(0.6), y, Inches(12.13), Inches(1.05))
        add_text(s, Inches(0.95), y + Inches(0.18), Inches(4), Inches(0.5),
                 title, size=18, bold=True, color=INK)
        add_text(s, Inches(5.3), y + Inches(0.25), Inches(7.3), Inches(0.7),
                 desc, size=14, color=SUB)
        y += Inches(1.2)
    footer(s, 1)


# ===== P2 · 我们学到的 =====
def slide_p2():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 2, "我们学到的", "做完这个项目，留下来的四件事")

    items = [
        ("01", "先写规范再写代码",
         "12 份 spec 文档 + 5 条 constitution。\nspec → plan → tasks → code，不是反过来。"),
        ("02", "AI 不是答案，是协作伙伴",
         "6 个 hard-won bug，AI 一上来都答不出。\n靠人读响应、读协议、读数据库。"),
        ("03", "trade-off 是工程的本质",
         "本地自用刻意不上 Redis / Celery / Postgres。\n但每一层都给扩展留口子。"),
        ("04", "测试是护栏，不是 KPI",
         "domain ≥ 80% 覆盖率硬门。\n每修一个 bug 同步加回归测试。"),
    ]
    gx, gy = Inches(0.6), Inches(1.95)
    cw, ch = Inches(6.0), Inches(2.4)
    gap = Inches(0.13)
    positions = [(0,0),(1,0),(0,1),(1,1)]
    for (col,row), (no, title, body) in zip(positions, items):
        x = gx + col*(cw+gap); y = gy + row*(ch+gap)
        add_card(s, x, y, cw, ch)
        add_text(s, x+Inches(0.3), y+Inches(0.2), Inches(1.0), Inches(0.5),
                 no, size=28, bold=True, color=ACCENT, font=FONT_EN)
        add_text(s, x+Inches(0.3), y+Inches(0.85), cw-Inches(0.6), Inches(0.5),
                 title, size=20, bold=True, color=INK)
        add_text(s, x+Inches(0.3), y+Inches(1.4), cw-Inches(0.6), Inches(0.9),
                 body, size=13, color=SUB)
    footer(s, 2)


# ===== P3 · 功能边界 =====
def slide_p3():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 3, "功能边界", "做什么 / 不做什么")

    # two columns
    do = [
        "本地文件 / 直链 / YouTube / Bilibili 输入",
        "中英文 ASR · Hook · 三幕 · 章节 · 引用 · 实体",
        "引用可点击跳原音频（毫秒级 seek）",
        "30 秒 TTS 浓缩（豆包大模型 v2）",
        "Markdown / JSON / MP3 一键导出",
        "WebSocket 实时进度推送",
    ]
    dont = [
        "多用户 / 公网部署",
        "实时直播流转写",
        "视频画面分析",
        "> 6 小时或 > 1 GB 输入",
        "商业 SaaS / 收费层",
        "多语言混合内容的同语言摘要",
    ]

    col_w = Inches(5.9); col_h = Inches(4.5)
    add_card(s, Inches(0.6), Inches(1.85), col_w, col_h)
    add_card(s, Inches(6.83), Inches(1.85), col_w, col_h)
    add_pill(s, Inches(0.85), Inches(2.05), "✓  已做", fill=OK)
    add_pill(s, Inches(7.08), Inches(2.05), "✗  v1 不做", fill=RGBColor(0xC0,0x3A,0x2B))

    y = Inches(2.65)
    for line in do:
        add_text(s, Inches(0.95), y, col_w-Inches(0.5), Inches(0.4),
                 "•  " + line, size=14, color=INK)
        y += Inches(0.45)
    y = Inches(2.65)
    for line in dont:
        add_text(s, Inches(7.18), y, col_w-Inches(0.5), Inches(0.4),
                 "•  " + line, size=14, color=SUB)
        y += Inches(0.45)

    # constraints strip
    add_card(s, Inches(0.6), Inches(6.5), Inches(12.13), Inches(0.5), fill=RGBColor(0xEC,0xEC,0xF0))
    add_text(s, Inches(0.85), Inches(6.55), Inches(12), Inches(0.4),
             "约束  ·  单用户  ·  127.0.0.1 loopback  ·  单进程 asyncio  ·  SQLite + 本地文件",
             size=12, bold=True, color=INK)
    footer(s, 3)


# ===== P4 · 前端 =====
def slide_p4():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 4, "前端", "两套并行 UI，共享同一个后端")

    # table
    rows = [
        ("",         "v1 frontend/ (:5173)",      "v2 frontend-v2/ (:5174)"),
        ("样式",      "纯 CSS + 渐变",              "Tailwind + Apple Liquid Glass"),
        ("动效",      "无",                         "framer-motion + Aceternity"),
        ("风格",      "功能优先",                    "内容优先 · 克制配色"),
        ("用途",      "当前主力",                    "A/B 视觉实验"),
    ]
    x0, y0 = Inches(0.6), Inches(1.85)
    col_w = [Inches(1.5), Inches(5.3), Inches(5.33)]
    row_h = Inches(0.42)
    for ri, row in enumerate(rows):
        x = x0
        for ci, val in enumerate(row):
            is_head = (ri == 0)
            bg = RGBColor(0xEC,0xEC,0xF0) if is_head else WHITE
            cell = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y0+ri*row_h, col_w[ci], row_h)
            cell.fill.solid(); cell.fill.fore_color.rgb = bg
            cell.line.color.rgb = LINE; cell.line.width = Pt(0.5)
            tf = cell.text_frame
            tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.1)
            tf.margin_top = Emu(0); tf.margin_bottom = Emu(0)
            p = tf.paragraphs[0]
            r = p.add_run(); r.text = val
            r.font.size = Pt(12); r.font.name = FONT
            r.font.bold = is_head or ci == 0
            r.font.color.rgb = INK
            x += col_w[ci]

    # details
    add_text(s, Inches(0.6), Inches(4.35), Inches(12), Inches(0.4),
             "详情页 · 4 个特别打磨的细节", size=18, bold=True, color=INK)
    details = [
        ("Hook 大字引用",      "30 字内一句话定位，看一眼就知道这集讲什么。"),
        ("Sticky 原音频",      "往下滚永远在顶，边读章节边听原音频。"),
        ("章节引用可点击",      "段内字符位置线性插值得毫秒时间戳，点击 seek + 自动播放 + 滚动跟随。"),
        ("AI Digest 彩虹按钮",  "流动渐变，视觉上与黑色原音频按钮一眼区分。"),
    ]
    cw = Inches(2.95); ch = Inches(1.65); gap = Inches(0.13)
    for i, (t, d) in enumerate(details):
        x = Inches(0.6) + i*(cw+gap); y = Inches(4.95)
        add_card(s, x, y, cw, ch)
        add_text(s, x+Inches(0.2), y+Inches(0.15), cw-Inches(0.3), Inches(0.45),
                 f"0{i+1}", size=14, bold=True, color=ACCENT, font=FONT_EN)
        add_text(s, x+Inches(0.2), y+Inches(0.5), cw-Inches(0.3), Inches(0.4),
                 t, size=13, bold=True, color=INK)
        add_text(s, x+Inches(0.2), y+Inches(0.9), cw-Inches(0.3), Inches(1.0),
                 d, size=11, color=SUB)
    footer(s, 4)


# ===== P5 · 后端 6 层 + 前后端连接 =====
def slide_p5():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 5, "后端（6 层）+ 前后端连接", "FastAPI · asyncio · SQLite · 本地文件")

    # left: 6 layers stack
    layers = [
        ("Layer 1", "API",          "api/",          "FastAPI 路由 + WebSocket 端点", ACCENT),
        ("Layer 2", "Services",     "services/",     "Pipeline runner · 任务编排 · 重试", RGBColor(0x5E,0x5C,0xE6)),
        ("Layer 3", "Domain",       "domain/",       "纯函数：解析 · 分段 · quote 校验 · prompt 装配", RGBColor(0xAF,0x52,0xDE)),
        ("Layer 4", "Exporters",    "exporters/",    "Markdown / JSON 产物生成", RGBColor(0xFF,0x9F,0x0A)),
        ("Layer 5", "Persistence",  "persistence/",  "SQLAlchemy 2 + Alembic migrations", RGBColor(0x32,0xAD,0xE6)),
        ("Layer 6", "Config",       "config.py",     ".env + Pydantic settings", RGBColor(0x8E,0x8E,0x93)),
    ]
    x0, y0 = Inches(0.6), Inches(1.85)
    lw, lh = Inches(7.5), Inches(0.7); gap = Inches(0.08)
    for i, (no, name, path, desc, color) in enumerate(layers):
        y = y0 + i*(lh+gap)
        # accent strip
        strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x0, y, Inches(0.12), lh)
        strip.fill.solid(); strip.fill.fore_color.rgb = color; strip.line.fill.background()
        # card
        card = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x0+Inches(0.12), y, lw-Inches(0.12), lh)
        card.fill.solid(); card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = LINE; card.line.width = Pt(0.5)
        add_text(s, x0+Inches(0.3), y+Inches(0.1), Inches(0.9), Inches(0.4),
                 no, size=10, bold=True, color=SUB, font=FONT_EN)
        add_text(s, x0+Inches(0.3), y+Inches(0.32), Inches(1.6), Inches(0.4),
                 name, size=15, bold=True, color=INK)
        add_text(s, x0+Inches(1.95), y+Inches(0.35), Inches(1.5), Inches(0.4),
                 path, size=11, color=ACCENT, font=FONT_EN)
        add_text(s, x0+Inches(3.5), y+Inches(0.32), Inches(4), Inches(0.4),
                 desc, size=11, color=SUB)

    # right: connection diagram
    rx = Inches(8.4); ry = Inches(1.85); rw = Inches(4.33); rh = Inches(5.0)
    add_card(s, rx, ry, rw, rh)
    add_text(s, rx+Inches(0.3), ry+Inches(0.2), rw-Inches(0.6), Inches(0.4),
             "前后端连接", size=15, bold=True, color=INK)
    # frontend box
    fe = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                            rx+Inches(0.5), ry+Inches(0.75), rw-Inches(1), Inches(0.8))
    fe.adjustments[0]=0.1; fe.fill.solid(); fe.fill.fore_color.rgb = RGBColor(0xEC,0xEC,0xF0)
    fe.line.color.rgb = LINE
    add_text(s, rx+Inches(0.6), ry+Inches(0.85), rw-Inches(1.2), Inches(0.3),
             "Frontend v1 / v2", size=12, bold=True, color=INK)
    add_text(s, rx+Inches(0.6), ry+Inches(1.15), rw-Inches(1.2), Inches(0.3),
             "React · Vite · WS client", size=10, color=SUB)
    # arrows label
    add_text(s, rx+Inches(0.3), ry+Inches(1.7), rw-Inches(0.6), Inches(0.35),
             "↓  HTTP /api  ·  WS /api/ws/jobs  ↑", size=11, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
    # backend box
    be = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                            rx+Inches(0.5), ry+Inches(2.15), rw-Inches(1), Inches(0.8))
    be.adjustments[0]=0.1; be.fill.solid(); be.fill.fore_color.rgb = INK; be.line.fill.background()
    add_text(s, rx+Inches(0.6), ry+Inches(2.25), rw-Inches(1.2), Inches(0.3),
             "FastAPI :8000", size=12, bold=True, color=WHITE)
    add_text(s, rx+Inches(0.6), ry+Inches(2.55), rw-Inches(1.2), Inches(0.3),
             "uvicorn · asyncio runner", size=10, color=RGBColor(0xA8,0xA8,0xB0))
    # bullets
    bullets = [
        "REST 调度 episode 生命周期",
        "WS 单条长连接广播 stage 事件",
        "make serve 同时出 SPA + 静态产物",
        "契约：http-api.md / job-events.md",
    ]
    yy = ry+Inches(3.2)
    for b in bullets:
        add_text(s, rx+Inches(0.4), yy, rw-Inches(0.6), Inches(0.35),
                 "•  " + b, size=11, color=INK)
        yy += Inches(0.4)
    footer(s, 5)


# ===== P6 · API =====
def slide_p6():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 6, "API", "REST + WebSocket 契约")

    rows = [
        ("POST",   "/api/episodes",                "提交（local_file / direct_url / youtube）"),
        ("GET",    "/api/episodes",                "列表（cursor 分页 + status 过滤）"),
        ("GET",    "/api/episodes/{id}",           "详情（章节 · 引用 · 实体 · stage 状态）"),
        ("DELETE", "/api/episodes/{id}",           "删除（CASCADE + 物理目录清理）"),
        ("POST",   "/api/episodes/{id}/retry",     "从最近 checkpoint 恢复"),
        ("POST",   "/api/episodes/{id}/digest",    "触发 TTS 浓缩生成"),
        ("GET",    "/api/episodes/{id}/audio",     "Range 请求原音频流（206）"),
        ("WS",     "/api/ws/jobs",                 "实时 stage 进度事件"),
    ]
    color_map = {
        "POST":   RGBColor(0x1F,0x8A,0x4C),
        "GET":    ACCENT,
        "DELETE": RGBColor(0xC0,0x3A,0x2B),
        "WS":     RGBColor(0xAF,0x52,0xDE),
    }
    x0, y0 = Inches(0.6), Inches(1.85)
    row_h = Inches(0.46)
    for i, (m, path, desc) in enumerate(rows):
        y = y0 + i*row_h
        # zebra bg
        bg = WHITE if i % 2 == 0 else RGBColor(0xF0,0xF0,0xF3)
        bgr = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x0, y, Inches(12.13), row_h)
        bgr.fill.solid(); bgr.fill.fore_color.rgb = bg; bgr.line.fill.background()
        add_pill(s, x0+Inches(0.15), y+Inches(0.08), m, fill=color_map[m], fg=WHITE, size=10)
        add_text(s, x0+Inches(1.4), y+Inches(0.1), Inches(4.5), Inches(0.35),
                 path, size=13, bold=True, color=INK, font=FONT_EN)
        add_text(s, x0+Inches(5.9), y+Inches(0.12), Inches(6), Inches(0.35),
                 desc, size=12, color=SUB)

    # error code strip
    err_y = Inches(5.85)
    add_card(s, Inches(0.6), err_y, Inches(12.13), Inches(1.0), fill=RGBColor(0xEC,0xEC,0xF0))
    add_text(s, Inches(0.85), err_y+Inches(0.12), Inches(12), Inches(0.35),
             "统一错误码", size=12, bold=True, color=INK)
    codes = "bad_input  ·  not_found  ·  conflict  ·  payload_too_large  ·  unsupported_media  ·  upstream_failed  ·  internal"
    add_text(s, Inches(0.85), err_y+Inches(0.5), Inches(12), Inches(0.5),
             codes, size=12, color=ACCENT, font=FONT_EN)
    footer(s, 6)


# ===== P7 · 视频 =====
def slide_p7():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 7, "视频", "现场 demo · 60 秒完整流程")

    # left: QR placeholder
    qx, qy = Inches(2.0), Inches(2.3)
    qs = Inches(3.8)
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, qx, qy, qs, qs)
    box.fill.solid(); box.fill.fore_color.rgb = WHITE
    box.line.color.rgb = INK; box.line.width = Pt(1.5)
    # diagonal markings to look like a placeholder
    add_text(s, qx, qy+qs/2-Inches(0.3), qs, Inches(0.6),
             "[ QR Code ]", size=24, bold=True, color=SUB, align=PP_ALIGN.CENTER, font=FONT_EN)
    add_text(s, qx, qy+qs/2+Inches(0.2), qs, Inches(0.4),
             "二维码占位", size=13, color=SUB, align=PP_ALIGN.CENTER)
    add_text(s, qx, qy+qs+Inches(0.2), qs, Inches(0.4),
             "扫码观看完整 demo", size=12, color=INK, align=PP_ALIGN.CENTER)

    # right: video covers what
    rx, ry, rw, rh = Inches(7.0), Inches(2.3), Inches(5.7), qs
    add_card(s, rx, ry, rw, rh)
    add_text(s, rx+Inches(0.3), ry+Inches(0.2), rw-Inches(0.6), Inches(0.4),
             "视频涵盖", size=15, bold=True, color=INK)
    steps = [
        "① 粘贴 YouTube / Bilibili / mp3 链接",
        "② WS 实时进度（下载→ASR→摘要→章节→TTS）",
        "③ 详情页 hook / 三幕 / 章节时间轴",
        "④ 点击章节引用 → 原音频 seek + 自动播放",
        "⑤ 一键生成 30 秒 AI Digest 浓缩音频",
        "⑥ 下载 Markdown / JSON / MP3",
    ]
    yy = ry+Inches(0.75)
    for st in steps:
        add_text(s, rx+Inches(0.3), yy, rw-Inches(0.6), Inches(0.4),
                 st, size=13, color=INK)
        yy += Inches(0.45)
    footer(s, 7)


# ===== P8 · Bug =====
def slide_p8():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 8, "Bug · 已解决 / 未解决", "6 个 hard-won bug + 后续工作")

    add_pill(s, Inches(0.6), Inches(1.75), "已解决", fill=OK)

    bugs = [
        ("1", "TTS 401",                 "Auth 头要 `Bearer;<token>` 用分号",  False),
        ("2", "TTS 400 max len",         "v1 单次 ≤ 1024 字节 → 按字节切句",   False),
        ("3", "BigTTS concurrency",      "resource_id 应为 seed-tts-2.0",     True),
        ("4", "digest.mp3 为空无错",      "mixed 路由到英文音色被静默丢弃",     False),
        ("5", "多 quote 时间戳一样",       "段内字符位置线性插值修复",          True),
        ("6", "Retry worker 崩",         "unique 约束撞车 + 前置清理",         False),
    ]
    x0, y0 = Inches(0.6), Inches(2.2)
    cw, ch = Inches(4.0), Inches(0.85); gap_x = Inches(0.1); gap_y = Inches(0.1)
    for i, (n, sym, fix, warn) in enumerate(bugs):
        col = i % 3; row = i // 3
        x = x0 + col*(cw+gap_x); y = y0 + row*(ch+gap_y)
        add_card(s, x, y, cw, ch)
        # number circle
        circ = s.shapes.add_shape(MSO_SHAPE.OVAL, x+Inches(0.18), y+Inches(0.18),
                                  Inches(0.5), Inches(0.5))
        circ.fill.solid()
        circ.fill.fore_color.rgb = WARN if warn else INK
        circ.line.fill.background()
        add_text(s, x+Inches(0.18), y+Inches(0.22), Inches(0.5), Inches(0.4),
                 n, size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font=FONT_EN)
        flag = "  ⚠" if warn else ""
        add_text(s, x+Inches(0.8), y+Inches(0.12), cw-Inches(0.9), Inches(0.35),
                 sym + flag, size=13, bold=True, color=INK)
        add_text(s, x+Inches(0.8), y+Inches(0.45), cw-Inches(0.9), Inches(0.4),
                 fix, size=10, color=SUB)

    # unresolved
    uy = Inches(4.6)
    add_pill(s, Inches(0.6), uy, "未解决 / 后续", fill=RGBColor(0xC0,0x3A,0x2B))
    todo = [
        "5 集真实播客的人工准确率评估",
        "60 分钟样本 ASR/LLM/TTS 分阶段耗时 benchmark",
        "多语言混合内容的同语言摘要质量优化",
        "Doubao 云端 smoke fixture（应对 provider API 变化）",
        "前端 Playwright E2E（batch · quote seek · digest retry）",
    ]
    yy = uy + Inches(0.5)
    for t in todo:
        add_text(s, Inches(0.85), yy, Inches(12), Inches(0.3),
                 "•  " + t, size=12, color=INK)
        yy += Inches(0.35)
    footer(s, 8)


# ===== P9 · 小组贡献表 =====
def slide_p9():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 9, "小组贡献表", "Group 1 · 2026.05")

    headers = ["成员", "角色", "主要贡献", "工时占比"]
    rows = [
        ["[姓名 A]", "[角色]", "[模块 / 任务]", "[%]"],
        ["[姓名 B]", "[角色]", "[模块 / 任务]", "[%]"],
        ["[姓名 C]", "[角色]", "[模块 / 任务]", "[%]"],
        ["[姓名 D]", "[角色]", "[模块 / 任务]", "[%]"],
    ]
    col_w = [Inches(2.0), Inches(2.5), Inches(6.13), Inches(1.5)]
    x0, y0 = Inches(0.6), Inches(1.95)
    row_h_head = Inches(0.5); row_h = Inches(0.7)
    # header
    x = x0
    for ci, h in enumerate(headers):
        cell = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y0, col_w[ci], row_h_head)
        cell.fill.solid(); cell.fill.fore_color.rgb = INK; cell.line.fill.background()
        tf = cell.text_frame; tf.margin_left = Inches(0.2); tf.margin_top = Inches(0.1)
        p = tf.paragraphs[0]; r = p.add_run(); r.text = h
        r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT
        x += col_w[ci]
    # body
    for ri, row in enumerate(rows):
        y = y0 + row_h_head + ri*row_h
        x = x0
        bg = WHITE if ri % 2 == 0 else RGBColor(0xF0,0xF0,0xF3)
        for ci, val in enumerate(row):
            cell = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, col_w[ci], row_h)
            cell.fill.solid(); cell.fill.fore_color.rgb = bg
            cell.line.color.rgb = LINE; cell.line.width = Pt(0.5)
            tf = cell.text_frame; tf.margin_left = Inches(0.2); tf.margin_top = Inches(0.18)
            p = tf.paragraphs[0]; r = p.add_run(); r.text = val
            r.font.size = Pt(13); r.font.color.rgb = SUB; r.font.name = FONT
            x += col_w[ci]

    add_text(s, Inches(0.6), Inches(5.95), Inches(12), Inches(0.4),
             "占位 · 成员名单与分工由小组核对后填入。",
             size=11, color=SUB)
    add_text(s, Inches(0.6), Inches(6.6), Inches(12), Inches(0.4),
             "AI 是工具，不是答案。这套东西是查出来的、设计出来的、写出来的。",
             size=14, bold=True, color=INK, align=PP_ALIGN.CENTER)
    footer(s, 9)


# build
slide_cover()
slide_p1()
slide_p2()
slide_p3()
slide_p4()
slide_p5()
slide_p6()
slide_p7()
slide_p8()
slide_p9()

prs.save(OUT)
print(f"Saved: {OUT}")
