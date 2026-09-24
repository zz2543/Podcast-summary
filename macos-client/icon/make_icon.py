#!/usr/bin/env python3
"""
生成 Podsum 的 app 图标 → Podsum/Assets.xcassets/AppIcon.appiconset。

图形沿用 ~/Applications/Podsum.app 启动器那枚（白色玻璃方圆 + 声波 + 文字行），
两个入口长得一样。区别只在留白：这里按 macOS 图标网格把方圆缩到 824/1024、
四周留边并加投影，否则 Dock 和启动台里它会比别的图标大一圈。

需要 Pillow。改完图形后重跑：  python3 icon/make_icon.py
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter


def squircle_points(size, n=5.0, steps=1440, inset=0.0):
    a = size / 2.0
    r = a - inset
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        ct, st = math.cos(t), math.sin(t)
        pts.append((a + r * math.copysign(abs(ct) ** (2.0 / n), ct),
                    a + r * math.copysign(abs(st) ** (2.0 / n), st)))
    return pts


def vgrad(S, stops):
    """stops: [(t, (r,g,b)), ...] with t in 0..1, ascending."""
    col = Image.new("RGB", (1, S))
    px = col.load()
    for y in range(S):
        t = y / (S - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t <= t1 or i == len(stops) - 2:
                u = 0.0 if t1 == t0 else min(max((t - t0) / (t1 - t0), 0.0), 1.0)
                px[0, y] = tuple(int(a + (b - a) * u) for a, b in zip(c0, c1))
                break
    return col.resize((S, S))


def vramp(S, y0, y1, v0, v1):
    """Vertical alpha ramp as an L image (y in fractions of S)."""
    col = Image.new("L", (1, S))
    px = col.load()
    for y in range(S):
        t = (y - y0 * S) / max(1e-6, (y1 - y0) * S)
        t = min(max(t, 0.0), 1.0)
        px[0, y] = int(v0 + (v1 - v0) * t)
    return col.resize((S, S))


def render(px, simple=False, ss=4):
    S = px * ss
    empty = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(squircle_points(S), fill=255)

    # --- glass body: white at the top, cooling into a pale grey at the base ---
    body = vgrad(S, [(0.00, (255, 255, 255)),
                     (0.46, (248, 249, 252)),
                     (0.78, (233, 235, 243)),
                     (1.00, (217, 220, 232))])

    # specular bloom across the upper third
    bloom = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bloom).ellipse([-S * 0.28, -S * 0.70, S * 1.28, S * 0.44], fill=255)
    bloom = bloom.filter(ImageFilter.GaussianBlur(S * 0.11)).point(lambda v: int(v * 0.85))
    body = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), body, bloom)

    # diagonal sheen band — the giveaway that this is glass, not paper
    sheen = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sheen).polygon(
        [(-S * 0.10, S * 0.92), (S * 0.46, -S * 0.08),
         (S * 0.74, -S * 0.08), (S * 0.18, S * 0.92)], fill=165)
    sheen = sheen.filter(ImageFilter.GaussianBlur(S * 0.055))
    body = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), body, sheen)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(body, (0, 0), mask)

    # --- glyph: black waveform + text lines ---
    fg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(fg)
    cy = S * 0.5
    INK = (12, 12, 16, 255)
    SOFT = (12, 12, 16, 105)

    if simple:   # 16/32/64px: fewer, chunkier elements so it survives the downscale
        bar_w, bar_gap = S * 0.070, S * 0.048
        heights = [0.21, 0.44, 0.29]
        x0 = S * 0.215
        line_h, line_gap = S * 0.070, S * 0.055
        lengths = [0.195, 0.135]
        mid_gap = S * 0.075
    else:        # 128px and up: full detail
        bar_w, bar_gap = S * 0.045, S * 0.030
        heights = [0.155, 0.30, 0.455, 0.255, 0.125]
        x0 = S * 0.19
        line_h, line_gap = S * 0.045, S * 0.038
        lengths = [0.215, 0.170, 0.115]
        mid_gap = S * 0.058

    x = x0
    for h in heights:
        hh = S * h / 2
        d.rounded_rectangle([x, cy - hh, x + bar_w, cy + hh], radius=bar_w / 2, fill=INK)
        x += bar_w + bar_gap
    x -= bar_gap

    lx = x + mid_gap
    total = len(lengths) * line_h + (len(lengths) - 1) * line_gap
    ly = cy - total / 2
    for i, L in enumerate(lengths):
        d.rounded_rectangle([lx, ly, lx + S * L, ly + line_h], radius=line_h / 2,
                            fill=INK if i < len(lengths) - 1 else SOFT)
        ly += line_h + line_gap

    # soft contact shadow so the glyph sits under the glass, not printed on it
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((40, 42, 60, 70), (0, 0), fg.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.016))
    shadow = shadow.transform(shadow.size, Image.AFFINE, (1, 0, 0, 0, 1, -S * 0.010))

    comp = Image.alpha_composite(img, Image.composite(shadow, empty, mask))
    comp = Image.alpha_composite(comp, Image.composite(fg, empty, mask))

    # --- rim: bright bevel along the top, a grey lip along the bottom ---
    ring = Image.composite(mask.filter(ImageFilter.GaussianBlur(S * 0.022))
                           .point(lambda v: 255 - v), Image.new("L", (S, S), 0), mask)
    top_rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    top_rim.paste((255, 255, 255, 255), (0, 0),
                  Image.composite(ring, Image.new("L", (S, S), 0),
                                  vramp(S, 0.00, 0.34, 255, 0)))
    bot_rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bot_rim.paste((150, 153, 170, 150), (0, 0),
                  Image.composite(ring, Image.new("L", (S, S), 0),
                                  vramp(S, 0.42, 1.00, 0, 255)))
    comp = Image.alpha_composite(comp, bot_rim)
    comp = Image.alpha_composite(comp, top_rim)

    # hairline edge so the white body still reads on a white background
    edge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(edge).polygon(squircle_points(S, inset=S * 0.004),
                                 outline=(120, 124, 145, 90),
                                 width=max(1, int(S * 0.005)))
    comp = Image.alpha_composite(comp, Image.composite(edge, empty, mask))
    return comp.resize((px, px), Image.LANCZOS)




# macOS 图标网格：1024 画布里主体 824，居中，下方带一点投影
BODY = 824 / 1024
SHADOW_BLUR = 10 / 1024
SHADOW_DY = 10 / 1024


def framed(px):
    ss = 4
    S = px * ss
    body_px = round(S * BODY)
    body = render(body_px // ss, simple=(px <= 64)).resize((body_px, body_px), Image.LANCZOS)
    off = (S - body_px) // 2

    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 90), (off, off + round(S * SHADOW_DY)), body.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * SHADOW_BLUR))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(body, (off, off))
    return canvas.resize((px, px), Image.LANCZOS)


if __name__ == "__main__":
    import json
    from pathlib import Path

    out = Path(__file__).resolve().parent.parent / "Podsum/Assets.xcassets"
    iconset = out / "AppIcon.appiconset"
    iconset.mkdir(parents=True, exist_ok=True)
    (out / "Contents.json").write_text(
        json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n")

    images = []
    for pt in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = pt * scale
            name = f"icon_{pt}x{pt}{'@2x' if scale == 2 else ''}.png"
            framed(px).save(iconset / name)
            images.append({"filename": name, "idiom": "mac",
                           "scale": f"{scale}x", "size": f"{pt}x{pt}"})
    (iconset / "Contents.json").write_text(json.dumps(
        {"images": images, "info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    print(f"✓ {iconset}  {len(images)} 张")
