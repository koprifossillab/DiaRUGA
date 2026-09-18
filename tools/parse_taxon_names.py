#!/usr/bin/env python3
"""학명 유효성 판정을 `taxon_names.json` 으로 뽑는다 — P24.

원본은 NAS 두 벌이다. **여기서는 이름을 새로 조회하지 않는다** — 사람이
브라우저로 AlgaeBase 를 이미 열어 확인한 것을 그러모을 뿐이다.

- `Diadiction/names/worms/worms_master_20260814.tsv` — 도감 1,845종의
  마스터 표(08-14~08-26, 37일치 배치). `AlgaeBase` 칼럼이 채워진 행만
  쓴다. 그 칼럼 값이 상태 문구 여섯 개(`그대로 유효`·`AlgaeBase 에
  없다`·`확인 필요`·`아직 안 찾았다`·`안 적혀 있다`·`미확인`) 중
  하나가 아니면, **그 값 자체가 새 학명이다**(이명 → 갈아탄다)
- `Diadiction/names/algaebase/paper_plates_filled_20260831.json` — 논문
  도판(P22·P23) 캡션 학명 156종을 **사람이 철자를 먼저 교정하고**
  AlgaeBase 상세 페이지의 `Status of Name` 을 읽어 채운 표(2026-08-31,
  `paper_plates_answered_20260831.md` 와 같은 자료 · `paper_plates_notes_
  20260831.md` 가 읽는 법과 결과를 정리해 뒀다). **09-18 까지 `temp/filled.json`
  이었다** — `temp/` 는 README 가 "언제든 비워도 됨" 이라 못 박은 자리라
  옮겼다(이름은 ASCII · 내용은 md5 같음). 열쇠는 **교정 전** 표기(`row[0]`) 그대로 쓴다 —
  `AtlasEntry.binomial` 도 캡션 원문을 그대로 정규화한 것이라 맞아야
  한다. `row[2]` 가 굵게 적힌 새 이름이면(철자 교정만이든 진짜 이명이든)
  `synonym` 으로 통일한다 — 검색 기능이 보기엔 "조회한 표기로는 안
  걸리고 이 이름으로 걸린다" 는 같은 동작이라 둘을 가를 필요가 없다.
  **1991 연일층군 논문에 규조가 아닌 것(규질편모조류·에브리아류) 14~20건이
  섞여 있다** — `공부노트` 가 찾아 둔 것이라 `비고` 에 그대로 남아 화면에
  보인다("규조 아님" 문구), 걸러내지는 않는다(캡션에 있는 이름이라
  `AtlasEntry` 에도 이미 들어가 있다 — TaxonName 이 그것까지 가릴 자리는
  아니다)

- `Diadiction/names/algaebase/antarctic2002_filled_20260918.json` — 남극
  논문 둘(207 · Censarek 2002 · Zielinski 2002)의 캡션 학명 중 판정이
  없던 32종을 같은 방법으로 채운 표(2026-09-18, `antarctic2002_answered_
  20260918.md`·`_notes_`·`_raw*_` 가 같은 자료). 모양이 `filled.json` 과
  같아 같은 파서로 읽는다. **둘을 손으로 잡아 둔 자리가 있다**
  (`HOLD`·`EXTRA`, 아래 주석) — 조회한 사람이 정리 노트에서 "이 판정은
  반영하지 말라" 고 한 것과, 조회 중에 함께 확인된 다른 조합이다

열쇠는 `tools/harvest_worms.binomial()` 로 정규화한다 — `var.`·`sp.`
꼬리는 종 단위로 뭉뚱그려진다(예: `Actinocyclus ehrenbergii var.
tenella` → `Actinocyclus ehrenbergii`). **두 소스가 같은 binomial 을
내면**(실측 2건뿐이다, 08-31) 실제 판정이 있는 쪽(accepted/synonym)을
실패한 쪽(absent/unassessed)보다 우선하고, 둘 다 판정이 있는데 갈리면
`worms_master`(더 크고 오래 검토된 자료)를 쓰되 **엇갈렸다는 사실은
`note` 에 남긴다**(지우지 않는다 — `name_validity_log.md` 의 규칙).

사용:

    python tools/parse_taxon_names.py                 # taxon_names.json 으로 뽑는다
    python tools/parse_taxon_names.py --dry-run       # 안 쓰고 요약만 본다
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION, binomial  # noqa: E402

WORMS_MASTER = DIADICTION / "names/worms/worms_master_20260814.tsv"
PAPER_FILLED = DIADICTION / "names/algaebase/paper_plates_filled_20260831.json"
PAPER_FILLED_2002 = DIADICTION / "names/algaebase/antarctic2002_filled_20260918.json"

# **판정을 그대로 반영하지 않는 이름** — 조회한 사람이 정리 노트에서 짚었다.
# `Nitzschia denticuloides`: AlgaeBase 가 `N. amphibia f. frauenfeldii`(담수종의
# 품종)로 넘기는데, 남극 중기 마이오세 층서 지표종이 담수종 품종일 리 없다 —
# 동명이의를 잘못 이은 것으로 보인다(worms_master 도 같은 이유로 `확인 필요`
# 를 뒀다: Hustedt 판 vs Schrader 판). 원기재 확인 전까지 `unassessed` 로 둔다
HOLD = {
    "Nitzschia denticuloides":
        "⚠ 09-18 남극 논문 조회는 N. amphibia f. frauenfeldii 이명으로 냈으나 "
        "동명이의 오연결로 보여 반영하지 않았다(정리 노트 5절)",
}

# **조회하다 함께 확인된 다른 조합** — 답변 표엔 없지만 `raw2.tsv` 에 판정이
# 있고 도감 항목(`AtlasEntry.binomial`)에 그 표기가 있는 것만 싣는다.
# `Nitzschia reinholdii`(1985 Plate) 는 `Fragilariopsis reinholdii` 와 같이
# `F. kanayae` 로 간다 — 종소명이 통째로 바뀌어 기계적으로는 못 잇는 자리
EXTRA = {
    "Nitzschia reinholdii": {
        "binomial": "Nitzschia reinholdii",
        "status": "synonym",
        "valid_name": "Fragilariopsis kanayae D.M.Williams & Kociolek",
        "source": "antarctic2002-raw2-20260918",
        "note": "갱신 2018 · Fragilariopsis reinholdii 와 함께 F. kanayae 로 "
                "(정리 노트 4절 · raw2.tsv)",
        "checked": "2018",
    },
}
OUT = Path(__file__).resolve().parent.parent / "taxon_names.json"

# worms_master 의 `AlgaeBase` 칼럼이 이 문구 중 하나면 그게 상태다.
# 그 여섯이 아니면 값 자체가 새 학명(synonym) 이다.
STATUS_WORDS = {
    "그대로 유효": "accepted",
    "AlgaeBase 에 없다": "absent",
    "확인 필요": "unassessed",
    "아직 안 찾았다": "unassessed",
    "안 적혀 있다": "unassessed",
    "미확인": "unassessed",
}

RESOLVED = {"accepted", "synonym"}


def from_worms_master() -> dict[str, dict]:
    """도감 1,845종 마스터 표를 읽는다."""
    out: dict[str, dict] = {}
    with WORMS_MASTER.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            ab = (row.get("AlgaeBase") or "").strip()
            if not ab:
                continue
            b = binomial(row["이름"]) or row["이름"].strip()
            if ab in STATUS_WORDS:
                status, valid_name = STATUS_WORDS[ab], ""
            else:
                status, valid_name = "synonym", ab
            out[b] = {
                "binomial": b,
                "status": status,
                "valid_name": valid_name,
                "source": "worms-master-20260814",
                "note": (row.get("AlgaeBase비고") or "").strip(),
                "checked": (row.get("갱신") or "").strip(),
            }
    return out


CHECKED_RE = re.compile(r"갱신\s*(\d{4})")


def from_paper_plates(path: Path = PAPER_FILLED,
                      source: str = "paper-plates-filled-20260831") -> dict[str, dict]:
    """논문 도판 캡션 학명을 사람이 철자 교정 뒤 AlgaeBase 로 채운 표를 읽는다.

    `filled.json` 은 `[캡션 원문 표기, 논문(들), 판정, 비고]` 네 칸짜리
    행이다(156종 · 남극 2002 는 32종). **열쇠는 캡션 원문 표기**(교정 전) —
    `AtlasEntry.binomial` 이 그 표기를 정규화한 것과 같아야 찾아진다.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for orig, _papers, verdict, note in rows:
        b = binomial(orig)
        if b is None:
            continue
        v = verdict.strip()
        if v.startswith("**") and v.endswith("**"):
            # 굵은 이름 — 철자 교정만이든 진짜 이명이든 "이 표기로는 안
            # 걸리고 이 이름으로 걸린다" 는 검색 쪽에선 같은 동작이라
            # 가르지 않는다(머리말 참고)
            status, valid_name = "synonym", v.strip("*")
            # 굵은 이름이 열쇠와 같은 종이면(`Crucidenticula kanayae var.
            # kanayae` → `C. kanayae`) 이명이 아니라 종 단위로는 유효다 —
            # 자기 자신을 가리키는 synonym 을 내면 안 된다
            if binomial(valid_name) == b:
                status, valid_name = "accepted", ""
        elif "그대로 유효" in v:
            status, valid_name = "accepted", ""
        elif "없음" in v:  # `AlgaeBase에 없음`
            status, valid_name = "absent", ""
        else:  # `확인 필요`
            status, valid_name = "unassessed", ""
        m = CHECKED_RE.search(note)
        out[b] = {
            "binomial": b,
            "status": status,
            "valid_name": valid_name,
            "source": source,
            "note": note,
            "checked": m.group(1) if m else "",
        }
    return out


def merge(worms: dict[str, dict], paper: dict[str, dict]) -> dict[str, dict]:
    """겹치는 이름은 판정이 있는 쪽을 우선하고, 갈리면 worms_master 를 쓰되
    엇갈렸다는 사실을 note 에 남긴다."""
    out = dict(worms)
    for b, p in paper.items():
        w = out.get(b)
        if w is None:
            out[b] = p
            continue
        if w["status"] in RESOLVED and p["status"] in RESOLVED:
            if w["status"] == p["status"] and w["valid_name"] == p["valid_name"]:
                w["note"] = (w["note"] + " · 논문 도판 조회도 같은 판정"
                             if w["note"] else "논문 도판 조회도 같은 판정")
            else:
                w["note"] = (
                    f"{w['note']} · ⚠ 논문 도판 조회는 다른 판정"
                    f"({p['status']}"
                    f"{' → ' + p['valid_name'] if p['valid_name'] else ''})"
                ).strip(" ·")
        elif w["status"] not in RESOLVED and p["status"] in RESOLVED:
            out[b] = p  # worms_master 쪽이 못 찾았는데 논문 조회가 판정을 냈다
        # 그 반대(w 가 판정 있고 p 가 실패)는 w 를 그대로 둔다 — 위 사례
        # (var. 형태를 종 단위로 뭉뚱그려 조회가 실패한 경우)가 이 자리다
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    worms = from_worms_master()
    paper = from_paper_plates()
    merged = merge(worms, paper)
    # 남극 2002(32종) — 같은 규칙으로 얹는다. 잡아 둔 것(HOLD)은 판정 대신
    # 그 사실을 note 에 남기고, 덤으로 확인된 조합(EXTRA)은 없을 때만 더한다
    paper2 = from_paper_plates(PAPER_FILLED_2002, "antarctic2002-filled-20260918")
    for b, why in HOLD.items():
        if b in paper2:
            paper2[b]["status"], paper2[b]["valid_name"] = "unassessed", ""
            paper2[b]["note"] = (paper2[b]["note"] + " · " + why).strip(" ·")
    merged = merge(merged, paper2)
    for b, why in HOLD.items():
        # 양쪽 다 판정이 없으면 merge 가 note 를 안 건드린다 — 잡아 둔 사실은 남긴다
        if b in merged and why not in merged[b]["note"]:
            merged[b]["note"] = (merged[b]["note"] + " · " + why).strip(" ·")
    for b, row in EXTRA.items():
        merged.setdefault(b, dict(row))

    from collections import Counter
    c = Counter(v["status"] for v in merged.values())
    overlap = set(worms) & set(paper)
    print(f"worms_master {len(worms)} · paper_plates {len(paper)} "
          f"· 겹침 {len(overlap)} · 남극2002 {len(paper2)} · 덤 {len(EXTRA)} "
          f"· 합계 {len(merged)}")
    print("  " + " · ".join(f"{k} {v}" for k, v in c.most_common()))

    if args.dry_run:
        return 0

    OUT.write_text(json.dumps(sorted(merged.values(), key=lambda r: r["binomial"]),
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
