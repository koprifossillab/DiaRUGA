r"""잠금 화면의 로고 GIF 를 굽는다 — 원본 PNG 를 애니메이션 마스크로 드러낸다.

    python tools/gate_logo.py                # web/viewer/assets/gate/ 에 셋을 쓴다
    python tools/gate_logo.py --sheet /tmp/s.png   # 장면 12장을 한 장에 모아 본다

나오는 것 (`viewer/gate.py` 가 읽는다):
    logo.gif    그려지는 장면. **한 번만 돈다** (loop 확장을 안 쓴다)
    logo.png    원본 PNG 사본 (docs/assets/logo/diaruga_logo_centric_bold.png) — 바이트 그대로
    logo.json   {"build_ms": …} — GIF 가 끝 장면에 닿는 시각. 화면이 이때 PNG 로 바꾼다

## 왜 SVG 를 움직이지 않고 PNG 를 드러내는가

GIF 가 끝나면 화면이 **원본 PNG 로 바꾼다.** 두 그림이 한 픽셀이라도 다르면
바꾸는 순간 로고가 튄다. SVG 를 이 서버에서 그리면 워드마크 글꼴(Montserrat)이
없어 다른 글꼴로 나오고, 사용자가 받아 온 GIF(2026-09-23, `N:\DiaRUGA\Diadiction\temp\`)도
끝 장면이 원본 PNG 와 글꼴·모양이 달랐다. 그래서 색은 전부 원본 PNG 에서 가져오고,
SVG 의 좌표는 **어디를 언제 드러낼지**(마스크)에만 쓴다. 끝 장면은 원본 그 자체다.

겹치는 자리의 주인은 글자 > 선 > 바탕 순이다. 바탕 도형을 드러낼 때 그 위의
글자·밑줄 자리는 바탕만 있는 그림(`back_img`)으로 채우고, 글자는 원본에서 푼
불투명도(`split_text`)로 얹는다 — 안 그러면 글자가 나오기 전에 글자 모양 구멍이
비치고, 올라오는 글자가 둘레의 어두운 테를 끌고 다닌다.

바탕색은 잠금 화면 바탕과 같아야 한다 (`templates/viewer/gate.html` 의 `--bg`).
GIF 는 반투명을 못 담아 이 색 위에 미리 얹어 굽는다.
"""
import argparse
import json
import math
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

U = 2          # 출력 해상도: SVG 1 단위 = 2 px (680×280 → 1360×560)
SS = 2         # 마스크를 이만큼 크게 그려 줄인다 (가장자리 부드럽게)
W, H = 680 * U, 280 * U
FPS = 25


# ── 시간 곡선 ────────────────────────────────────────────────────────────
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def phase(t, t0, t1):
    return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t1)


def ease_out(x):          # cubic
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back_out(x, s=1.6):   # 살짝 넘쳤다 돌아온다
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


# ── 기하 → 마스크 ────────────────────────────────────────────────────────
class Canvas:
    """SVG 좌표로 흰 선을 그리는 마스크 한 장 (크게 그려 줄인다)."""

    def __init__(self):
        self.k = U * SS
        self.im = Image.new("L", (W * SS, H * SS), 0)
        self.d = ImageDraw.Draw(self.im)

    def P(self, x, y):
        return (x * self.k, y * self.k)

    def polyline(self, pts, width):
        if len(pts) < 2:
            return
        w = max(1, int(round(width * self.k)))
        self.d.line([self.P(*p) for p in pts], fill=255, width=w, joint="curve")
        r = w / 2  # 둥근 끝
        for p in (pts[0], pts[-1]):
            x, y = self.P(*p)
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=255)

    def polygon(self, pts):
        self.d.polygon([self.P(*p) for p in pts], fill=255)

    def disc(self, cx, cy, r):
        x, y = self.P(cx, cy)
        r *= self.k
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=255)

    def result(self, blur=0.0):
        m = self.im.resize((W, H), Image.LANCZOS)
        if blur:
            m = m.filter(ImageFilter.GaussianBlur(blur))
        return np.asarray(m, dtype=np.float32) / 255.0


def affine(tx, ty, rot_deg=0.0, sc=1.0):
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    return lambda x, y: (tx + sc * (c * x - s * y), ty + sc * (s * x + c * y))


def partial(pts, f):
    """점열의 앞 f(0~1) 만큼 (호 길이 기준)."""
    if f <= 0:
        return []
    if f >= 1:
        return pts
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    goal = sum(seg) * f
    out = [pts[0]]
    for i, L in enumerate(seg):
        if goal <= L:
            a = goal / L if L else 0
            out.append((pts[i][0] + a * (pts[i + 1][0] - pts[i][0]),
                        pts[i][1] + a * (pts[i + 1][1] - pts[i][1])))
            return out
        goal -= L
        out.append(pts[i + 1])
    return out


def circle_pts(cx, cy, r, start_deg=-90, n=240):
    return [(cx + r * math.cos(math.radians(start_deg + 360 * i / n)),
             cy + r * math.sin(math.radians(start_deg + 360 * i / n))) for i in range(n + 1)]


def ellipse_pts(tf, rx, ry, start_deg=180, n=360):
    return [tf(rx * math.cos(math.radians(start_deg + 360 * i / n)),
               ry * math.sin(math.radians(start_deg + 360 * i / n))) for i in range(n + 1)]


def quad_pts(p0, p1, p2, n=120):
    return [((1 - s) ** 2 * p0[0] + 2 * (1 - s) * s * p1[0] + s * s * p2[0],
             (1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * p2[1])
            for s in (i / n for i in range(n + 1))]


# ── 합성 ────────────────────────────────────────────────────────────────
def load_png(path, bg):
    im = Image.open(path).convert("RGBA").resize((W, H), Image.LANCZOS)
    base = Image.new("RGBA", (W, H), bg + (255,))
    return np.asarray(Image.alpha_composite(base, im).convert("RGB"), dtype=np.float32)


def letters_from(mask, min_gap=2):
    """글자 마스크를 세로 빈 줄로 갈라 글자마다 (x0, x1) 을 낸다."""
    cols = mask.max(axis=0) > 0.05
    spans, x = [], 0
    while x < len(cols):
        if cols[x]:
            x0 = x
            while x < len(cols) and cols[x]:
                x += 1
            spans.append([x0, x])
        x += 1
    merged = []
    for s in spans:   # 너무 좁은 틈은 한 글자 (i 의 점 같은 것은 세로라 여기 안 걸린다)
        if merged and s[0] - merged[-1][1] <= min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


def shift_y(a, dy):
    """배열을 dy px 아래로 (위로는 음수). 빈 자리는 0."""
    dy = int(round(dy))
    if dy == 0:
        return a
    out = np.zeros_like(a)
    if dy > 0:
        out[dy:] = a[:-dy]
    else:
        out[:dy] = a[-dy:]
    return out


def split_text(png, tm, under, color):
    """원본 = 밑그림 × (1-α) + 글자색 × α 로 보고 글자 상자 안의 α 를 푼다.

    밑그림(`under`)은 글자를 걷어 낸 그림이다. 글자가 아직 안 나온 장면에서
    바탕 도형에 글자 모양 구멍이 비치지 않게, 올라오는 글자가 둘레의 어두운
    테를 끌고 다니지 않게 하려고 가른다.
    """
    tc = np.array(color, dtype=np.float32)
    den = (tc - under).sum(axis=2)
    num = (png - under).sum(axis=2)
    a = np.where(np.abs(den) > 30, num / np.where(den == 0, 1, den), 0)
    return np.clip(a, 0, 1).astype(np.float32) * (tm > 0)


def lerp(out, img, a):
    return out * (1 - a[..., None]) + img * a[..., None]


def render(scene, png, bg, t):
    bgv = np.array(bg, dtype=np.float32)
    under, ta, tc = scene["under"], scene["text_alpha"], np.array(scene["color"], np.float32)
    fg, back = scene["layers"](t)
    out = np.broadcast_to(bgv, png.shape).copy()
    # 바탕 도형 → 선. 선 자리는 선이 그려질 때 드러난다 (바탕이 먼저 비추지 않게)
    out = lerp(out, scene["back_img"], back)
    out = lerp(out, under, fg)
    for (x0, x1), (a, dy) in zip(scene["letters"], scene["letter_state"](t)):
        if a <= 0:
            continue
        m = np.zeros_like(ta)
        m[:, x0:x1] = ta[:, x0:x1]
        ms = shift_y(m, dy) * a
        out = lerp(out, tc, ms)
    # 끝에서 원본으로 모은다 — 글자 α 를 푼 오차·마스크가 못 덮은 가장자리가 여기서 닫힌다
    rest = scene["rest"](t)
    if rest > 0:
        out = lerp(out, png, np.full(ta.shape, rest, np.float32))
    tm = ta

    shine = scene.get("shine")
    if shine:
        band = shine(t)
        if band is not None:
            b = (band * tm)[..., None]
            out = out + (255 - out) * b
    return np.clip(out, 0, 255).astype(np.uint8)


def write_gif(frames, hold_ms, path, final_rgb):
    """전체 공용 팔레트 하나로 — 프레임마다 팔레트가 바뀌면 깜빡인다.

    팔레트는 마지막 프레임(= 원본)과 중간 프레임 몇 장을 이어 붙여 뽑는다.
    """
    sample = [final_rgb] + frames[:: max(1, len(frames) // 6)]
    strip = Image.fromarray(np.concatenate(sample, axis=0))
    pal = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    ims = [Image.fromarray(f).quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    delay = int(1000 / FPS)
    durs = [delay] * (len(ims) - 1) + [hold_ms]
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=durs,
                optimize=False, disposal=1)   # loop 를 안 준다 = 한 번만 돈다
    return sum(durs)


# ── 장면: DiaRUGA ───────────────────────────────────────────────────────
def scene_diaruga(png, png_alpha):
    C = (150, 90)
    ring_o = circle_pts(*C, 58, start_deg=-90)
    ring_i = circle_pts(*C, 44, start_deg=-90)
    spokes = []
    for (x1, y1, x2, y2) in [(0, -58, 0, -44), (41, -41, 31, -31), (58, 0, 44, 0), (41, 41, 31, 31),
                             (0, 58, 0, 44), (-41, 41, -31, 31), (-58, 0, -44, 0), (-41, -41, -31, -31),
                             (20, -54, 15, -42), (54, -20, 42, -15), (54, 20, 42, 15), (20, 54, 15, 42),
                             (-20, 54, -15, 42), (-54, 20, -42, 15), (-54, -20, -42, -15), (-20, -54, -15, -42)]:
        ang = (math.degrees(math.atan2(y1, x1)) + 90) % 360   # 12시에서 시계 방향
        spokes.append((ang, (C[0] + x1, C[1] + y1), (C[0] + x2, C[1] + y2)))
    spokes.sort()

    tf = affine(370, 185, -10)
    pen_ell = ellipse_pts(tf, 250, 15, start_deg=180)
    pen_lines = [[tf(-245, 0), tf(245, 0)], [tf(-220, -7), tf(220, -7)], [tf(-220, 7), tf(220, 7)]]
    pen_lines = [[p[0], p[1]] for p in pen_lines]
    uline = quad_pts((150, 185), (340, 212), (530, 185))
    SW = 3 + 3.2    # 원본 선 굵기 3 + 가장자리 여유

    cvp = Canvas()
    cvp.polyline(pen_ell, SW)
    for ln in pen_lines:
        cvp.polyline(ln, SW)
    pen_full = cvp.result()
    rot = math.radians(10)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) / U
    pen_coord = (xx - 370) * math.cos(rot) - (yy - 185) * math.sin(rot)
    cvf = Canvas()
    cvf.polyline(ring_o, SW); cvf.polyline(ring_i, SW); cvf.polyline(uline, SW)
    for _, p1, p2 in spokes:
        cvf.polyline([p1, p2], SW)
    fg_full = cvf.result()

    # 글자: 글자 상자 안에서 원본 알파가 짙은 곳 (펜네이트 0.28·밑줄 0.6 보다 짙다)
    tm = np.zeros((H, W), np.float32)
    y0, y1, x0, x1 = 92 * U, 162 * U, 185 * U, 495 * U
    tm[y0:y1, x0:x1] = (png_alpha[y0:y1, x0:x1] > 0.7).astype(np.float32)
    tm = np.asarray(Image.fromarray((tm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)),
                    dtype=np.float32) / 255
    letters = letters_from(tm)

    # 밑그림: 글자 자리를 글자 아래 있던 것(펜네이트 0.28 · 고리)으로 채운다
    col = (0x7d, 0xd3, 0xfc)
    thin = Canvas()
    thin.polyline(ring_o, 3)
    cover = thin.result()
    thin = Canvas()
    thin.polyline(pen_ell, 3)
    for ln in pen_lines:
        thin.polyline(ln, 3)
    cover = np.maximum(cover, 0.28 * thin.result())
    bgv, cv_ = np.array(png[0, 0]), np.array(col, np.float32)
    under_img = np.where(tm[..., None] > 0, bgv + (cv_ - bgv) * cover[..., None], png)
    text_alpha = split_text(png, tm, under_img, col)
    # 바탕 도형만 있는 그림: 선·글자 자리에서는 펜네이트만 그려 넣는다 (밑줄이 지나는 자리가 비지 않게)
    pen_only = bgv + (cv_ - bgv) * (0.28 * thin.result())[..., None]
    back_img = np.where(np.maximum(fg_full, tm)[..., None] > 0, pen_only, png)

    def layers(t):
        cv = Canvas()
        # 1) 바깥 고리 → 안 고리가 12시부터 시계 방향으로 그려진다
        cv.polyline(partial(ring_o, ease_in_out(phase(t, 0.05, 0.85))), SW)
        cv.polyline(partial(ring_i, ease_in_out(phase(t, 0.20, 0.95))), SW)
        # 2) 늑(costae)이 고리를 따라 돌며 안쪽으로 뻗는다
        for i, (ang, p1, p2) in enumerate(spokes):
            f = ease_out(phase(t, 0.55 + ang / 360 * 0.45, 0.75 + ang / 360 * 0.45))
            if f > 0:
                cv.polyline([p1, (p1[0] + f * (p2[0] - p1[0]), p1[1] + f * (p2[1] - p1[1]))], SW)
        # 3) 밑줄
        cv.polyline(partial(uline, ease_in_out(phase(t, 1.55, 2.15))), SW)
        # 4) 펜네이트: 긴 축을 따라 왼쪽 끝에서 오른쪽 끝으로 쓸려 드러난다
        p = ease_in_out(phase(t, 0.40, 1.50))
        front = -270 + p * 540
        pen = pen_full * np.clip((front - pen_coord) / 40.0, 0, 1)
        return cv.result(), pen

    def letter_state(t):
        out = []
        for i in range(len(letters)):
            p = phase(t, 0.95 + 0.07 * i, 1.45 + 0.07 * i)
            out.append((ease_out(p), (1 - back_out(p)) * 14 * U))
        return out

    def rest(t):
        return ease_in_out(phase(t, 2.10, 2.40))

    def shine(t):
        p = phase(t, 1.85, 2.45)
        if p <= 0 or p >= 1:
            return None
        xs = np.arange(W, dtype=np.float32)[None, :] + 0.35 * np.arange(H, dtype=np.float32)[:, None]
        c = x0 - 60 * U + p * (x1 - x0 + 120 * U)
        return 0.55 * np.exp(-((xs - c) / (18 * U)) ** 2) * math.sin(math.pi * p)

    return dict(layers=layers, rest=rest, letters=letters, fg_full=fg_full,
                under=under_img, text_alpha=text_alpha, color=col, back_img=back_img,
                letter_state=letter_state, shine=shine, end=2.45)



REPO = Path(__file__).resolve().parent.parent
SRC_PNG = REPO / "docs/assets/logo/diaruga_logo_centric_bold.png"
SRC_SVG = SRC_PNG.with_suffix(".svg")
OUT_DIR = REPO / "web" / "viewer" / "assets" / "gate"
BG = "#0f1115"     # gate.html 의 --bg 와 같아야 한다


def main():
    ap = argparse.ArgumentParser(description="잠금 화면 로고 GIF 를 굽는다")
    ap.add_argument("--sheet", help="장면 12장을 모은 확인용 그림을 여기 쓴다")
    a = ap.parse_args()
    bg = tuple(int(BG.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    png = load_png(SRC_PNG, bg)
    alpha = np.asarray(Image.open(SRC_PNG).convert("RGBA").resize((W, H), Image.LANCZOS),
                       dtype=np.float32)[..., 3] / 255
    sc = scene_diaruga(png, alpha)
    n = int(round(sc["end"] * FPS)) + 1
    frames = [render(sc, png, bg, i / FPS) for i in range(n)]
    final = png.astype(np.uint8)
    diff = np.abs(frames[-1].astype(int) - final.astype(int)).max()
    frames[-1] = final     # 끝 장면은 원본 그 자체다 (위 diff 는 바로 앞까지의 어긋남)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_gif(frames, 1000, OUT_DIR / "logo.gif", final)
    shutil.copyfile(SRC_PNG, OUT_DIR / "logo.png")
    build_ms = (n - 1) * int(1000 / FPS)
    (OUT_DIR / "logo.json").write_text(json.dumps({"build_ms": build_ms, "bg": BG}) + "\n")
    print(json.dumps({"frames": n, "letters": len(sc["letters"]), "build_ms": build_ms,
                      "last_vs_png_maxdiff": int(diff),
                      "gif_bytes": (OUT_DIR / "logo.gif").stat().st_size}))
    if a.sheet:
        pick = [frames[int(i)] for i in np.linspace(0, n - 1, 12)]
        small = [Image.fromarray(f).resize((W // 2, H // 2)) for f in pick]
        sheet = Image.new("RGB", (W // 2 * 3, H // 2 * 4))
        for k, s_ in enumerate(small):
            sheet.paste(s_, ((k % 3) * W // 2, (k // 3) * H // 2))
        sheet.save(a.sheet)


if __name__ == "__main__":
    main()
