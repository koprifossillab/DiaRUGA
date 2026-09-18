#!/usr/bin/env python3
"""생층서 기준면(FO·LO) 표를 `atlas/biodatum/datums.json` 으로 뽑는다 — P28 1단계.

원본은 NAS `Diadiction/datums/` 다 — 사람이 논문 열넷을 읽고 원문과
대조해 만든 표(2026-09-18). **여기서는 연령을 새로 매기지 않는다** — 그
표를 DB 가 읽을 모양으로 고를 뿐이다.

- `diatom_datums_1.json` — 기준면 728행 + 출처 14 + Warnock 대 6 + LR04 표.
  `temp/` 에 셋으로 자라 있던 판 중 마지막 것(MIS 열 다섯이 더 있다).
  앞 두 판은 `datums/_old/` 에 있고 안 본다 — 행 단위로 대조해 내용이
  같은 것을 확인했다(P28 §1)
- `규조_생층서_기준면_대조표_2.xlsx` — 같은 표의 사람용. **「대(zone)」
  시트만 읽는다** — Censarek 20·NPD 18 대가 JSON 에는 없다. 파일 이름이
  CP949 라 이름으로 안 짚고 `*.xlsx` 하나를 잡는다

## 표를 그대로 넣으면 안 되는 자리 (P28 §1.2 · 전부 실측)

- **`(출처, 종, 기준면)` 이 열쇠가 아니다** — Cody 의 두 모델·Censarek 의
  남북 대 구분·Warnock 경유 재인용이 같은 열쇠로 겹친다(209건). `note` 첫
  토막과 `code` 에 있던 것을 `variant`·`via` 칸으로 올린다
- **`species`(정규화) 열이 다 정규화되어 있지 않다** — 종소명 대문자
  (`Rouxia Antarctica`)·낱말 갈라짐(`prae dimorpha`)·앞 대시. 소문자로
  내리면 174 → 170 이 되는데, **합쳐지는 것은 `MERGE_OK` 에 못 박은 넷뿐**
  이고 새로 합쳐지는 것이 생기면 멈춘다(표를 만든 사람이 넷은 맞다고 했다,
  09-18). `Shionodiscus tetraoestruppii var.`(오식·재인용) 은 **합치지
  않는다** — 반입 뒤 AlgaeBase 재확인 목록으로 간다
- **`var.` 는 떼지 않는다.** 변종은 다른 사건이다(용어 시트). 맞추는 열쇠
  `binomial` 만 두 낱말(`harvest_worms.binomial()` — 도감과 같은 규칙)이고
  표시 이름 `name` 은 변종까지 든다
- 파생 열(`spread_*`·`pkg*`·`plate_path`·`algaebase`·`mis_calc` 류)은
  안 옮긴다 — DB 가 이미 더 정확히 알거나 화면이 계산한다

사용:

    python tools/parse_biodatums.py              # atlas/biodatum/datums.json
    python tools/parse_biodatums.py --dry-run    # 안 쓰고 요약만
    python tools/parse_biodatums.py --recheck    # AlgaeBase 재확인 목록(도감 판정이 없는 이름)을 찍는다
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION, GENUS_FIX, binomial  # noqa: E402

SRC_DIR = DIADICTION / "datums"
SRC_JSON = SRC_DIR / "diatom_datums_1.json"
REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "atlas" / "biodatum" / "datums.json"
TAXON_NAMES = REPO / "taxon_names.json"

# 기준면 어휘. 벗어나면 멈춘다 — 아홉째가 조용히 들어오면 화면이 못 읽는다
DATUM_KINDS = ("FO", "LO", "FCO", "LCO", "LCO(LAAD)", "AC1", "AC2", "AC+LCO")

# `note` 첫 토막 → variant. Cody 두 모델 · Crampton 복합. Censarek 은 `code`
VARIANT_OF = {
    "Average Range Model": "average",
    "Total Range Model": "total",
    "Composite mid-age": "composite",
}
CODE_VARIANT = {"SSODZ", "NSODZ"}

# 재인용 경유 — 표 전체에서 경유 문헌은 Warnock 하나뿐이다. 다른 문구가
# `경유`·`재인용` 을 달고 나오면 멈춘다
VIA_PHRASES = {
    "Warnock et al. (2025) Table 2 경유": "warnock2025",
    "Warnock et al. (2025) 본문에서 재인용 — 원문 미대조": "warnock2025",
}

CONFIDENCE = {
    "높음(원문 대조)": "high",
    "높음(재인용 원문 대조)": "recite",
    "보통(재인용)": "mid",
    "낮음(웹 요약 1회, 원문 미대조)": "low",
}

PRIMARY_MARKS = ("주요 지시종(+)", "주요 기준면(#)")

# 표기 고침 — 표의 `species` 열에서 확인된 것만. 원문 표기는 `name_printed` 에 남는다
NAME_FIX = {
    "Denticulopsis prae dimorpha": "Denticulopsis praedimorpha",
}

# 소문자로 내려 합쳐져도 되는 것 (표를 만든 사람이 확인, 2026-09-18).
# 값: 합쳐지는 원문 표기들. 여기 없는 합침이 생기면 멈춘다
MERGE_OK = {
    "Rouxia antarctica": {"Rouxia Antarctica", "Rouxia antarctica"},
    "Thalassiosira antarctica": {"Thalassiosira Antarctica", "Thalassiosira antarctica"},
    "Denticulopsis praedimorpha": {"Denticulopsis prae dimorpha", "Denticulopsis praedimorpha"},
    "Crucidenticula nicobarica": {"–Crucidenticula nicobarica", "Crucidenticula nicobarica"},
}

# xlsx 「대(zone)」 시트의 체계 문구 → 코드
ZONE_SCHEME = {
    "Warnock et al. (2025) / Winter et al. (2012)": "warnock2025",
    "Censarek (2002) SSODZ": "censarek-ssodz",
    "Censarek (2002) NSODZ": "censarek-nsodz",
    "NPD (Yanagisawa & Akiba 1998 / IODP 346)": "npd",
}

EPITHET = re.compile(r"^[a-zöäüéë\-]+$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_name(raw: str) -> tuple[str, str, str, str]:
    """표의 `species` → (name, binomial, genus, infra).

    `name` 은 표시 이름(변종까지), `binomial` 은 도감과 맞추는 두 낱말.
    비공식 이름(`Nitzschia 17 Schrader 1976`)은 `binomial` 이 빈 칸이고
    `name` 은 표기 그대로다 — 사건은 유효하지만 맞출 종이 없다.
    """
    s = raw.strip().lstrip("–-— ").strip()
    s = NAME_FIX.get(s, s)
    words = s.split()
    genus = GENUS_FIX.get(words[0].capitalize(), words[0].capitalize())
    # 종소명이 두 글자 이하면 형태 기호다(`Actinocyclus F …`·`Fragilariopsis A …`)
    if len(words) < 2 or len(words[1]) < 3 or not EPITHET.match(words[1].lower()):
        return s, "", genus, " ".join(words[1:])
    epithet = words[1].lower()
    infra = " ".join(words[2:])
    name = f"{genus} {epithet}" + (f" {infra}" if infra else "")
    return name, binomial(f"{genus} {epithet}") or "", genus, infra


def lift_note(note: str, code: str) -> tuple[str, str, bool, str]:
    """`note` 에서 칸으로 올릴 것을 뽑고 나머지를 돌려준다.

    → (variant, via, primary, note_rest). 한 토막이 칸으로 갔으면 note 에서
    뺀다 — 두 벌이 되면 화면이 같은 말을 두 번 한다.
    """
    variant, via, primary, rest = "", "", False, []
    for tok in [t.strip() for t in note.split(" · ") if t.strip()]:
        if tok in VARIANT_OF:
            variant = VARIANT_OF[tok]
        elif tok in VIA_PHRASES:
            via = VIA_PHRASES[tok]
        elif tok in PRIMARY_MARKS:
            primary = True
        else:
            if ("경유" in tok or "재인용" in tok) and "Warnock" in tok:
                raise SystemExit(f"모르는 경유 문구다 — VIA_PHRASES 에 더한다: {tok!r}")
            rest.append(tok)
    if code in CODE_VARIANT:
        variant = code
    return variant, via, primary, " · ".join(rest)


def label_to_authors_year(label: str) -> tuple[str, int]:
    m = re.search(r"\((\d{4})\)", label)
    if not m:
        raise SystemExit(f"출처 이름에 연도가 없다: {label!r}")
    authors = re.sub(r"\s*\(\d{4}\)\s*", " ", label).strip()
    authors = re.sub(r"\s+", " ", authors)
    return authors, int(m.group(1))


def read_zones(xlsx: Path) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    ws = wb["대(zone)"]
    rows = list(ws.iter_rows(values_only=True))
    head = [str(c) for c in rows[0]]
    want = ["체계", "대(zone)", "상한 연령(Ma)", "하한 연령(Ma)", "상한 정의", "하한 정의", "제안·개정자"]
    if head[:7] != want:
        raise SystemExit(f"「대(zone)」 시트 머리가 다르다: {head}")
    out: list[dict] = []
    seq: dict[str, int] = {}
    for r in rows[1:]:
        if not r or r[0] is None:
            continue
        scheme = ZONE_SCHEME.get(str(r[0]))
        if scheme is None:
            raise SystemExit(f"모르는 대 체계다 — ZONE_SCHEME 에 더한다: {r[0]!r}")
        seq[scheme] = seq.get(scheme, 0) + 1

        def ma(v):
            if v in (None, "", "—"):
                return None
            return float(v)

        out.append({
            "scheme": scheme, "seq": seq[scheme], "name": str(r[1]).strip(),
            "top_ma": ma(r[2]), "base_ma": ma(r[3]),
            "top_def": "" if r[4] in (None, "—") else str(r[4]).strip(),
            "base_def": "" if r[5] in (None, "—") else str(r[5]).strip(),
            "author": "" if r[6] is None else str(r[6]).strip(),
        })
    return out


def convert(doc: dict) -> tuple[list[dict], list[dict], dict[str, set[str]]]:
    refs = []
    for key, s in doc["sources"].items():
        authors, year = label_to_authors_year(s["label"])
        refs.append({
            "key": key, "label": s["label"], "authors": authors, "year": year,
            "citation": s.get("citation") or "", "region": s.get("region") or "",
            "scheme": s.get("scheme") or "", "timescale": s.get("timescale") or "",
            "licence": s.get("licence") or "", "url": s.get("url") or "",
            "basis": s.get("basis") or "",
        })
    keys = {r["key"] for r in refs}

    datums, merged = [], {}
    seq: dict[str, int] = {}
    for r in doc["rows"]:
        src = r["source"]
        if src not in keys:
            raise SystemExit(f"sources 에 없는 출처키다: {src!r}")
        if r["datum"] not in DATUM_KINDS:
            raise SystemExit(f"모르는 기준면이다 — DATUM_KINDS 에 더한다: {r['datum']!r} ({src} {r['species']})")
        conf = CONFIDENCE.get(r["confidence"])
        if conf is None:
            raise SystemExit(f"모르는 신뢰도 문구다: {r['confidence']!r}")
        age, lo, hi = float(r["age"]), float(r["age_min"]), float(r["age_max"])
        if not (lo <= age <= hi):
            raise SystemExit(f"연령이 하한·상한 밖이다: {src} {r['species']} {r['datum']} {lo}–{hi} ↔ {age}")
        name, binom, genus, infra = split_name(r["species"])
        merged.setdefault(name, set()).add(r["species"])
        variant, via, primary, note = lift_note(r.get("note") or "", r.get("code") or "")
        if via and via not in keys:
            raise SystemExit(f"경유 문헌이 sources 에 없다: {via!r}")
        seq[src] = seq.get(src, 0) + 1
        unc = r.get("uncertainty")
        datums.append({
            "reference": src, "via": via, "seq": seq[src],
            "name": name, "name_printed": r["species_printed"] or r["species"],
            "binomial": binom, "genus": genus, "infra": infra,
            "datum": r["datum"], "variant": variant,
            "age": age, "age_min": lo, "age_max": hi,
            "uncertainty": float(unc) if unc not in (None, "") else None,
            "age_text": r.get("age_text") or "",
            "zone": r.get("zone") or "", "code": r.get("code") or "",
            "chron": r.get("chron") or "", "scheme": r.get("scheme") or "",
            "timescale": r.get("timescale") or "", "region": r.get("region") or "",
            "confidence": conf, "primary": primary,
            "mis_stated": r.get("mis_stated") or "",
            "note": note,
        })

    bad = {k: v for k, v in merged.items() if len(v) > 1 and v != MERGE_OK.get(k)}
    if bad:
        for k, v in bad.items():
            print(f"  합쳐진다: {k!r} ← {sorted(v)}", file=sys.stderr)
        raise SystemExit("MERGE_OK 에 없는 합침이다 — 표를 만든 사람이 확인한 뒤 MERGE_OK 에 더한다")
    return refs, datums, merged


def recheck_list(datums: list[dict]) -> list[dict]:
    """반입 뒤 AlgaeBase 에서 다시 확인할 이름 — 도감 판정(`taxon_names.json`)이
    없는 것. 도판이 있는 논문의 종은 P22·P23 에서 이미 확인했으므로 거기
    판정이 있는 이름은 뺀다(사용자 지시, 09-18)."""
    known: set[str] = set()
    if TAXON_NAMES.exists():
        known = {t["binomial"] for t in json.loads(TAXON_NAMES.read_text(encoding="utf-8"))}
    seen: dict[str, dict] = {}
    for d in datums:
        if d["binomial"] and d["binomial"] in known:
            continue
        row = seen.setdefault(d["name"], {"name": d["name"], "binomial": d["binomial"],
                                           "printed": set(), "sources": set()})
        row["printed"].add(d["name_printed"])
        row["sources"].add(d["reference"] + (f"←{d['via']}" if d["via"] else ""))
    return [dict(r, printed=sorted(r["printed"]), sources=sorted(r["sources"]))
            for r in sorted(seen.values(), key=lambda r: r["name"])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--recheck", action="store_true",
                    help="AlgaeBase 재확인 목록을 찍는다 (안 쓴다)")
    args = ap.parse_args()

    xlsx = sorted(SRC_DIR.glob("*.xlsx"))
    if len(xlsx) != 1:
        raise SystemExit(f"{SRC_DIR} 에 xlsx 가 하나여야 한다: {[p.name for p in xlsx]}")
    doc = json.loads(SRC_JSON.read_text(encoding="utf-8"))
    refs, datums, merged = convert(doc)
    zones = read_zones(xlsx[0])

    if args.recheck:
        rows = recheck_list(datums)
        print(f"AlgaeBase 재확인 {len(rows)} 이름 (도감 판정이 있는 것은 뺐다)")
        for r in rows:
            printed = "" if r["printed"] == [r["name"]] else f"  (원문 {' / '.join(r['printed'])})"
            print(f"  {r['name']:44} {', '.join(r['sources'])}{printed}")
        return 0

    by_src: dict[str, int] = {}
    via_n = 0
    for d in datums:
        by_src[d["reference"]] = by_src.get(d["reference"], 0) + 1
        via_n += bool(d["via"])
    names = {d["name"] for d in datums}
    print(f"기준면 {len(datums)}행 · 출처 {len(refs)} · 이름 {len(names)}"
          f"(표기 {len({d['name_printed'] for d in datums})}) · 재인용 {via_n} · 대 {len(zones)}")
    for k, v in sorted(by_src.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24} {v}")
    for k, v in merged.items():
        if len(v) > 1:
            print(f"  합침 {k!r} ← {sorted(v)}")
    no_binom = sorted({d["name"] for d in datums if not d["binomial"]})
    print(f"  이명법 없음(비공식 이름) {len(no_binom)}: {no_binom}")

    if args.dry_run:
        return 0
    out = {
        "generated": dt.date.today().isoformat(),
        "source": {"json": str(SRC_JSON.relative_to(DIADICTION)),
                   "json_sha256": sha256(SRC_JSON),
                   # NAS 의 파일 이름은 CP949 다 — 사람이 읽을 이름으로 적는다
                   "xlsx": xlsx[0].name.encode("utf-8", "surrogateescape").decode("cp949", "replace"),
                   "xlsx_sha256": sha256(xlsx[0])},
        "references": refs, "zones": zones, "datums": datums,
        "mis_reference": doc.get("mis_reference", {}),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"→ {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
