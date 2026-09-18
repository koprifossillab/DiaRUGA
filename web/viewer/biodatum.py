"""생층서 기준면 그림 — 권역 표와 SVG 배치 (P28). **Django 를 안 부른다.**

`atlas.py` 의 `AREA_OF` 와 같은 자리다 — 권역은 자료가 아니라 사람이 정한
것이라 코드에 못 박는다. 질의는 `data.py`(`biodatum_chart`)가 하고 여기는
받은 dict 를 화면 좌표로 놓는다(`core.html` 의 깊이 축과 같은 식 — 서버가
인라인 SVG 로 낸다).

## 권역 — `Site.area` 와 다른 축이다

출처 열넷은 남극해(11)와 북서태평양·일본(3)으로 갈린다. 북서태평양은 한국
도감 권역(`atlas.AREAS` 의 `korea`)이 아니라 이름을 섞지 않는다. **거르개는
체크박스다** — 태평양 자료를 남극과 한 축에 놓고 볼 때가 있다(사용자,
09-18). 둘 다 끄면 아무것도 안 그린다 — 조용히 전체를 내면 거르개가 죽은
것을 모른다.
"""
from __future__ import annotations

from . import mis

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
    "yanagisawa1998": "npacific", "iodp346": "npacific", "fujiwara2008": "npacific",
}
# 대 체계 → 권역. 바탕띠를 그 권역이 켜졌을 때만 낸다
AREA_OF_SCHEME = {
    "warnock2025": "antarctic", "censarek-ssodz": "antarctic",
    "censarek-nsodz": "antarctic", "npd": "npacific",
}
SCHEME_LABEL = {
    "warnock2025": "Winter 2012 / Warnock 2025",
    "censarek-ssodz": "SSODZ (Censarek 2002)",
    "censarek-nsodz": "NSODZ (Censarek 2002)",
    "npd": "NPD (Yanagisawa & Akiba 1998)",
}
# 출처 → 도감 키. 같은 논문의 도판이 도감 표에 있다(207). FK 가 아니다 —
# `Occurrence.source` 가 문자열인 것과 같다
ATLAS_OF_REF = {
    "censarek2002": "2002-censarek-miocene",
    "zielinski2002b": "2002-zielinski-rouxia",
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

TOP = 70          # 위 여백 (연령 축 머리 · 대 체계 이름이 비스듬히 선다)
BOTTOM = 16
HEIGHT = 640      # 축 길이(px)
COL = 26          # 종 한 열의 폭
AXIS_W = 44       # 왼쪽 연령 축
ZONE_W = 26       # 대 띠 한 체계의 폭
MIS_W = 30        # 오른쪽 MIS 눈금
LABEL_H = 175     # 아래 종 이름 자리(회전 글자)


def nice_max(v: float) -> float:
    """축 끝 — 자료 최대의 조금 위를 보기 좋은 값으로."""
    if v <= 0:
        return 1.0
    for step in (0.5, 1, 2, 5, 10, 20, 30, 50):
        if v <= step * 0.96:
            return float(step)
    return float(int(v) + 1)


def axis_ticks(y_max: float) -> list[float]:
    step = 0.1 if y_max <= 1 else 0.25 if y_max <= 2 else 0.5 if y_max <= 5 \
        else 1 if y_max <= 10 else 2 if y_max <= 20 else 5
    out, v = [], 0.0
    while v <= y_max + 1e-9:
        out.append(round(v, 4))
        v += step
    return out


def layout(species: list[dict], zones: list[dict], y_max: float | None = None) -> dict:
    """종 열과 대 띠를 좌표로.

    `species[i]` = {name, binomial, genus, in_atlas, points: [{datum, age,
    age_min, age_max, ref, via, variant, confidence, primary, ...}]} —
    `data.biodatum_chart` 가 만든 것. 여기서는 값을 안 고른다(무엇을 그릴지는
    질의가 정했다), 자리만 잡는다.
    """
    ages = [p["age_max"] for s in species for p in s["points"]]
    y_max = y_max or nice_max(max(ages) if ages else 0)
    scale = HEIGHT / y_max

    def y(ma: float) -> float:
        return round(TOP + min(ma, y_max) * scale, 1)

    schemes: list[str] = []
    for z in zones:
        if z["scheme"] not in schemes:
            schemes.append(z["scheme"])
    x0 = AXIS_W + ZONE_W * len(schemes) + 8
    width = x0 + COL * max(len(species), 1) + 8 + MIS_W

    cols = []
    for i, s in enumerate(species):
        x = x0 + COL * i + COL / 2
        pts = []
        fo = [p for p in s["points"] if p["datum"] == "FO"]
        lo = [p for p in s["points"] if p["datum"] == "LO"]
        # 막대: 가장 젊은 LO 에서 가장 오래된 FO 까지 — 문헌이 본 범위의 합
        top_ma = min((p["age_min"] for p in lo), default=None)
        base_ma = max((p["age_max"] for p in fo), default=None)
        bar = None
        if top_ma is not None or base_ma is not None:
            t = top_ma if top_ma is not None else min(p["age_min"] for p in s["points"])
            b = base_ma if base_ma is not None else max(p["age_max"] for p in s["points"])
            bar = {"y1": y(t), "y2": y(b), "h": max(1.0, round(y(b) - y(t), 1)),
                   # 한쪽만 있으면 열린 범위다 — 화면이 점선으로 낸다
                   "open_top": top_ma is None, "open_base": base_ma is None}
        for p in s["points"]:
            pts.append(dict(p, cy=y(p["age"]), y1=y(p["age_min"]), y2=y(p["age_max"])))
        # 열 아래 이름은 속을 머리글자로 줄인다 — 한 그림이 대개 한 속이고
        # 긴 이름(`Denticulopsis praedimorpha var. minor`)이 자리를 넘는다.
        # 전체 이름은 표와 마우스 설명에 있다
        cols.append(dict(s, x=round(x, 1), bar=bar, points=pts, label=_short_name(s["name"])))

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
            bands.append({
                "scheme": sc, "x": AXIS_W + ZONE_W * si, "w": ZONE_W,
                "y1": y(top), "y2": y(base), "h": max(1.0, round(y(base) - y(top), 1)),
                "name": z["name"],
                "short": _short_zone(z["name"]), "shade": k % 2,
                "base_def": z["base_def"], "top_def": z["top_def"],
                "open_top": z["top_ma"] is None and k == 0,
            })
            prev_base = base

    ticks = [{"ma": t, "y": y(t)} for t in axis_ticks(y_max)]
    # MIS 눈금은 축이 1.5 Ma 이하일 때만 — 그보다 길면 글자가 겹친다.
    # **값이 아니라 눈금이다** (`mis.py` 머리말)
    mis_ticks = [dict(t, y=y(t["ma"])) for t in mis.stage_ticks(y_max)] if y_max <= 1.5 else []
    terms = [{"name": n, "ma": ka / 1000.0, "y": y(ka / 1000.0)}
             for n, ka in mis.TERMINATIONS_KA if ka / 1000.0 <= y_max] if y_max <= 1.5 else []
    return {
        "width": int(width), "height": int(TOP + HEIGHT + BOTTOM + LABEL_H),
        "axis_bottom": y(y_max), "top": TOP, "y_max": y_max,
        "x0": x0, "col": COL, "mis_x": width - MIS_W,
        "ticks": ticks, "mis_ticks": mis_ticks, "terminations": terms,
        "schemes": [{"key": s, "label": SCHEME_LABEL.get(s, s),
                     "x": AXIS_W + ZONE_W * i} for i, s in enumerate(schemes)],
        "bands": bands, "cols": cols,
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
