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
    for c in cols:
        per.update(c["per_species"])
    n = {k: sum(c[k] for c in cols)
         for k in ("n_detected", "n_counted", "n_frag", "n_identified")}
    return {**n,
            "n_unnamed": n["n_counted"] - n["n_identified"],
            "frag_pct": (round(100.0 * n["n_frag"] / n["n_detected"], 1)
                         if n["n_detected"] else None),
            "id_pct": (round(100.0 * n["n_identified"] / n["n_counted"], 1)
                       if n["n_counted"] else None),
            "per_species": dict(per)}


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
    return buf.getvalue()
