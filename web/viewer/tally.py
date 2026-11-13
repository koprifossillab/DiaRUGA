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
