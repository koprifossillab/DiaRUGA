"""생층서 기준면 그림 — 권역 표와 SVG 배치 (P28). **Django 를 안 부른다.**

`atlas.py` 의 `AREA_OF` 와 같은 자리다 — 권역은 자료가 아니라 사람이 정한
것이라 코드에 못 박는다. 질의는 `data.py`(`biodatum_chart`)가 하고 여기는
받은 dict 를 화면 좌표로 놓는다(`core.html` 의 깊이 축과 같은 식 — 서버가
인라인 SVG 로 낸다).

## 권역 — `Site.area` 와 다른 축이다

출처 열다섯은 남극해(12)와 북서태평양·일본(3)으로 갈린다. 북서태평양은 한국
도감 권역(`atlas.AREAS` 의 `korea`)이 아니라 이름을 섞지 않는다. **거르개는
체크박스다** — 태평양 자료를 남극과 한 축에 놓고 볼 때가 있다(사용자,
09-18). 둘 다 끄면 아무것도 안 그린다 — 조용히 전체를 내면 거르개가 죽은
것을 모른다.
"""
from __future__ import annotations

import math

from . import gts, mis

AREAS = (
    ("antarctic", "남극해"),
    ("npacific", "북서태평양·일본"),
)
AREA_LABEL = dict(AREAS)
AREA_OF_REF = {
    "warnock2025": "antarctic", "cody2008": "antarctic", "crampton2016": "antarctic",
    "censarek2002": "antarctic", "censarek704B": "antarctic",
    "zielinski2002b": "antarctic", "winter_iwai2002": "antarctic",
    "gersonde_barcena1998": "antarctic", "zielinski_gersonde2002": "antarctic",
    "kato2024": "antarctic", "winter2012": "antarctic",
    "gersonde1990": "antarctic",    # ODP Leg 113 웨델해 (209)
    # winter_iwai2002 는 위에 있다 — 210 에서 원문 표로 갈아 끼웠다(시추공별 43행)
    "yanagisawa1998": "npacific", "iodp346": "npacific", "fujiwara2008": "npacific",
}
# 대 체계 → 권역. 바탕띠를 그 권역이 켜졌을 때만 낸다
AREA_OF_SCHEME = {
    "warnock2025": "antarctic", "censarek-ssodz": "antarctic",
    "censarek-nsodz": "antarctic", "gersonde1990": "antarctic",
    "winter2002": "antarctic",      # ODP Leg 178 남극반도 (210)
    "npd": "npacific",
}
SCHEME_LABEL = {
    "warnock2025": "Winter 2012 / Warnock 2025",
    "censarek-ssodz": "SSODZ (Censarek 2002)",
    "censarek-nsodz": "NSODZ (Censarek 2002)",
    "gersonde1990": "Gersonde & Burckle 1990",
    "winter2002": "Winter & Iwai 2002",
    "npd": "NPD (Yanagisawa & Akiba 1998)",
}
# 출처 → 도감 키. 같은 논문의 도판이 도감 표에 있다(207). FK 가 아니다 —
# `Occurrence.source` 가 문자열인 것과 같다
ATLAS_OF_REF = {
    "censarek2002": "2002-censarek-miocene",
    "zielinski2002b": "2002-zielinski-rouxia",
    "gersonde1990": "1990-gersonde-weddell",
}
# Cody (2008) 두 모델 중 기본은 평균 — Warnock Table 2 가 그것을 인용한다
MODELS = (("average", "평균범위"), ("total", "전범위"), ("both", "둘 다"))


def area_of_ref(key: str) -> str:
    """모르면 빈 문자열 — 새 출처가 조용히 어느 권역에 앉으면 안 된다."""
    return AREA_OF_REF.get(key or "", "")


def area_keys(areas) -> set[str]:
    want = set(areas)
    return {k for k, a in AREA_OF_REF.items() if a in want}


# ── SVG 배치 ─────────────────────────────────────────────────────
#
# 세로 시간축 — **아래가 오래된 쪽**(층서 관례). 종마다 한 열. 폭은 종 수에
# 따라 늘어나고 화면이 가로로 굴린다(뷰박스를 화면에 맞춰 찌그러뜨리지 않는다).
#
# 왼쪽 축은 숫자(Ma)만이 아니다(209) — 국제 층서 연대표의 기·세·절
# (`gts.py`)과 LR04 MIS 단계(`mis.py`)가 기둥으로 나란히 선다. 숫자 하나로는
# "이 기준면이 어느 절에 드는가" 를 사람이 매번 환산해야 했다.

TOP = 70          # 위 여백 (연령 축 머리 · 대 체계 이름이 비스듬히 선다)
BOTTOM = 16
HEIGHT = 640      # 축 길이(px) — 5 Ma 까지. 그보다 길면 `axis_height` 가 늘린다
HEIGHT_MAX = 1040
COL = 26          # 종 한 열의 폭
AXIS_W = 44       # 왼쪽 연령 축(숫자)
GTS_W = {"period": 14, "epoch": 18, "stage": 28}   # 기·세·절 기둥
MIS_W = 24        # MIS 기둥 — 절 오른쪽
ZONE_W = 26       # 대 띠 한 체계의 폭
LABEL_H = 175     # 아래 종 이름 자리(회전 글자)
LABEL_DEG = 60    # 종 이름 기울기 — 템플릿의 rotate() 와 같은 값이어야 한다
LEFT_W = AXIS_W + sum(GTS_W.values()) + MIS_W + 6   # 대 띠가 시작하는 x
# 오른쪽 여백 — 마지막 열의 이름이 기울어 오른쪽으로 뻗는 만큼(210). 이름
# 길이는 LABEL_H / sin(60°) 까지이고 그것의 cos(60°) 만큼이 열 밖으로 나간다.
# 이것이 없으면 뷰박스가 열에서 끝나 **가장 오른쪽 종의 이름이 잘린다**
RIGHT_PAD = int(LABEL_H / math.tan(math.radians(LABEL_DEG))) + 10


def axis_height(span: float) -> int:
    """축 길이 — 5 Ma 폭까지는 640px, 20 Ma 에서 1040px. 절(stage)이 짧은
    쪽(젤라절 0.78 Ma)이 긴 축에서 글자 하나 못 넣는 띠가 되는 것을 막는다.
    `span` 은 축의 폭(y_max − y_min)이다 — 좁혀 보면 그만큼 늘어난다(210)."""
    if span <= 5:
        return HEIGHT
    return int(HEIGHT + (HEIGHT_MAX - HEIGHT) * min(1.0, (span - 5) / 15))


def nice_max(v: float) -> float:
    """축 끝 — 자료 최대의 조금 위를 보기 좋은 값으로."""
    if v <= 0:
        return 1.0
    for step in (0.5, 1, 2, 5, 10, 20, 30, 50):
        if v <= step * 0.96:
            return float(step)
    return float(int(v) + 1)


def axis_ticks(y_max: float, y_min: float = 0.0) -> list[float]:
    """눈금 — 간격은 축의 **폭**이 정한다. 좁힌 창(0.4–0.8 Ma)은 0.05 간격."""
    span = y_max - y_min
    step = 0.05 if span <= 0.5 else 0.1 if span <= 1 else 0.25 if span <= 2 \
        else 0.5 if span <= 5 else 1 if span <= 10 else 2 if span <= 20 else 5
    out, k = [], int(y_min / step - 1e-9)
    while True:
        v = round(k * step, 4)
        if v > y_max + 1e-9:
            break
        if v >= y_min - 1e-9:
            out.append(v)
        k += 1
    return out


def parse_bound(text: str):
    """범위 칸 하나 — `1.2`(Ma) 또는 `MIS 5`·`G2`(단계 이름). 단계면 (상한, 하한)
    을, 숫자면 (v, v) 를, 못 읽으면 None 을 낸다. 부르는 쪽이 "부터" 칸은
    상한을, "까지" 칸은 하한을 집는다(MIS 5 부터 MIS 11 까지 = 0.071–0.424)."""
    t = (text or "").strip()
    if not t:
        return None
    try:
        v = float(t)
        return (v, v) if v >= 0 else None
    except ValueError:
        return mis.stage_span(t)


def window(from_text: str, to_text: str) -> tuple[float | None, float | None]:
    """`?from=`·`?to=` → (y_min, y_max). 못 읽는 쪽은 None(= 자료가 정한다).
    뒤집혀 있으면 바로 세운다 — 사람이 칸을 바꿔 넣은 것이지 빈 창을 원한
    것이 아니다."""
    a, b = parse_bound(from_text), parse_bound(to_text)
    lo = a[0] if a else None
    hi = b[1] if b else None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = (b[0] if b else hi), (a[1] if a else lo)
    if lo is not None and hi is not None and hi - lo < 0.01:
        hi = lo + 0.01
    return lo, hi


def layout(species: list[dict], zones: list[dict], y_max: float | None = None,
           y_min: float = 0.0) -> dict:
    """종 열과 대 띠를 좌표로.

    `species[i]` = {name, binomial, genus, in_atlas, points: [{datum, age,
    age_min, age_max, ref, via, variant, confidence, primary, ...}]} —
    `data.biodatum_chart` 가 만든 것. 여기서는 값을 안 고른다(무엇을 그릴지는
    질의가 정했다), 자리만 잡는다.

    **창(`y_min`–`y_max`)이 있으면 그 밖은 안 그린다**(210). 점은 연령 폭이
    창에 걸치는 것만, 막대는 점 전부로 재고 창에서 자른다(창 밖의 FO 까지
    이어진 막대가 열린 채로 보여야 "이 종은 더 내려간다" 를 안다). 점도 막대도
    창에 안 걸치는 종은 열을 안 만든다 — 표도 그 열을 따라간다.
    """
    ages = [p["age_max"] for s in species for p in s["points"]]
    y_max = y_max or nice_max(max(ages) if ages else 0)
    y_min = max(0.0, min(y_min or 0.0, y_max - 0.01))
    span = y_max - y_min
    height = axis_height(span)
    scale = height / span

    def y(ma: float) -> float:
        return round(TOP + (min(max(ma, y_min), y_max) - y_min) * scale, 1)

    def hits(lo: float, hi: float) -> bool:
        return lo <= y_max and hi >= y_min

    schemes: list[str] = []
    for z in zones:
        if z["scheme"] not in schemes:
            schemes.append(z["scheme"])
    x0 = LEFT_W + ZONE_W * len(schemes) + 8

    cols = []
    for s in species:
        fo = [p for p in s["points"] if p["datum"] == "FO"]
        lo = [p for p in s["points"] if p["datum"] == "LO"]
        # 막대: 가장 젊은 LO 에서 가장 오래된 FO 까지 — 문헌이 본 범위의 합
        top_ma = min((p["age_min"] for p in lo), default=None)
        base_ma = max((p["age_max"] for p in fo), default=None)
        bar = None
        if top_ma is not None or base_ma is not None:
            t = top_ma if top_ma is not None else min(p["age_min"] for p in s["points"])
            b = base_ma if base_ma is not None else max(p["age_max"] for p in s["points"])
            if hits(t, b):
                bar = {"y1": y(t), "y2": y(b), "h": max(1.0, round(y(b) - y(t), 1)),
                       # 한쪽만 있거나 창에서 잘렸으면 열린 범위다 — 화면이 점선으로 낸다
                       "open_top": top_ma is None or t < y_min,
                       "open_base": base_ma is None or b > y_max}
        pts = [dict(p, cy=y(p["age"]), y1=y(p["age_min"]), y2=y(p["age_max"]))
               for p in s["points"] if hits(p["age_min"], p["age_max"])]
        if not pts and bar is None:
            continue
        x = x0 + COL * len(cols) + COL / 2
        # 열 아래 이름은 속을 머리글자로 줄인다 — 한 그림이 대개 한 속이고
        # 긴 이름(`Denticulopsis praedimorpha var. minor`)이 자리를 넘는다.
        # 전체 이름은 표와 마우스 설명에 있다
        cols.append(dict(s, x=round(x, 1), bar=bar, points=pts, label=_short_name(s["name"])))
    x_end = x0 + COL * max(len(cols), 1)
    width = x_end + RIGHT_PAD

    bands = []
    for si, sc in enumerate(schemes):
        zs = [z for z in zones if z["scheme"] == sc]
        # 하한만 있는 체계(Censarek·NPD)는 위 대의 하한이 상한이다
        zs = sorted(zs, key=lambda z: (z["base_ma"] if z["base_ma"] is not None else 1e9))
        prev_base = 0.0
        for k, z in enumerate(zs):
            top = z["top_ma"] if z["top_ma"] is not None else prev_base
            base = z["base_ma"] if z["base_ma"] is not None else y_max
            if top >= y_max:
                break
            if base > y_min:
                bands.append({
                    "scheme": sc, "x": LEFT_W + ZONE_W * si, "w": ZONE_W,
                    "y1": y(top), "y2": y(base), "h": max(1.0, round(y(base) - y(top), 1)),
                    "top_ma": round(max(top, y_min), 4), "base_ma": round(min(base, y_max), 4),
                    "name": z["name"],
                    "short": _short_zone(z["name"]), "shade": k % 2,
                    "base_def": z["base_def"], "top_def": z["top_def"],
                    "open_top": z["top_ma"] is None and k == 0,
                })
            prev_base = base

    ticks = [{"ma": t, "y": y(t)} for t in axis_ticks(y_max, y_min)]

    # 기·세·절 기둥 — ICS 표(`gts.py`). 글자는 띠에 들어갈 때만, 약자로도 안
    # 들면 비운다(마우스 설명에는 늘 있다). 띠는 누르면 그 범위로 좁힌다 —
    # `top_ma`·`base_ma` 는 창에서 자르지 않은 원래 경계다(그것이 링크의 값)
    gx, gts_cols, gts_bands = AXIS_W, [], []
    for col, label, _rows in gts.COLUMNS:
        gts_cols.append({"key": col, "label": label, "x": gx, "w": GTS_W[col]})
        gx += GTS_W[col]
    col_x = {c["key"]: c["x"] for c in gts_cols}
    for b in gts.bands(y_max):
        if b["base_ma"] <= y_min:
            continue
        y1, y2 = y(b["top_ma"]), y(b["base_ma"])
        gts_bands.append(dict(b, x=col_x[b["col"]], w=GTS_W[b["col"]], y1=y1, y2=y2,
                              h=max(1.0, round(y2 - y1, 1)),
                              label=gts.label_for(b["name"], y2 - y1)))
    # MIS 기둥 — 절 오른쪽. 빙기(짝수)를 칠하고, 번호는 띠에 글자가 들 때만
    # (7px · 긴 축에서는 긴 단계 몇만 남는다), 종결면은 축 폭이 2.5 Ma 이하일 때만.
    # **값이 아니라 눈금이다**(`mis.py` 머리말) — LR04 끝(5.3 Ma)을 넘는 축은
    # 거기까지만 칠한다
    mis_x = gx
    mis_bands = []
    for b in mis.stage_bands(y_max):
        if b["base_ma"] <= y_min:
            continue
        y1, y2 = y(b["top_ma"]), y(b["base_ma"])
        mis_bands.append(dict(b, y1=y1, y2=y2, h=max(0.5, round(y2 - y1, 1)),
                              label=b["name"] if y2 - y1 >= 7 else ""))
    # 경계 눈금(선)은 폭 1.5 Ma 이하에서만 — 그보다 길면 띠의 칠로 충분하다
    mis_ticks = [dict(t, y=y(t["ma"])) for t in mis.stage_ticks(y_max)
                 if t["ma"] >= y_min] if span <= 1.5 else []
    terms = [{"name": n, "ma": ka / 1000.0, "y": y(ka / 1000.0)}
             for n, ka in mis.TERMINATIONS_KA
             if y_min <= ka / 1000.0 <= y_max] if span <= 2.5 else []
    return {
        "width": int(width), "height": int(TOP + height + BOTTOM + LABEL_H),
        "axis_bottom": y(y_max), "top": TOP, "y_max": y_max, "y_min": y_min,
        "axis_h": height, "label_deg": LABEL_DEG,
        "x0": x0, "col": COL, "x_right": int(x_end) + 4,
        "ticks": ticks,
        "gts_cols": gts_cols, "gts_bands": gts_bands,
        "mis_x": mis_x, "mis_w": MIS_W, "mis_bands": mis_bands,
        "mis_ticks": mis_ticks, "terminations": terms,
        "schemes": [{"key": s, "label": SCHEME_LABEL.get(s, s),
                     "x": LEFT_W + ZONE_W * i} for i, s in enumerate(schemes)],
        "bands": bands, "cols": cols,
        "n_species": len(cols), "n_points": sum(len(c["points"]) for c in cols),
    }


def _short_name(name: str) -> str:
    w = name.split()
    if len(w) >= 2 and w[0][:1].isupper() and w[0].isalpha() and len(w[0]) > 3:
        return f"{w[0][0]}. {' '.join(w[1:])}"
    return name


def _short_zone(name: str) -> str:
    """띠 안에 들어갈 짧은 이름 — `Thalassiosira lentiginosa Partial Range Zone`
    → `T. lentiginosa`. NPD 코드는 그대로."""
    w = name.replace(" Partial Range Zone", "").replace(" Concurrent Range Zone", "") \
        .replace(" Zone", "").split()
    if len(w) >= 2 and w[0][0].isupper() and w[0].isalpha() and len(w[0]) > 3:
        return f"{w[0][0]}. {' '.join(w[1:])}"
    return name
