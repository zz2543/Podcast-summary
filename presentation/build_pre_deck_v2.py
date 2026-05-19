"""Build Pre deck v2 — Dark Editorial style.

Output: GotIt-Pre-deck-v2.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

OUT = Path(__file__).resolve().parent / "GotIt-Pre-deck-v2.pptx"

# ===== Dark Editorial palette =====
BG       = RGBColor(0x0B, 0x0E, 0x16)   # near-black navy
PANEL    = RGBColor(0x14, 0x18, 0x24)   # card fill
PANEL2   = RGBColor(0x1B, 0x20, 0x2E)   # card fill emphasized
LINE     = RGBColor(0x2A, 0x30, 0x42)
INK      = RGBColor(0xF2, 0xF4, 0xF8)
SUB      = RGBColor(0x9B, 0xA3, 0xB4)
MUTE     = RGBColor(0x60, 0x68, 0x7A)
ACCENT   = RGBColor(0x7C, 0xF0, 0xCB)   # mint green
ACCENT2  = RGBColor(0xC4, 0x8BFF & 0xFF, 0xFF)  # placeholder, redefined below
ACCENT2  = RGBColor(0xB6, 0x8BFF & 0xFF, 0xFF)
ACCENT2  = RGBColor(0xB7, 0x8DFF & 0xFF, 0xFF)
# clean redefine
ACCENT   = RGBColor(0x7C, 0xF0, 0xCB)   # mint
MAG      = RGBColor(0xFF, 0x4D, 0x8D)   # magenta
AMBER    = RGBColor(0xFF, 0xB7, 0x4D)   # amber
SKY      = RGBColor(0x6C, 0xC8, 0xFF)   # sky blue
VIOLET   = RGBColor(0xB6, 0x8DFF & 0xFF, 0xFF)
VIOLET   = RGBColor(0xB6, 0x8D, 0xFF)
RED      = RGBColor(0xFF, 0x6B, 0x6B)
OK       = ACCENT
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
BLACK    = RGBColor(0x00, 0x00, 0x00)

FONT = "PingFang SC"
FONT_EN = "SF Pro Display"
FONT_MONO = "JetBrains Mono"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


# ---------- helpers ----------
def add_bg(slide, color=BG):
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    rect.line.fill.background()
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.shadow.inherit = False
    return rect


def add_text(slide, x, y, w, h, text, *, size=18, bold=False, color=INK,
             align=PP_ALIGN.LEFT, font=FONT, italic=False, letter_space=None):
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
        r.font.italic = italic
        r.font.name = font
        r.font.color.rgb = color
    return tb


def add_rect(slide, x, y, w, h, *, fill=PANEL, border=None, border_w=0.5, radius=None):
    shp = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(shp, x, y, w, h)
    if radius is not None:
        s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if border is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = border
        s.line.width = Pt(border_w)
    s.shadow.inherit = False
    return s


def add_pill(slide, x, y, text, *, fill=INK, fg=BG, size=10, padding_em=0.65):
    w = Inches(0.5 + padding_em * len(text) * 0.16)
    # better width estimate
    w = Inches(max(0.6, 0.16 * len(text) + 0.4))
    h = Inches(0.3)
    s = add_rect(slide, x, y, w, h, fill=fill, radius=0.5)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = Inches(0.1)
    tf.margin_top = tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = True; r.font.name = FONT_EN
    r.font.color.rgb = fg
    return s


def add_rule(slide, x, y, w, color=LINE, weight=0.75):
    line = slide.shapes.add_connector(1, x, y, x + w, y)
    line.line.color.rgb = color
    line.line.width = Pt(weight)
    return line


def add_vbar(slide, x, y, h, color=ACCENT, w=Inches(0.08)):
    """Vertical accent bar."""
    b = add_rect(slide, x, y, w, h, fill=color)
    return b


def page_header(slide, num, kicker, title, accent=ACCENT):
    # left accent vertical bar
    add_vbar(slide, Inches(0.6), Inches(0.6), Inches(0.95), color=accent)
    # number
    add_text(slide, Inches(0.85), Inches(0.55), Inches(2), Inches(0.45),
             f"P{num:02d}", size=14, bold=True, color=accent, font=FONT_EN)
    # kicker
    add_text(slide, Inches(0.85), Inches(0.95), Inches(8), Inches(0.4),
             kicker.upper(), size=10, bold=True, color=SUB,
             font=FONT_EN)
    # title
    add_text(slide, Inches(0.6), Inches(1.65), Inches(12.1), Inches(0.85),
             title, size=36, bold=True, color=INK)
    add_rule(slide, Inches(0.6), Inches(2.55), Inches(12.13), color=LINE)


def footer(slide, num, total=9, section=""):
    add_text(slide, Inches(0.6), Inches(7.1), Inches(8), Inches(0.3),
             "GotIt  /  Podcast-Summary  /  Group 1  ·  2026.05",
             size=9, color=MUTE, font=FONT_EN)
    add_text(slide, Inches(8.6), Inches(7.1), Inches(4.13), Inches(0.3),
             f"{num:02d} / {total:02d}",
             size=9, color=MUTE, align=PP_ALIGN.RIGHT, font=FONT_EN)


# ============== Cover ==============
def slide_cover():
    s = prs.slides.add_slide(BLANK); add_bg(s)

    # ambient gradient: simulate with two soft rounded blurred shapes
    blob1 = add_rect(s, Inches(-2), Inches(-2), Inches(8), Inches(8),
                     fill=RGBColor(0x14, 0x2E, 0x3D), radius=0.5)
    blob1.line.fill.background()
    blob2 = add_rect(s, Inches(7.5), Inches(3), Inches(9), Inches(7),
                     fill=RGBColor(0x2A, 0x1A, 0x3A), radius=0.5)
    blob2.line.fill.background()

    # grid lines (subtle)
    for i in range(1, 12):
        add_rule(s, Inches(i*1.1), Inches(0), Inches(0),
                 color=RGBColor(0x18, 0x1C, 0x28))  # invisible-ish

    # number plate
    add_text(s, Inches(0.7), Inches(0.55), Inches(4), Inches(0.4),
             "—  CASE  STUDY  /  01",
             size=11, bold=True, color=ACCENT, font=FONT_EN)

    # title big
    add_text(s, Inches(0.7), Inches(2.2), Inches(12), Inches(1.3),
             "GotIt",
             size=96, bold=True, color=INK, font=FONT_EN)
    add_text(s, Inches(0.7), Inches(3.5), Inches(12), Inches(0.8),
             "本地端到端播客摘要工具",
             size=34, bold=True, color=INK)
    add_text(s, Inches(0.7), Inches(4.25), Inches(12), Inches(0.6),
             "把一小时播客 / 压成几分钟看得懂、三十秒听得完的浓缩。",
             size=16, color=SUB)

    # meta row
    add_rule(s, Inches(0.7), Inches(6.4), Inches(12), color=LINE)
    add_text(s, Inches(0.7), Inches(6.55), Inches(4), Inches(0.4),
             "GROUP 1", size=11, bold=True, color=INK, font=FONT_EN)
    add_text(s, Inches(0.7), Inches(6.85), Inches(4), Inches(0.4),
             "Presenters", size=9, color=MUTE, font=FONT_EN)

    add_text(s, Inches(5.3), Inches(6.55), Inches(4), Inches(0.4),
             "2026.05", size=11, bold=True, color=INK, font=FONT_EN)
    add_text(s, Inches(5.3), Inches(6.85), Inches(4), Inches(0.4),
             "Date", size=9, color=MUTE, font=FONT_EN)

    add_text(s, Inches(9.0), Inches(6.55), Inches(4), Inches(0.4),
             "PODCAST-SUMMARY", size=11, bold=True, color=INK, font=FONT_EN)
    add_text(s, Inches(9.0), Inches(6.85), Inches(4), Inches(0.4),
             "Project", size=9, color=MUTE, font=FONT_EN)


# ============== P1 · 背景 ==============
def slide_p1():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 1, "context  /  background", "我们想解决一件什么事？", accent=ACCENT)

    # left big stat block
    add_rect(s, Inches(0.6), Inches(2.95), Inches(5.6), Inches(3.9),
             fill=PANEL, radius=0.04)
    add_text(s, Inches(0.95), Inches(3.15), Inches(5), Inches(0.4),
             "EPISODE  DURATION", size=10, bold=True, color=ACCENT, font=FONT_EN)
    add_text(s, Inches(0.95), Inches(3.55), Inches(5), Inches(1.6),
             "40–90", size=88, bold=True, color=INK, font=FONT_EN)
    add_text(s, Inches(0.95), Inches(5.25), Inches(5), Inches(0.4),
             "分钟 / 集", size=18, color=SUB)
    add_text(s, Inches(0.95), Inches(5.95), Inches(5), Inches(0.8),
             "听完成本高、时间不可逆——\n用户最想要的是“先判断、后回听”。",
             size=13, color=SUB)

    # right list — three pain points + one proposition
    items = [
        ("01", "用户三问",
         "讲了啥？/ 值不值得听？/ 哪里值得回头？", SKY),
        ("02", "现有工具痛点",
         "Otter 太重 · YouTube 字幕无章节 · 生转录稿不浓缩。", AMBER),
        ("03", "我们的定位",
         "给一个链接 → hook + 三幕 + 章节 + 引用 + 实体 + 30s TTS 浓缩。", ACCENT),
    ]
    y = Inches(2.95)
    for no, t, d, c in items:
        add_rect(s, Inches(6.5), y, Inches(6.23), Inches(1.2),
                 fill=PANEL, radius=0.04)
        add_vbar(s, Inches(6.5), y, Inches(1.2), color=c)
        add_text(s, Inches(6.75), y+Inches(0.18), Inches(1), Inches(0.4),
                 no, size=18, bold=True, color=c, font=FONT_EN)
        add_text(s, Inches(7.55), y+Inches(0.2), Inches(5), Inches(0.4),
                 t, size=15, bold=True, color=INK)
        add_text(s, Inches(7.55), y+Inches(0.6), Inches(5.0), Inches(0.6),
                 d, size=11, color=SUB)
        y += Inches(1.35)
    footer(s, 1)


# ============== P2 · 我们学到的 ==============
def slide_p2():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 2, "learnings  /  takeaways", "我们学到的四件事", accent=VIOLET)

    items = [
        ("01", "先写规范，再写代码",
         "12 份 spec + 5 条 constitution\nspec → plan → tasks → code",
         "Spec-Driven", VIOLET),
        ("02", "AI 是协作伙伴，不是答案",
         "6 个 hard-won bug 没有一个 AI 一上来能答\n靠人读响应、读协议、读 DB",
         "Human-in-Loop", MAG),
        ("03", "trade-off 是工程的本质",
         "本地自用刻意不上 Redis/Celery/Postgres\n每一层都给扩展留口子",
         "Pragmatic", AMBER),
        ("04", "测试是护栏，不是 KPI",
         "domain ≥ 80% 覆盖率硬门\n每修一个 bug 同步加回归测试",
         "Test-Guarded", ACCENT),
    ]

    gx, gy = Inches(0.6), Inches(2.95)
    cw, ch = Inches(6.0), Inches(1.95)
    gap = Inches(0.13)
    pos = [(0,0),(1,0),(0,1),(1,1)]
    for (col,row),(no, t, body, tag, c) in zip(pos, items):
        x = gx + col*(cw+gap); y = gy + row*(ch+gap)
        add_rect(s, x, y, cw, ch, fill=PANEL, radius=0.04)
        # big number
        add_text(s, x+Inches(0.3), y+Inches(0.15), Inches(1.5), Inches(0.8),
                 no, size=46, bold=True, color=c, font=FONT_EN)
        # tag
        add_pill(s, x+cw-Inches(1.8), y+Inches(0.25), tag, fill=c, fg=BG, size=9)
        # title
        add_text(s, x+Inches(0.3), y+Inches(0.95), cw-Inches(0.6), Inches(0.45),
                 t, size=17, bold=True, color=INK)
        # body
        add_text(s, x+Inches(0.3), y+Inches(1.4), cw-Inches(0.6), Inches(0.6),
                 body, size=11, color=SUB)
    footer(s, 2)


# ============== P3 · 功能边界 ==============
def slide_p3():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 3, "scope  /  boundary", "做什么 · 不做什么", accent=ACCENT)

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

    cw = Inches(6.0); ch = Inches(3.7)
    # left card — DO
    add_rect(s, Inches(0.6), Inches(2.95), cw, ch, fill=PANEL, radius=0.04)
    add_vbar(s, Inches(0.6), Inches(2.95), ch, color=ACCENT)
    add_text(s, Inches(0.9), Inches(3.1), Inches(2), Inches(0.4),
             "IN  SCOPE", size=11, bold=True, color=ACCENT, font=FONT_EN)
    add_text(s, Inches(0.9), Inches(3.45), Inches(4), Inches(0.5),
             "已经做了的能力", size=19, bold=True, color=INK)
    yy = Inches(4.15)
    for line in do:
        add_text(s, Inches(0.9), yy, cw-Inches(0.4), Inches(0.4),
                 "▸  " + line, size=12, color=INK)
        yy += Inches(0.38)

    # right card — DON'T
    add_rect(s, Inches(6.73), Inches(2.95), cw, ch, fill=PANEL, radius=0.04)
    add_vbar(s, Inches(6.73), Inches(2.95), ch, color=RED)
    add_text(s, Inches(7.03), Inches(3.1), Inches(2), Inches(0.4),
             "OUT  OF  SCOPE", size=11, bold=True, color=RED, font=FONT_EN)
    add_text(s, Inches(7.03), Inches(3.45), Inches(4), Inches(0.5),
             "v1 明确不做", size=19, bold=True, color=INK)
    yy = Inches(4.15)
    for line in dont:
        add_text(s, Inches(7.03), yy, cw-Inches(0.4), Inches(0.4),
                 "✕  " + line, size=12, color=SUB)
        yy += Inches(0.38)

    # constraints strip
    add_rect(s, Inches(0.6), Inches(6.75), Inches(12.13), Inches(0.5),
             fill=PANEL2, radius=0.3)
    add_text(s, Inches(0.85), Inches(6.83), Inches(2.5), Inches(0.35),
             "CONSTRAINTS", size=9, bold=True, color=ACCENT, font=FONT_EN)
    add_text(s, Inches(2.7), Inches(6.83), Inches(10), Inches(0.35),
             "单用户  ·  127.0.0.1 loopback  ·  单进程 asyncio  ·  SQLite + 本地文件",
             size=11, color=INK, font=FONT_EN)
    footer(s, 3)


# ============== P4 · 前端 ==============
def slide_p4():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 4, "frontend  /  ui", "两套并行 UI，共享同一个后端", accent=SKY)

    # split: left big v1/v2 compare, right details
    # left compare table
    add_rect(s, Inches(0.6), Inches(2.95), Inches(7.4), Inches(3.9),
             fill=PANEL, radius=0.04)
    add_text(s, Inches(0.85), Inches(3.1), Inches(7), Inches(0.4),
             "V1  vs  V2  —  并行视觉实验", size=11, bold=True, color=SKY, font=FONT_EN)

    rows = [
        ("",      "v1 (:5173)",            "v2 (:5174)"),
        ("样式",  "纯 CSS + 渐变",          "Tailwind + Liquid Glass"),
        ("动效",  "无",                     "framer-motion + Aceternity"),
        ("风格",  "功能优先",                "内容优先 · 克制配色"),
        ("用途",  "当前主力",                "A/B 视觉实验"),
    ]
    x0, y0 = Inches(0.85), Inches(3.55)
    col_w = [Inches(1.3), Inches(2.9), Inches(2.95)]
    row_h = Inches(0.5)
    for ri, row in enumerate(rows):
        x = x0
        for ci, val in enumerate(row):
            is_head = (ri == 0)
            fill = PANEL2 if is_head else BG
            add_rect(s, x, y0+ri*row_h, col_w[ci], row_h,
                     fill=fill, border=LINE, border_w=0.4)
            tf_color = SKY if is_head else (INK if ci == 0 else SUB)
            font_used = FONT_EN if is_head and ci > 0 else FONT
            add_text(s, x+Inches(0.18), y0+ri*row_h+Inches(0.13),
                     col_w[ci]-Inches(0.2), Inches(0.4),
                     val, size=12, bold=(is_head or ci==0),
                     color=tf_color, font=font_used)
            x += col_w[ci]

    # right: 4 detail tiles
    add_text(s, Inches(8.3), Inches(3.1), Inches(4.5), Inches(0.4),
             "详情页 · 4 个打磨细节", size=11, bold=True, color=SKY, font=FONT_EN)

    details = [
        ("Hook 大字引用",     "30 字内一句话定位"),
        ("Sticky 原音频",     "滚动时永远在顶部"),
        ("章节引用可点击",     "字符位置插值 → 毫秒 seek"),
        ("AI Digest 彩虹按钮", "区别于黑色原音频按钮"),
    ]
    dx, dy = Inches(8.3), Inches(3.55)
    dw, dh = Inches(2.18), Inches(1.55)
    for i, (t, d) in enumerate(details):
        col = i % 2; row = i // 2
        x = dx + col*(dw+Inches(0.09)); y = dy + row*(dh+Inches(0.1))
        add_rect(s, x, y, dw, dh, fill=PANEL, radius=0.04)
        add_text(s, x+Inches(0.2), y+Inches(0.15), Inches(0.6), Inches(0.4),
                 f"0{i+1}", size=14, bold=True, color=SKY, font=FONT_EN)
        add_text(s, x+Inches(0.2), y+Inches(0.55), dw-Inches(0.3), Inches(0.5),
                 t, size=12, bold=True, color=INK)
        add_text(s, x+Inches(0.2), y+Inches(1.0), dw-Inches(0.3), Inches(0.5),
                 d, size=10, color=SUB)
    footer(s, 4)


def slide_p5():
    """Backend page — talk about the pipeline (the real story)."""
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 5, "backend  /  pipeline", "后端做的事 · 一条 8 段流水线", accent=MAG)

    # ---- top: 8-stage pipeline as horizontal flow ----
    stages = [
        ("01", "fetch",         "yt-dlp + ffmpeg",     SKY),
        ("02", "transcribe",    "豆包 ASR",             SKY),
        ("03", "hook",          "DeepSeek",             VIOLET),
        ("04", "three-act",     "DeepSeek",             VIOLET),
        ("05", "chapters",      "DeepSeek",             VIOLET),
        ("06", "quote-verify",  "自研插值",              MAG),
        ("07", "entities",      "DeepSeek",             VIOLET),
        ("08", "export",        "md + json",            AMBER),
    ]
    px = Inches(0.6); py = Inches(2.85)
    pw_total = Inches(12.13)
    cw = Inches(1.42); gap = (pw_total - cw*8) / 7
    for i, (no, name, prov, c) in enumerate(stages):
        x = px + i*(cw + gap)
        add_rect(s, x, py, cw, Inches(1.55), fill=PANEL, radius=0.06)
        add_vbar(s, x, py, Inches(1.55), color=c, w=Inches(0.06))
        add_text(s, x+Inches(0.18), py+Inches(0.15), cw-Inches(0.25), Inches(0.35),
                 no, size=10, bold=True, color=c, font=FONT_EN)
        add_text(s, x+Inches(0.18), py+Inches(0.5), cw-Inches(0.25), Inches(0.45),
                 name, size=13, bold=True, color=INK, font=FONT_EN)
        add_text(s, x+Inches(0.18), py+Inches(1.05), cw-Inches(0.25), Inches(0.4),
                 prov, size=9, color=SUB)
    # TTS side branch label
    add_text(s, Inches(0.6), Inches(4.55), Inches(12.13), Inches(0.3),
             "＋  digest (TTS · 豆包 BigTTS 2.0)  —  按钮触发的独立子 pipeline",
             size=10, color=AMBER, font=FONT_EN, align=PP_ALIGN.CENTER)

    # ---- bottom-left: 工程决策 ----
    blx, bly = Inches(0.6), Inches(5.0)
    blw, blh = Inches(7.7), Inches(1.95)
    add_rect(s, blx, bly, blw, blh, fill=PANEL, radius=0.04)
    add_vbar(s, blx, bly, blh, color=ACCENT)
    add_text(s, blx+Inches(0.25), bly+Inches(0.15), Inches(6), Inches(0.35),
             "ENGINEERING  DECISIONS", size=10, bold=True, color=ACCENT, font=FONT_EN)
    decisions = [
        ("独立 retry",  "每个 stage tenacity 指数退避 · 单步失败不重跑整条作业"),
        ("进度落盘",    "stage_progress 写 SQLite · 进程重启可继续"),
        ("事件总线",    "状态变化广播到 WebSocket · 前端实时看进度"),
        ("单进程",      "asyncio 而非 Celery/Redis · 本地够用，留扩展口"),
    ]
    yy = bly+Inches(0.55)
    for k, v in decisions:
        add_text(s, blx+Inches(0.3), yy, Inches(1.6), Inches(0.3),
                 "▸ " + k, size=11, bold=True, color=INK)
        add_text(s, blx+Inches(2.0), yy, blw-Inches(2.2), Inches(0.3),
                 v, size=10, color=SUB)
        yy += Inches(0.32)

    # ---- bottom-right: 前后端连接 ----
    rx, ry = Inches(8.5), Inches(5.0)
    rw, rh = Inches(4.23), Inches(1.95)
    add_rect(s, rx, ry, rw, rh, fill=PANEL, radius=0.04)
    add_vbar(s, rx, ry, rh, color=MAG)
    add_text(s, rx+Inches(0.25), ry+Inches(0.15), Inches(4), Inches(0.35),
             "FRONT  ⇄  BACK", size=10, bold=True, color=MAG, font=FONT_EN)
    conn = [
        ("HTTP",   "/api/episodes/*  ·  调度生命周期"),
        ("WS",     "/api/ws/jobs  ·  广播 stage 事件"),
        ("Serve",  "make serve  →  SPA + 产物 一并出"),
        ("契约",   "contracts/http-api · job-events"),
    ]
    yy = ry+Inches(0.55)
    for k, v in conn:
        add_text(s, rx+Inches(0.3), yy, Inches(0.8), Inches(0.3),
                 k, size=10, bold=True, color=MAG, font=FONT_EN)
        add_text(s, rx+Inches(1.1), yy, rw-Inches(1.3), Inches(0.3),
                 v, size=10, color=INK)
        yy += Inches(0.32)
    footer(s, 5)


def _UNUSED_slide_p5_old():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 5, "backend  /  architecture", "DEPRECATED", accent=MAG)

    # left: 6 layers
    layers = [
        ("01", "API",          "api/",          "FastAPI 路由 + WebSocket 端点",      ACCENT),
        ("02", "Services",     "services/",     "Pipeline runner · 任务编排 · 重试",   VIOLET),
        ("03", "Domain",       "domain/",       "纯函数：解析 · 分段 · quote · prompt", MAG),
        ("04", "Exporters",    "exporters/",    "Markdown / JSON 产物生成",            AMBER),
        ("05", "Persistence",  "persistence/",  "SQLAlchemy 2 + Alembic migrations",  SKY),
        ("06", "Config",       "config.py",     ".env + Pydantic settings",           MUTE),
    ]
    x0, y0 = Inches(0.6), Inches(2.95)
    lw, lh = Inches(7.5), Inches(0.6); gap = Inches(0.07)
    for i, (no, name, path, desc, c) in enumerate(layers):
        y = y0 + i*(lh+gap)
        add_rect(s, x0, y, lw, lh, fill=PANEL, radius=0.04)
        add_vbar(s, x0, y, lh, color=c, w=Inches(0.1))
        add_text(s, x0+Inches(0.25), y+Inches(0.13), Inches(0.5), Inches(0.4),
                 no, size=10, bold=True, color=c, font=FONT_EN)
        add_text(s, x0+Inches(0.85), y+Inches(0.13), Inches(1.6), Inches(0.4),
                 name, size=14, bold=True, color=INK)
        add_text(s, x0+Inches(2.45), y+Inches(0.16), Inches(1.5), Inches(0.4),
                 path, size=10, color=c, font=FONT_MONO)
        add_text(s, x0+Inches(3.95), y+Inches(0.16), Inches(3.6), Inches(0.4),
                 desc, size=10, color=SUB)

    # right: connection
    rx, ry, rw, rh = Inches(8.4), Inches(2.95), Inches(4.33), Inches(3.9)
    add_rect(s, rx, ry, rw, rh, fill=PANEL, radius=0.04)
    add_text(s, rx+Inches(0.3), ry+Inches(0.2), rw-Inches(0.6), Inches(0.4),
             "前后端连接", size=11, bold=True, color=MAG, font=FONT_EN)
    # frontend box
    fe = add_rect(s, rx+Inches(0.45), ry+Inches(0.7),
                  rw-Inches(0.9), Inches(0.75),
                  fill=PANEL2, radius=0.15)
    add_text(s, rx+Inches(0.6), ry+Inches(0.78), rw-Inches(1.2), Inches(0.3),
             "Frontend v1 / v2", size=12, bold=True, color=INK)
    add_text(s, rx+Inches(0.6), ry+Inches(1.08), rw-Inches(1.2), Inches(0.3),
             "React · Vite · WS client", size=9, color=SUB, font=FONT_EN)
    # arrow label
    add_text(s, rx+Inches(0.3), ry+Inches(1.6), rw-Inches(0.6), Inches(0.3),
             "↕   HTTP /api    ·    WS /api/ws/jobs",
             size=10, bold=True, color=ACCENT, align=PP_ALIGN.CENTER, font=FONT_EN)
    # backend box
    be = add_rect(s, rx+Inches(0.45), ry+Inches(2.0),
                  rw-Inches(0.9), Inches(0.75),
                  fill=INK, radius=0.15)
    add_text(s, rx+Inches(0.6), ry+Inches(2.08), rw-Inches(1.2), Inches(0.3),
             "FastAPI :8000", size=12, bold=True, color=BG)
    add_text(s, rx+Inches(0.6), ry+Inches(2.38), rw-Inches(1.2), Inches(0.3),
             "uvicorn · asyncio runner", size=9, color=MUTE, font=FONT_EN)
    # bullets
    bullets = [
        "REST 调度 episode 生命周期",
        "WS 长连接广播 stage 事件",
        "make serve 同时出 SPA 与产物",
        "契约文件：http-api / job-events",
    ]
    yy = ry+Inches(2.95)
    for b in bullets:
        add_text(s, rx+Inches(0.4), yy, rw-Inches(0.6), Inches(0.3),
                 "•  " + b, size=10, color=INK)
        yy += Inches(0.22)
    footer(s, 5)


# ============== P6 · 接入的外部 API ==============
def slide_p6():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 6, "external  /  integrations", "接入的外部 API · 我们调了谁", accent=AMBER)

    # cards: ASR, LLM, TTS (default + fallback)
    cards = [
        {
            "tag": "ASR  ·  语音识别",
            "color": SKY,
            "title": "豆包 Seed-ASR 2.0",
            "vendor": "Volcengine / ByteDance",
            "rows": [
                ("接口", "submit → query (HTTPS 轮询)"),
                ("URL",  "openspeech.bytedance.com/api/v3/auc/bigmodel/*"),
                ("资源", "volc.seedasr.auc  ·  flash: volc.bigasr.auc_turbo"),
                ("回退", "Whisper (本地)  ·  Qwen ASR"),
            ],
        },
        {
            "tag": "LLM  ·  摘要 / 章节 / 实体",
            "color": ACCENT,
            "title": "DeepSeek Chat",
            "vendor": "DeepSeek",
            "rows": [
                ("模型", "deepseek-chat (OpenAI 兼容)"),
                ("URL",  "api.deepseek.com/v1/chat/completions"),
                ("用途", "Hook · 三幕 · 章节 outline · 实体抽取"),
                ("回退", "Qwen (qwen-max)  ·  Anthropic Claude"),
            ],
        },
        {
            "tag": "TTS  ·  30 秒 Digest",
            "color": MAG,
            "title": "豆包 BigTTS 2.0 (Seed-TTS)",
            "vendor": "Volcengine / ByteDance",
            "rows": [
                ("协议", "WebSocket 二进制双向流"),
                ("URL",  "wss://openspeech.bytedance.com/api/v3/tts/bidirection"),
                ("资源", "seed-tts-2.0  (字符版)"),
                ("回退", "Doubao TTS v1 (HTTP)  ·  Qwen CosyVoice v2"),
            ],
        },
    ]

    x0, y0 = Inches(0.6), Inches(2.95)
    cw, ch = Inches(4.0), Inches(3.5)
    gap = Inches(0.13)
    for i, card in enumerate(cards):
        x = x0 + i*(cw+gap)
        add_rect(s, x, y0, cw, ch, fill=PANEL, radius=0.04)
        add_vbar(s, x, y0, ch, color=card["color"], w=Inches(0.08))
        # tag
        add_text(s, x+Inches(0.25), y0+Inches(0.2), cw-Inches(0.4), Inches(0.4),
                 card["tag"], size=10, bold=True, color=card["color"], font=FONT_EN)
        # title
        add_text(s, x+Inches(0.25), y0+Inches(0.55), cw-Inches(0.4), Inches(0.55),
                 card["title"], size=18, bold=True, color=INK)
        # vendor
        add_text(s, x+Inches(0.25), y0+Inches(1.1), cw-Inches(0.4), Inches(0.35),
                 card["vendor"], size=10, color=SUB, font=FONT_EN, italic=True)
        # divider
        add_rule(s, x+Inches(0.25), y0+Inches(1.55), cw-Inches(0.5), color=LINE)
        # rows
        yy = y0+Inches(1.7)
        for label, val in card["rows"]:
            add_text(s, x+Inches(0.25), yy, Inches(0.7), Inches(0.3),
                     label, size=9, bold=True, color=card["color"], font=FONT_EN)
            add_text(s, x+Inches(0.25), yy+Inches(0.28), cw-Inches(0.5), Inches(0.4),
                     val, size=10, color=INK, font=FONT_MONO)
            yy += Inches(0.62)

    # bottom strip: extras
    add_rect(s, Inches(0.6), Inches(6.65), Inches(12.13), Inches(0.55),
             fill=PANEL2, radius=0.3)
    add_text(s, Inches(0.85), Inches(6.75), Inches(2.5), Inches(0.35),
             "ALSO  USED", size=9, bold=True, color=AMBER, font=FONT_EN)
    extras = "yt-dlp  (YouTube/Bilibili 下载)   ·   ffmpeg  (音频归一化/转 mp3)   ·   一行 env 切换 provider，调用代码零感知"
    add_text(s, Inches(2.7), Inches(6.78), Inches(10), Inches(0.35),
             extras, size=10, color=INK)
    footer(s, 6)


# ============== P7 · 视频 ==============
def slide_p7():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 7, "demo  /  video", "现场 demo · 60 秒完整流程", accent=AMBER)

    # left: QR placeholder
    qx, qy, qs = Inches(1.8), Inches(3.1), Inches(3.5)
    # frame
    add_rect(s, qx-Inches(0.15), qy-Inches(0.15), qs+Inches(0.3), qs+Inches(0.3),
             fill=PANEL2, radius=0.04)
    add_rect(s, qx, qy, qs, qs, fill=INK, radius=0.02)
    add_text(s, qx, qy+qs/2-Inches(0.4), qs, Inches(0.5),
             "[ QR Code ]", size=22, bold=True, color=BG,
             align=PP_ALIGN.CENTER, font=FONT_EN)
    add_text(s, qx, qy+qs/2+Inches(0.15), qs, Inches(0.4),
             "二维码占位", size=12, color=MUTE,
             align=PP_ALIGN.CENTER)
    add_text(s, qx-Inches(0.15), qy+qs+Inches(0.25), qs+Inches(0.3), Inches(0.4),
             "扫码观看完整 demo", size=12, color=INK,
             align=PP_ALIGN.CENTER)

    # right: steps
    rx, ry = Inches(6.5), Inches(2.95)
    rw, rh = Inches(6.23), Inches(3.9)
    add_rect(s, rx, ry, rw, rh, fill=PANEL, radius=0.04)
    add_text(s, rx+Inches(0.3), ry+Inches(0.2), rw-Inches(0.6), Inches(0.4),
             "VIDEO  COVERS", size=11, bold=True, color=AMBER, font=FONT_EN)
    add_text(s, rx+Inches(0.3), ry+Inches(0.55), rw-Inches(0.6), Inches(0.5),
             "六个步骤一次跑完", size=18, bold=True, color=INK)
    steps = [
        ("01", "粘贴 YouTube / Bilibili / mp3 链接"),
        ("02", "WS 实时进度（下载→ASR→摘要→章节→TTS）"),
        ("03", "详情页 hook / 三幕 / 章节时间轴"),
        ("04", "点击章节引用 → 原音频 seek + 自动播放"),
        ("05", "一键生成 30 秒 AI Digest 浓缩音频"),
        ("06", "下载 Markdown / JSON / MP3"),
    ]
    yy = ry+Inches(1.2)
    for no, t in steps:
        add_text(s, rx+Inches(0.3), yy, Inches(0.6), Inches(0.4),
                 no, size=12, bold=True, color=AMBER, font=FONT_EN)
        add_text(s, rx+Inches(0.9), yy, rw-Inches(1.1), Inches(0.4),
                 t, size=12, color=INK)
        yy += Inches(0.42)
    footer(s, 7)


# ============== P8 · Bug ==============
def slide_p8():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 8, "bugs  /  hard-won", "已解决 6 个 · 未解决 5 项", accent=RED)

    # resolved: 6 cards in 2x3
    add_pill(s, Inches(0.6), Inches(2.85), "RESOLVED  ·  6", fill=ACCENT, fg=BG, size=10)

    bugs = [
        ("1", "TTS 401",            "Auth 头要 Bearer;<token> 分号",     False),
        ("2", "TTS max-len 1024B",  "按 utf-8 字节切句拼装",              False),
        ("3", "BigTTS concurrency", "resource_id 应为 seed-tts-2.0",     True),
        ("4", "digest.mp3 空文件",   "mixed 错路由英文音色被静默丢弃",     False),
        ("5", "quote 时间戳一样",     "段内字符位置线性插值修复",          True),
        ("6", "Retry worker 崩",    "unique 撞车 + 前置清理",            False),
    ]
    x0, y0 = Inches(0.6), Inches(3.3)
    cw, ch = Inches(4.0), Inches(0.95)
    gap_x, gap_y = Inches(0.1), Inches(0.1)
    for i, (n, sym, fix, warn) in enumerate(bugs):
        col = i % 3; row = i // 3
        x = x0 + col*(cw+gap_x); y = y0 + row*(ch+gap_y)
        add_rect(s, x, y, cw, ch, fill=PANEL, radius=0.04)
        # number badge
        c = AMBER if warn else SUB
        add_vbar(s, x, y, ch, color=c, w=Inches(0.06))
        add_text(s, x+Inches(0.2), y+Inches(0.13), Inches(0.6), Inches(0.4),
                 f"#{n}", size=14, bold=True, color=c, font=FONT_EN)
        flag = "  ⚠" if warn else ""
        add_text(s, x+Inches(0.8), y+Inches(0.13), cw-Inches(0.9), Inches(0.4),
                 sym + flag, size=13, bold=True, color=INK)
        add_text(s, x+Inches(0.8), y+Inches(0.5), cw-Inches(0.9), Inches(0.4),
                 fix, size=10, color=SUB)

    # unresolved
    add_pill(s, Inches(0.6), Inches(5.5), "OPEN  ·  5", fill=RED, fg=INK, size=10)
    todo = [
        "5 集真实播客的人工准确率评估",
        "60 分钟样本 ASR/LLM/TTS 分阶段耗时 benchmark",
        "多语言混合内容的同语言摘要质量优化",
        "Doubao 云端 smoke fixture（应对 API 变化）",
        "前端 Playwright E2E（batch / quote seek / digest retry）",
    ]
    add_rect(s, Inches(0.6), Inches(5.95), Inches(12.13), Inches(1.0),
             fill=PANEL, radius=0.04)
    add_vbar(s, Inches(0.6), Inches(5.95), Inches(1.0), color=RED, w=Inches(0.06))
    # 5 items in single row
    iw = Inches(2.39); ix = Inches(0.75)
    for i, t in enumerate(todo):
        x = ix + i*(iw+Inches(0.0))
        add_text(s, x+Inches(0.1), Inches(6.05), iw-Inches(0.2), Inches(0.35),
                 f"0{i+1}", size=10, bold=True, color=RED, font=FONT_EN)
        add_text(s, x+Inches(0.1), Inches(6.4), iw-Inches(0.2), Inches(0.6),
                 t, size=9, color=INK)
    footer(s, 8)


# ============== P9 · 小组贡献 ==============
def slide_p9():
    s = prs.slides.add_slide(BLANK); add_bg(s)
    page_header(s, 9, "team  /  contribution", "小组贡献表", accent=ACCENT)

    headers = ["成员", "角色", "主要贡献", "工时占比"]
    rows = [
        ["[姓名 A]", "[角色]", "[模块 / 任务]", "[%]"],
        ["[姓名 B]", "[角色]", "[模块 / 任务]", "[%]"],
        ["[姓名 C]", "[角色]", "[模块 / 任务]", "[%]"],
        ["[姓名 D]", "[角色]", "[模块 / 任务]", "[%]"],
    ]
    col_w = [Inches(2.0), Inches(2.5), Inches(6.13), Inches(1.5)]
    x0, y0 = Inches(0.6), Inches(2.95)
    row_h_head = Inches(0.55); row_h = Inches(0.75)

    # header row
    x = x0
    for ci, h in enumerate(headers):
        add_rect(s, x, y0, col_w[ci], row_h_head,
                 fill=INK, border=None)
        add_text(s, x+Inches(0.22), y0+Inches(0.15), col_w[ci]-Inches(0.3), Inches(0.4),
                 h, size=12, bold=True, color=BG)
        x += col_w[ci]

    # body rows
    for ri, row in enumerate(rows):
        y = y0 + row_h_head + ri*row_h
        x = x0
        fill = PANEL if ri % 2 == 0 else PANEL2
        for ci, val in enumerate(row):
            add_rect(s, x, y, col_w[ci], row_h, fill=fill, border=LINE, border_w=0.4)
            add_text(s, x+Inches(0.22), y+Inches(0.22), col_w[ci]-Inches(0.3), Inches(0.4),
                     val, size=12, color=SUB)
            x += col_w[ci]

    add_text(s, Inches(0.6), Inches(6.5), Inches(12), Inches(0.4),
             "占位  ·  成员名单与分工由小组核对后填入。",
             size=10, color=MUTE)

    # closing quote
    add_rule(s, Inches(0.6), Inches(7.0), Inches(12.13), color=LINE)
    add_text(s, Inches(0.6), Inches(7.1), Inches(12), Inches(0.4),
             "“AI 是工具，不是答案。这套东西是查出来的、设计出来的、写出来的。”",
             size=12, bold=True, color=ACCENT, italic=True, align=PP_ALIGN.CENTER)


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
