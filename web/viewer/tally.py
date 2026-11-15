"""산출표 — 검토 결과를 종별로 센다 (P34).

**읽기 전용이고 저장하지 않는다.** 종명은 `DiatomObject.species` 에 이미 있고
세는 규칙도 `data._summary_rows` 에 이미 있다(`per_sp`, 202). 산출표를 테이블에
넣으면 두 벌이 되어 **종명 하나를 고치는 순간 어긋난다** — P17 의 파생 항목
(`derived_series`)이 저장하지 않는 것과 같은 이유다.

**이름이 `tally` 인 이유** — 도감 쪽에 이미 `Occurrence`(문헌의 종 × 지역 출현
기록, P20)가 있다. 이것은 검토 결과를 슬라이드·시료별로 센 집계라 다른 것이고,
한 낱말로 섞이면 화면·코드에서 둘이 같은 것으로 읽힌다. 화면 문구는 "산출표"·
"종" 이다.

## 세는 규칙 (사용자 2026-11-13)

- **파편은 세지 않는다.** 종 줄은 **세는 분류**(`ClassDef.counted=True`)의 개체만
  센다. 파편에 붙은 종명도 뺀다. 파편은 열마다 **파편 비율** 하나로만 보인다 —
  식은 비교 화면과 같다(`data.count_column`).
- **비율의 분모는 종명이 붙은 개체**다(`n_identified`) — 논문의 관례로 센 개체는
  전부 동정한 것이다. 세는 개체 전체를 분모로 하면 동정률이 낮은 지금은 모든
  종이 0 근처로 눌린다. 그래서 **동정률을 늘 함께 낸다** — 종명이 2%인 열을
  100%의 그림처럼 내면 안 된다.
- **이름은 적힌 그대로 묶는다.** 이명을 합치지 않는다(논문 이름은 그 시대의
  이름이다). 한 종명이 분류 둘에 걸쳐 있으면(`Eucampia` 와 미분류처럼) 종 줄
  하나로 더한다 — 분류는 형태로 고른 것이고 종명이 더 아래 층이다.
"""

import math
from collections import Counter

from . import data


def column(summary: dict) -> dict:
    """슬라이드 하나의 집계(`data._slide_summary`)를 산출표 열 하나로 접는다.

    `per_species` 는 종명 → 수(세는 분류만). `species_cls` 는 종명 → 분류마다의
    수 — 막대 색을 고를 때 쓴다.
    """
    per_cls = {c["key"]: c["n"] for c in summary["class_counts"]}
    counted = {c["key"] for c in data.counted_classes()}
    per_species: Counter = Counter()
    species_cls: dict[str, Counter] = {}
    for sc in summary.get("species_counts", ()):
        if sc["cls"] not in counted:
            continue                       # 파편·미분류에 붙은 종명은 안 센다
        per_species[sc["species"]] += sc["n"]
        species_cls.setdefault(sc["species"], Counter())[sc["cls"]] += sc["n"]
    n_identified = sum(per_species.values())
    cc = data.count_column(per_cls, summary["n_detected"])
    return {
        **cc,
        "n_detected": summary["n_detected"],
        "n_identified": n_identified,
        "n_unnamed": cc["n_counted"] - n_identified,
        "id_pct": (round(100.0 * n_identified / cc["n_counted"], 1)
                   if cc["n_counted"] else None),
        "per_species": dict(per_species),
        "species_cls": {k: dict(v) for k, v in species_cls.items()},
        # 그래프의 CRS(분류 하나 전체)와 시야당 개체가 쓴다 (P34 5단계)
        "per_cls": per_cls,
        "detected_groups": summary.get("detected_groups", 0),
    }


def species_bars(col: dict) -> list[dict]:
    """슬라이드 화면 `종` 막대 (P34 3단계). 분류 막대(`data._class_bars`)와 같은 모양.

    **길이는 가장 많은 종에 대한 비율**이고(분류 막대와 같다), `share` 가 종명이
    붙은 개체에 대한 비율이다. **색은 그 종이 가장 많이 붙은 분류의 마스크 색**
    — 사진에서 파랗던 것이 막대에서도 파래야 한다(230).

    차례는 많은 순, 같으면 이름순.
    """
    colors = {r["key"]: r["color"] for r in data._class_rows()}
    per = col["per_species"]
    top = max(per.values(), default=0)
    n_id = col["n_identified"]
    out = []
    for name, n in sorted(per.items(), key=lambda kv: (-kv[1], kv[0])):
        by_cls = col["species_cls"].get(name, {})
        cls = max(sorted(by_cls), key=lambda k: by_cls[k]) if by_cls else ""
        out.append({"label": name, "n": n, "cls": cls,
                    "color": colors.get(cls) or "",
                    "pct": round(100 * n / top) if top else 0,
                    "share": round(100.0 * n / n_id, 1) if n_id else None})
    return out


# ─────────────────────────────────────────── 지점 단위 산출표 (P34 4단계)

def merge(cols: list[dict]) -> dict:
    """열 여럿을 하나로 더한다 — **같은 시료의 관찰은 더한다** (P34 6.2).

    관찰은 시료 하나를 처리 방법을 달리해 본 것이라 서로 동등하고 대표를 몰래
    고를 근거가 없다(063 · `derived_series()` 머리말). 비율은 더한 수에서 다시
    낸다 — 비율을 평균하면 개체가 적은 관찰이 같은 무게를 받는다.
    """
    per: Counter = Counter()
    pcls: Counter = Counter()
    for c in cols:
        per.update(c["per_species"])
        pcls.update(c.get("per_cls") or {})
    n = {k: sum(c.get(k) or 0 for c in cols)
         for k in ("n_detected", "n_counted", "n_frag", "n_identified",
                   "detected_groups")}
    return {**n,
            "n_unnamed": n["n_counted"] - n["n_identified"],
            "frag_pct": (round(100.0 * n["n_frag"] / n["n_detected"], 1)
                         if n["n_detected"] else None),
            "id_pct": (round(100.0 * n["n_identified"] / n["n_counted"], 1)
                       if n["n_counted"] else None),
            "per_species": dict(per),
            "per_cls": dict(pcls)}


def _name_key(name: str) -> tuple:
    """속 알파벳순, 속 안에서 종순 — 견본 표(Table 2)의 차례."""
    genus, _, rest = name.partition(" ")
    return (genus.lower(), rest.lower(), name)


def _short(name: str, prev: str) -> str:
    """바로 윗줄과 속이 같으면 속명을 첫 글자로 줄인다 (`A. ingens`). 견본 표가
    그렇게 적는다. **CSV 에는 안 쓴다** — 줄을 정렬하거나 거르면 윗줄이 바뀐다."""
    genus, sp, rest = name.partition(" ")
    if sp and prev.partition(" ")[0] == genus:
        return f"{genus[0]}. {rest}"
    return name


def locality_table(site_code: str, loc_code: str, split_obs: bool = False) -> dict | None:
    """지점 하나의 산출표 — 열은 시료(깊이·단면 위치 차례), 줄은 종.

    **`집계 제외` 관찰은 뺀다**(목록·합계·`derived_series` 와 같은 규칙).
    **`숨김` 은 센다** — 보기 상태이지 자료의 성질이 아니다.

    `split_obs` 면 관찰마다 열을 가른다(사용자가 나중에 조정할 수 있게).
    """
    from .models import Locality

    loc = (Locality.objects.select_related("site")
           .filter(site__code=site_code, code=loc_code).first())
    if loc is None:
        return None
    slides = sorted((sl for sm in loc.samples.select_related("locality").all()
                     for sl in sm.slides.live()), key=data._slide_order)
    used = [sl for sl in slides if not sl.exclude_from_totals]
    summary = data._summary_for(used)
    outcrop = loc.kind == "outcrop"

    # 열 — 시료마다(또는 관찰마다) 하나. 차례는 `_slide_order` 그대로라 같은
    # 시료의 관찰은 붙어 있다.
    groups: list[tuple[tuple, list]] = []
    for sl in used:
        key = (sl.sample_id, sl.id if split_obs else None)
        if groups and groups[-1][0] == key:
            groups[-1][1].append(sl)
        else:
            groups.append((key, [sl]))

    cols = []
    for _, sls in groups:
        c = merge([column(data._slide_summary(sl, summary)) for sl in sls])
        sm = sls[0].sample
        if outcrop or sm is None or sm.depth_cm is None:
            head = sm.code if sm else sls[0].name
        else:
            head = f"{sm.depth_cm:g} cm"
        c.update({
            "head": head,
            # 이름표가 빈 관찰이 많다 — 비우면 같은 깊이 열 둘이 구분이 안 된다
            "obs": ((sls[0].obs_label or (f"({sls[0].obs_no})" if sls[0].obs_no
                                          else sls[0].slug))
                    if split_obs else ""),
            "n_obs": len(sls),
            "slugs": [sl.slug for sl in sls],
            "depth_cm": sm.depth_cm if sm else None,
        })
        cols.append(c)

    names = sorted({n for c in cols for n in c["per_species"]}, key=_name_key)
    rows, prev = [], ""
    for name in names:
        cells = []
        for c in cols:
            n = c["per_species"].get(name, 0)
            cells.append({"n": n,
                          "pct": (round(100.0 * n / c["n_identified"], 1)
                                  if n and c["n_identified"] else None),
                          # 칸에서 카탈로그로 가는 길 — 관찰이 하나인 열만.
                          # 더한 열은 어느 관찰로 갈지 고를 근거가 없다
                          "slug": c["slugs"][0] if len(c["slugs"]) == 1 else "",
                          "noid": not c["n_identified"]})
        total = sum(x["n"] for x in cells)
        n_id = sum(c["n_identified"] for c in cols)
        rows.append({"name": name, "short": _short(name, prev), "cells": cells,
                     "total": total,
                     # 합계 열의 % — 더한 수에서 낸다(열마다의 % 를 평균하지 않는다)
                     "total_pct": round(100.0 * total / n_id, 1) if n_id else None})
        prev = name
    tot = merge(cols) if cols else None
    return {"loc": loc, "site": loc.site, "is_outcrop": outcrop,
            "cols": cols, "rows": rows, "total": tot,
            "split_obs": split_obs,
            "n_excluded": len(slides) - len(used)}


# ─────────────────────────────────────────── 해상도 목표 (260)

# 시료마다 **완형(세는 개체 = 파편 제외)을 몇 개 셌어야 하는가**. 규조 산출의 관례가
# 시료당 300~400 개체다 — 사용자 11-15: 400 을 기준으로, 200~400 에서 고른다.
TARGET_DEFAULT = 400
TARGET_MIN, TARGET_MAX = 200, 400
TARGET_CHOICES = (200, 250, 300, 350, 400)


def parse_target(raw) -> int:
    """`?target=` — 범위 밖이거나 수가 아니면 기본값. **조용히 끝값으로 붙이지
    않는다** — 1000 을 적었는데 400 으로 그려지면 그 그림이 1000 기준인 줄 안다."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return TARGET_DEFAULT
    return v if TARGET_MIN <= v <= TARGET_MAX else TARGET_DEFAULT


def attach_target(t: dict, target: int) -> dict:
    """열마다 `target_pct` = 완형 ÷ 목표 × 100. **100 에서 자르지 않는다** — 넘은
    것도 정보다(그래프는 칸 끝에 붙이고 글자로 실제 값을 적는다). 합계 열에는 안
    낸다 — 목표는 시료 하나의 것이라 시료를 더한 수와 비교하는 것이 성립하지 않는다."""
    t["target"] = target
    for c in t["cols"]:
        c["target_pct"] = round(100.0 * c["n_counted"] / target, 1)
    return t


def table_csv(t: dict, unit: str = "n") -> str:
    """산출표를 CSV 로 (P34 6.3). **속명을 줄이지 않는다**, **0 도 0 으로 적는다** —
    빈칸은 사람이 읽는 표의 관례이고, 받아서 계산하는 쪽에는 "안 셌다" 로 읽힌다."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    pct = unit == "pct"
    heads = [c["head"] + (f" ({c['obs']})" if c["obs"] else "") for c in t["cols"]]
    w.writerow(["species", *heads, "total"])
    for r in t["rows"]:
        vals = [(x["pct"] or 0) if pct else x["n"] for x in r["cells"]]
        w.writerow([r["name"], *vals, (r["total_pct"] or 0) if pct else r["total"]])
    tot = t["total"] or {}
    w.writerow(["(identified)", *[c["n_identified"] for c in t["cols"]],
                tot.get("n_identified", 0)])
    w.writerow(["(counted, non-fragment)", *[c["n_counted"] for c in t["cols"]],
                tot.get("n_counted", 0)])
    w.writerow(["(identified %)", *[c["id_pct"] if c["id_pct"] is not None else ""
                                    for c in t["cols"]], tot.get("id_pct") or ""])
    w.writerow(["(fragment % of detected)",
                *[c["frag_pct"] if c["frag_pct"] is not None else "" for c in t["cols"]],
                tot.get("frag_pct") or ""])
    if t.get("target"):
        w.writerow([f"(target attainment % of {t['target']} counted)",
                    *[c["target_pct"] for c in t["cols"]], ""])
    return buf.getvalue()


# ─────────────────────────────────────────── 산출 그래프 (P34 5단계)

# **기본 종** (사용자 11-13) — 견본 Fig. 2(박영숙 외 2011)의 다섯 + CRS.
# 코드에 박은 것은 **설정이 없을 때의 값**이다. 고치는 자리는 `Setting`
# (`tally_default_taxa`, 판을 안 내고 고친다)과 코어마다의 목록이다.
#
# 항목은 종명이거나 `cls:<분류>` 다 — CRS 는 종 하나가 아니라 **`chaetoceros`
# 분류 전체**다(사용자 11-13: "일단 c 클래스 전체로").
CLS_PREFIX = "cls:"
GRP_PREFIX = "grp:"
# **종 묶음** — 논문이 한 값으로 다루는 종들. 분자는 구성 종의 합, 분모는 종처럼
# 종명이 붙은 개체다(분류 항목과 다르다). 사용자 11-15: FCC complex =
# *F. curta* + *F. cylindrus* — 남극 해빙 지표로 함께 센다.
GROUPS = {
    "fcc": {"name": "FCC complex",
            "members": ("Fragilariopsis curta", "Fragilariopsis cylindrus")},
}
DEFAULT_TAXA = ["Actinocyclus actinochilus", "Eucampia antarctica",
                "Fragilariopsis kerguelensis", "grp:fcc",
                "Rhizosolenia styliformis",
                "Thalassionema nitzschioides", "cls:chaetoceros"]
SETTING_KEY = "tally_default_taxa"


def default_taxa() -> list[str]:
    from .models import Setting
    row = Setting.objects.filter(key=SETTING_KEY).first()
    v = row.value if row else None
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return list(v)
    return list(DEFAULT_TAXA)


def taxa_for(loc) -> list[str]:
    """그 코어에 사람이 정해 둔 목록, 없으면 전역 기본."""
    own = getattr(loc, "tally_taxa", None)
    return list(own) if own else default_taxa()


def taxon_label(item: str) -> dict:
    """항목의 이름표. 분류 항목은 약칭(`ClassDef.short`)을 이름으로 쓴다 — CRS."""
    if item.startswith(CLS_PREFIX):
        key = item[len(CLS_PREFIX):]
        row = next((r for r in data._class_rows() if r["key"] == key), None)
        name = (row["short"] or row["label"]) if row else key
        full = row["label"] if row else key
        return {"item": item, "name": name, "note": f"{full} 분류 전체",
                "italic": False, "is_cls": True}
    if item.startswith(GRP_PREFIX):
        g = GROUPS.get(item[len(GRP_PREFIX):])
        if g:
            note = " + ".join(_abbr(m) for m in g["members"])
            return {"item": item, "name": g["name"], "note": note,
                    "italic": False, "is_cls": False, "is_grp": True}
    return {"item": item, "name": item, "note": "", "italic": True,
            "is_cls": False}


def _abbr(name: str) -> str:
    genus, _, rest = name.partition(" ")
    return f"{genus[0]}. {rest}" if rest else name


def _members(item: str) -> tuple:
    """종 묶음이면 구성 종, 아니면 그 종 하나. 모르는 묶음은 빈 것 — 0 이 아니라
    `None` 이 나오게 부르는 쪽이 거른다."""
    if item.startswith(GRP_PREFIX):
        g = GROUPS.get(item[len(GRP_PREFIX):])
        return tuple(g["members"]) if g else ()
    return (item,)


def taxon_values(cols: list[dict], item: str) -> list[float | None]:
    """열마다의 % — **분모가 없는 열은 `None`**(0 이 아니다 — 안 본 것이다).

    종은 그 열의 **종명이 붙은 개체**가 분모, 분류 항목(CRS)은 **세는 개체 전체**가
    분모다. 분류는 종명 없이도 세어지므로 종명 수로 나누면 100 을 넘는다.
    """
    out = []
    if item.startswith(CLS_PREFIX):
        key = item[len(CLS_PREFIX):]
        for c in cols:
            d = c["n_counted"]
            out.append(round(100.0 * c["per_cls"].get(key, 0) / d, 2) if d else None)
    else:
        ms = _members(item)
        for c in cols:
            d = c["n_identified"]
            n = sum(c["per_species"].get(m, 0) for m in ms)
            out.append(round(100.0 * n / d, 2) if d and ms else None)
    return out


def _nice_max(v: float) -> float:
    for m in (1, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100):
        if v <= m:
            return m
    return math.ceil(v / 50) * 50


def plot(t: dict, taxa: list[str], series_keys: list[str] | None = None) -> dict:
    """현대식 산출 그래프 (견본 Fig. 2). **SVG 문자열을 서버가 만든다.**

    화면에 얹는 것과 내려받는 것이 같은 그림이어야 해서다 — 논문 그림으로 가져가
    다듬을 것이라 흰 바탕·검은 선이고 테마를 안 따른다.

    - 세로축: 시추코어는 깊이(cm, 위가 얕다). **노두는 시료 차례**를 같은 간격으로
      — cm 축에 얹으면 없는 간격을 지어낸다(지점 화면과 같은 규칙).
    - 패널마다 가로축이 따로다 — 한 종이 60% 면 나머지가 다 눌린다.
    - 맨 앞에 고른 **코어 자료**(P17), 맨 뒤에 **동정률**과 **시야당 세는 개체**.
    """
    from html import escape
    cols = t["cols"]
    loc = t["loc"]
    outcrop = t["is_outcrop"]

    # ── 세로축
    prof: list = []
    if outcrop:
        ys = list(range(len(cols)))
        lo, hi = -0.5, max(len(cols) - 0.5, 0.5)
        ticks = [(i, c["head"]) for i, c in enumerate(cols)]
        axis_name = "시료 차례"
    else:
        ys = [c["depth_cm"] for c in cols]
        prof = data.core_profiles(loc, series_keys or [])
        depths = [y for y in ys if y is not None]
        for p in prof:
            for seg in p["segments"]:
                depths += [pt["cm"] for pt in seg]
        if depths:
            dmin, dmax = min(depths), max(depths)
        else:
            dmin, dmax = 0, 10
        step = data._nice_step(max(dmax - dmin, 1))
        lo = math.floor(dmin / step) * step
        hi = math.ceil(dmax / step) * step
        if hi <= lo:
            hi = lo + step
        ticks = [(v, f"{v:g}") for v in range(int(lo), int(hi) + 1, step)]
        axis_name = "깊이 (cm)"

    panels = []
    for p in prof:
        panels.append({"title": p["label"], "sub": p["unit"], "italic": False,
                       "kind": "core", "segs": p["segments"],
                       "lo": p["lo"], "hi": p["hi"]})
    for item in taxa:
        lab = taxon_label(item)
        vals = taxon_values(cols, item)
        top = max([v for v in vals if v is not None] + [0])
        panels.append({"title": lab["name"], "italic": lab["italic"],
                       "sub": ("% (세는 개체)" if lab["is_cls"]
                               else "% (종 합)" if lab.get("is_grp") else "%"),
                       "kind": "pct", "vals": vals, "xmax": _nice_max(top)})
    idv = [c["id_pct"] for c in cols]
    target = t.get("target")
    # 동정률 점마다 **완형 수 / 목표 · 달성률** 을 적는다 (260) — 동정률 60% 가 완형
    # 20개의 60% 인지 400개의 60% 인지 그림에서 갈려야 한다
    labels = ([(c["n_counted"], c.get("target_pct")) for c in cols]
              if target else None)
    panels.append({"title": "동정률", "italic": False,
                   "sub": f"% · 완형/{target}" if target else "%", "kind": "pct",
                   "vals": idv, "xmax": 100, "labels": labels})
    pv = [(round(c["n_counted"] / c["detected_groups"], 2)
           if c.get("detected_groups") else None) for c in cols]
    panels.append({"title": "시야당 개체", "italic": False, "sub": "개/시야",
                   "kind": "pct", "vals": pv,
                   "xmax": _nice_max(max([v for v in pv if v is not None] + [0]))})

    # ── 그리기
    PW, GAP, LEFT, TOP, H, BOT = 96, 12, 64, 58, 440, 26
    W = LEFT + len(panels) * (PW + GAP) + 8
    HH = TOP + H + BOT

    def Y(v):
        return TOP + (v - lo) / (hi - lo) * H

    # 글자를 적을 만큼 시료가 떨어져 있는가 — 촘촘한 코어(1 cm 간격)에서는 글자가
    # 겹쳐 아무것도 안 읽힌다. 그때는 점의 <title> 과 표에만 남는다.
    yp = sorted(Y(y) for y in ys if y is not None)
    roomy = all(b - a >= 22 for a, b in zip(yp, yp[1:]))

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {HH}" '
         f'width="{W}" height="{HH}" font-family="Helvetica, Arial, sans-serif" '
         f'font-size="10">',
         f'<rect width="{W}" height="{HH}" fill="#fff"/>']
    # 세로축 눈금
    o.append(f'<text x="12" y="{TOP + H / 2}" transform="rotate(-90 12 {TOP + H / 2})" '
             f'text-anchor="middle" fill="#000">{escape(axis_name)}</text>')
    for v, txt in ticks:
        y = Y(v)
        o.append(f'<text x="{LEFT - 6}" y="{y + 3:.1f}" text-anchor="end" fill="#000">'
                 f'{escape(str(txt))}</text>')
    for i, pn in enumerate(panels):
        x0 = LEFT + i * (PW + GAP)
        o.append(f'<g class="panel" data-kind="{pn["kind"]}">')
        # 제목 — 두 줄로 나눠 좁은 칸에 넣는다
        words = pn["title"].split(" ", 1)
        style = ' font-style="italic"' if pn["italic"] else ""
        for j, w in enumerate(words):
            o.append(f'<text x="{x0 + PW / 2}" y="{12 + j * 12}" text-anchor="middle" '
                     f'font-weight="bold"{style} fill="#000">{escape(w)}</text>')
        o.append(f'<text x="{x0 + PW / 2}" y="{38}" text-anchor="middle" fill="#555">'
                 f'{escape(pn["sub"])}</text>')
        o.append(f'<rect x="{x0}" y="{TOP}" width="{PW}" height="{H}" fill="none" '
                 f'stroke="#000" stroke-width="0.8"/>')
        for v, _ in ticks:
            y = Y(v)
            o.append(f'<line x1="{x0}" x2="{x0 + 4}" y1="{y:.1f}" y2="{y:.1f}" stroke="#000" stroke-width="0.6"/>')
        if pn["kind"] == "core":
            # 범위는 유효숫자 셋 — 반입값 그대로 찍으면 `2.89738` 이 칸을 넘는다
            if pn["lo"] is not None:
                o.append(f'<text x="{x0 + 1}" y="{TOP - 6}" fill="#000">{pn["lo"]:.3g}</text>')
                o.append(f'<text x="{x0 + PW - 1}" y="{TOP - 6}" text-anchor="end" '
                         f'fill="#000">{pn["hi"]:.3g}</text>')
            for seg in pn["segs"]:
                pts = [(x0 + pt["x"] / 100 * PW, Y(pt["cm"])) for pt in seg
                       if lo <= pt["cm"] <= hi]
                if len(pts) > 1:
                    o.append('<polyline fill="none" stroke="#000" stroke-width="0.8" points="'
                             + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>')
                elif pts:
                    o.append(f'<circle cx="{pts[0][0]:.1f}" cy="{pts[0][1]:.1f}" r="1.5"/>')
        else:
            xm = pn["xmax"]
            # 양 끝 눈금 글자는 칸 안쪽으로 붙인다 — 가운데 맞춤이면 옆 칸의 0 과 겹친다
            for tv, anchor, dx in ((0, "start", 1), (xm / 2, "middle", 0),
                                   (xm, "end", -1)):
                tx = x0 + tv / xm * PW
                o.append(f'<line x1="{tx:.1f}" x2="{tx:.1f}" y1="{TOP}" y2="{TOP - 3}" stroke="#000" stroke-width="0.6"/>')
                o.append(f'<text x="{tx + dx:.1f}" y="{TOP - 6}" text-anchor="{anchor}" '
                         f'fill="#000">{tv:g}</text>')
            # 분모가 없는 열(None)에서 선을 끊는다 — 이으면 안 본 자리를 본 것처럼 그린다
            run: list = []
            runs = []
            pts = []
            for y, v in zip(ys, pn["vals"]):
                if y is None or v is None:
                    if run:
                        runs.append(run)
                    run = []
                    continue
                pt = (x0 + min(v, xm) / xm * PW, Y(y), v)
                run.append(pt)
                pts.append(pt)
            if run:
                runs.append(run)
            for r in runs:
                if len(r) > 1:
                    o.append('<polyline fill="none" stroke="#000" stroke-width="0.9" points="'
                             + " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in r) + '"/>')
            labs = pn.get("labels")
            k = 0
            for y, v, lab in zip(ys, pn["vals"], labs or [None] * len(ys)):
                if y is None or v is None:
                    continue
                x, yy, _ = pts[k]
                k += 1
                tip = f"{v:g}"
                if lab:
                    tip += f" · 완형 {lab[0]}/{target} · 목표 달성 {lab[1]:g}%"
                o.append(f'<path class="pt" d="M{x:.1f} {yy - 3:.1f}L{x + 3:.1f} {yy:.1f}'
                         f'L{x:.1f} {yy + 3:.1f}L{x - 3:.1f} {yy:.1f}Z" fill="#fff" '
                         f'stroke="#000" stroke-width="0.8"><title>{escape(tip)}</title></path>')
            # 달성률 글자는 **점의 반대쪽 절반**에 — 점·선과 안 겹친다
            if labs and roomy:
                for y, v, lab in zip(ys, pn["vals"], labs):
                    if y is None or lab is None:
                        continue
                    yy = Y(y)
                    right = v is None or v < xm / 2
                    tx, anchor = (x0 + PW - 3, "end") if right else (x0 + 3, "start")
                    o.append(f'<text class="tgt" x="{tx}" y="{yy - 1:.1f}" text-anchor="{anchor}" '
                             f'font-size="8" fill="#000">{lab[0]}/{target}</text>')
                    o.append(f'<text class="tgt" x="{tx}" y="{yy + 8:.1f}" text-anchor="{anchor}" '
                             f'font-size="8" fill="#555">{lab[1]:g}%</text>')
        o.append("</g>")
    o.append(f'<text x="{LEFT}" y="{HH - 8}" fill="#555">{escape(loc.code)} · '
             f'% 의 분모: 종 = 종명이 붙은 개체 · 분류 항목 = 세는 개체 · 파편은 세지 않는다 · '
             f'검토를 마친 시야만'
             + (f' · 완형/{target} = 세는 개체 ÷ 해상도 목표 {target}' if target else '')
             + "".join(f' · {escape(taxon_label(x)["name"])} = {escape(taxon_label(x)["note"])}'
                       for x in taxa if x.startswith(GRP_PREFIX) and x[len(GRP_PREFIX):] in GROUPS)
             + '</text>')
    o.append("</svg>")
    return {"svg": "".join(o), "panels": len(panels),
            "n_points": sum(1 for pn in panels if pn["kind"] == "pct"
                            for v, y in zip(pn["vals"], ys)
                            if v is not None and y is not None)}


def taxa_options(t: dict, loc) -> list[dict]:
    """고를 수 있는 항목 — **전역 기본 · 이 코어에 저장한 것 · 표에 나온 종 · 분류 항목**.

    차례: 전역 기본 목록의 차례 → 저장한 것 → 나머지 종(속 알파벳순) → 분류 항목.
    분류 항목은 **세는 분류 중 분류학으로 알아본 것**(`is_taxon`)만 — 원형·봉상은
    형태라 산출 그래프의 줄이 아니다.
    """
    seen: dict[str, dict] = {}

    def add(item, src):
        if item and item not in seen:
            seen[item] = {**taxon_label(item), "src": src,
                          "total": None}

    for x in default_taxa():
        add(x, "default")
    for x in (getattr(loc, "tally_taxa", None) or []):
        add(x, "saved")
    for r in t["rows"]:
        add(r["name"], "table")
    for k in GROUPS:
        add(GRP_PREFIX + k, "group")
    for r in data._class_rows():
        if r["counted"] and r.get("is_taxon"):
            add(CLS_PREFIX + r["key"], "class")
    tot = t.get("total") or {}
    for item, o in seen.items():
        if item.startswith(CLS_PREFIX):
            o["total"] = (tot.get("per_cls") or {}).get(item[len(CLS_PREFIX):], 0)
        else:
            ps = tot.get("per_species") or {}
            o["total"] = sum(ps.get(m, 0) for m in _members(item))
    return list(seen.values())


# ─────────────────────────────────────────── 슬라이드 산출표 (261)

def slide_table(slide, target: int = TARGET_DEFAULT, sort: str = "n") -> dict:
    """슬라이드 하나의 **산출표 화면** (261 · 사용자 11-15: "지금 건 그대로 두고
    화면을 따로 하나"). 슬라이드 화면 분류 상자의 `종` 쪽(258)과 **같은 셈**이다 —
    `column()` 하나를 두 화면이 쓴다. 다른 것은 펼친 정도다:

    - 요약 — 검토 완료 시야 · 완형(세는 개체) · 해상도 목표 · 동정률 · 파편
    - 종 표 — 개수 · 종명 붙은 개체 중 % · 세는 개체 중 % · 붙은 분류
    - 분류 표 — 분류마다 개체 · **그 분류 안의 동정률** · 세는가

    `sort` — `n`(많은 순, 기본) · `name`(속 알파벳순 — 옛 산출표의 차례, 윗줄과 같은
    속은 줄인다).
    """
    summary = data._slide_summary(slide)
    col = column(summary)
    n_id, n_cnt = col["n_identified"], col["n_counted"]
    rows_by = {r["key"]: r for r in data._class_rows()}

    sp_rows = []
    for name, n in col["per_species"].items():
        by_cls = col["species_cls"].get(name, {})
        cls_keys = sorted(by_cls, key=lambda k: (-by_cls[k], k))
        sp_rows.append({
            "name": name, "n": n,
            "share_id": round(100.0 * n / n_id, 1) if n_id else None,
            "share_cnt": round(100.0 * n / n_cnt, 1) if n_cnt else None,
            "cls": [{"key": k, "short": (rows_by.get(k) or {}).get("short", k),
                     "color": (rows_by.get(k) or {}).get("color") or "",
                     "n": by_cls[k]} for k in cls_keys],
        })
    if sort == "name":
        sp_rows.sort(key=lambda r: _name_key(r["name"]))
        prev = ""
        for r in sp_rows:
            r["short"] = _short(r["name"], prev)
            prev = r["name"]
    else:
        sp_rows.sort(key=lambda r: (-r["n"], _name_key(r["name"])))
        for r in sp_rows:
            r["short"] = r["name"]
    top = max((r["n"] for r in sp_rows), default=0)
    for r in sp_rows:
        r["bar"] = round(100 * r["n"] / top) if top else 0

    # 분류마다 — 세는 분류 먼저(정렬 차례), 파편은 뒤에 따로
    id_by_cls: Counter = Counter()
    for name, by_cls in col["species_cls"].items():
        id_by_cls.update(by_cls)
    cls_rows = []
    for r in data._class_rows():
        n = col["per_cls"].get(r["key"], 0)
        if not n:
            continue
        counted = bool(r["counted"])
        cls_rows.append({
            "key": r["key"], "label": r["label"], "short": r["short"],
            "color": r["color"] or "", "n": n, "counted": counted,
            "n_id": id_by_cls.get(r["key"], 0) if counted else None,
            "id_pct": (round(100.0 * id_by_cls.get(r["key"], 0) / n, 1)
                       if counted else None),
            "share_cnt": round(100.0 * n / n_cnt, 1) if counted and n_cnt else None,
        })
    cls_rows.sort(key=lambda c: (not c["counted"],
                                 rows_by[c["key"]]["sort_order"], c["key"]))
    return {
        "col": col, "target": target,
        "target_pct": round(100.0 * n_cnt / target, 1),
        "target_bar": min(100, round(100 * n_cnt / target)),
        "n_groups": summary["n_groups"],
        "reviewed_groups": summary["reviewed_groups"],
        "sp_rows": sp_rows, "cls_rows": cls_rows, "sort": sort,
    }


def slide_csv(st: dict) -> str:
    """슬라이드 산출표 CSV — 종 표 + 요약 줄. 속명을 줄이지 않는다."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["species", "n", "% of identified", "% of counted", "classes"])
    for r in st["sp_rows"]:
        w.writerow([r["name"], r["n"],
                    r["share_id"] if r["share_id"] is not None else "",
                    r["share_cnt"] if r["share_cnt"] is not None else "",
                    " ".join(f'{c["key"]}:{c["n"]}' for c in r["cls"])])
    c = st["col"]
    w.writerow([])
    for k, v in (("identified", c["n_identified"]),
                 ("counted (non-fragment)", c["n_counted"]),
                 ("unnamed", c["n_unnamed"]),
                 ("identified %", c["id_pct"] if c["id_pct"] is not None else ""),
                 ("fragments", c["n_frag"]),
                 ("fragment % of detected",
                  c["frag_pct"] if c["frag_pct"] is not None else ""),
                 (f"target attainment % of {st['target']} counted", st["target_pct"]),
                 ("reviewed viewpoints", st["reviewed_groups"]),
                 ("viewpoints", st["n_groups"])):
        w.writerow([f"({k})", v])
    return buf.getvalue()
