#!/usr/bin/env python3
"""생층서 기준면 JSON 을 DB 에 넣는다 — P28 2단계.

    dbsync.sh import_biodatums.py       # 저장소 → /srv (처음 한 번)
    dbrun.sh  import_biodatums.py
    dbrun.sh  import_biodatums.py --dry-run
    dbrun.sh  import_biodatums.py --src /app/atlas/biodatum/datums.json

1단계(`tools/parse_biodatums.py`)가 NAS 의 표를 `atlas/biodatum/datums.json`
으로 골라 저장소에 넣어 두었다. **이쪽은 NAS 를 안 본다** —
`ops/import_occurrence.py` 와 같은 자리다. JSON 이 이미지에 실려 가므로
**판 먼저, 반입 나중**이다.

## 이 반입이 지키는 것

- **`Reference` 는 `key` 로 upsert 한다** — 지우지 않는다. 출처 열넷의
  열쇠는 표의 `출처키` 를 그대로 쓰고 `REF_KEYS` 에 못 박는다. 벗어나면
  멈춘다 — 표에 새 출처가 생기면 사람이 열쇠를 정한다
- **`Biodatum`·`Biozone` 은 통째로 갈아치운다.** `Atlas`·`TaxonName` 과
  같은 규약 — 원본은 NAS 표이고 이 둘은 사본이다
- **`AtlasEntry` 에 FK 를 매달지 않는다.** `binomial`·`genus` 는 문자열이고
  도감과 맞추는 것은 질의가 한다 (P28 §1.3)
- 한 트랜잭션. 넣고 나서 JSON 과 세어 맞지 않으면 되돌린다
"""
import argparse
import json
import os
import sys
from pathlib import Path

import django

# `ops/check_db.py` 의 머리와 같다 — 컨테이너 안에서는 코드가 `/app` 이라
# `DIARUGA_APP` 을 봐야 한다.
APP = Path(os.environ.get("DIARUGA_APP")
           or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(APP / "web"))
sys.path.append(str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diarugaweb.settings")
django.setup()

from django.db import transaction                                   # noqa: E402

from viewer.models import (BIODATUM_CONFIDENCE, BIODATUM_KINDS,     # noqa: E402
                           Biodatum, Biozone, Reference)

SRC = APP / "atlas" / "biodatum" / "datums.json"

# **여기서만 열쇠를 정한다.** 표의 `출처키` 그대로다 — `import_occurrence.py`
# 의 `REF_KEY` 와 같은 자리. 표에 없던 출처가 오면 멈춘다.
REF_KEYS = {
    "warnock2025", "cody2008", "crampton2016", "yanagisawa1998", "iodp346",
    "censarek2002", "censarek704B", "zielinski2002b", "winter_iwai2002",
    "gersonde_barcena1998", "zielinski_gersonde2002", "kato2024", "winter2012",
    "fujiwara2008",
    "gersonde1990",     # Gersonde & Burckle (1990) ODP Leg 113 — 209
}

KINDS = {k for k, _ in BIODATUM_KINDS}
CONF = {k for k, _ in BIODATUM_CONFIDENCE}


def load(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    for k in ("references", "zones", "datums"):
        if k not in doc:
            raise SystemExit(f"{path.name}: 기준면 JSON 이 아니다 ({k} 가 없다)")
    return doc


def put(doc: dict) -> tuple[int, int, int]:
    refs = {}
    for r in doc["references"]:
        key = r["key"]
        if key not in REF_KEYS:
            raise SystemExit(
                f"REF_KEYS 에 없는 출처다: {key!r} — tools/parse_biodatums.py 가 못 보던 "
                f"출처를 냈다. 열쇠를 정해 이 스크립트의 REF_KEYS 에 추가한다.")
        note = " · ".join(x for x in (
            f"확보 경로: {r['basis']}" if r.get("basis") else "",
            f"이용 조건: {r['licence']}" if r.get("licence") else "") if x)
        ref, _ = Reference.objects.update_or_create(
            key=key,
            defaults={"authors": r["authors"][:64], "year": int(r["year"]),
                      "kind": "paper", "title": r.get("citation") or "",
                      "url": r.get("url") or "", "note": note})
        refs[key] = ref

    Biodatum.objects.all().delete()
    Biozone.objects.all().delete()

    rows = []
    for d in doc["datums"]:
        ref = refs.get(d["reference"])
        if ref is None:
            raise SystemExit(f"references[] 에 없는 출처다: {d['reference']!r} (#{d['seq']} {d['name']})")
        if d["via"] and d["via"] not in refs:
            raise SystemExit(f"경유 문헌이 references[] 에 없다: {d['via']!r}")
        if d["datum"] not in KINDS:
            raise SystemExit(f"모르는 기준면이다: {d['datum']!r} ({d['reference']} #{d['seq']})")
        if d["confidence"] not in CONF:
            raise SystemExit(f"모르는 신뢰도다: {d['confidence']!r} ({d['reference']} #{d['seq']})")
        rows.append(Biodatum(
            reference=ref, via=d["via"], seq=d["seq"],
            name=d["name"], name_printed=d["name_printed"],
            binomial=d["binomial"], genus=d["genus"], infra=d["infra"],
            datum=d["datum"], variant=d["variant"],
            age=d["age"], age_min=d["age_min"], age_max=d["age_max"],
            uncertainty=d["uncertainty"], age_text=d["age_text"],
            zone=d["zone"], code=d["code"], chron=d["chron"],
            scheme=d["scheme"], timescale=d["timescale"], region=d["region"],
            confidence=d["confidence"], primary=bool(d["primary"]),
            mis_stated=d["mis_stated"], note=d["note"]))
    Biodatum.objects.bulk_create(rows)

    Biozone.objects.bulk_create([
        Biozone(scheme=z["scheme"], seq=z["seq"], name=z["name"],
                top_ma=z["top_ma"], base_ma=z["base_ma"],
                top_def=z["top_def"], base_def=z["base_def"], author=z["author"])
        for z in doc["zones"]])
    return len(refs), len(rows), len(doc["zones"])


def verify(doc: dict) -> list[str]:
    """넣은 것이 JSON 과 같은가."""
    bad = []
    want, got = len(doc["datums"]), Biodatum.objects.count()
    if want != got:
        bad.append(f"기준면: JSON 은 {want} 인데 DB 는 {got}")
    want_n = {d["name"] for d in doc["datums"]}
    got_n = set(Biodatum.objects.values_list("name", flat=True))
    if want_n != got_n:
        bad.append(f"이름: {sorted(want_n ^ got_n)[:5]} 가 어긋난다")
    wz, gz = len(doc["zones"]), Biozone.objects.count()
    if wz != gz:
        bad.append(f"대: JSON 은 {wz} 인데 DB 는 {gz}")
    return bad


class _Rollback(Exception):
    """`transaction.atomic` 을 되돌리는 유일한 길은 예외다."""

    def __init__(self, bad):
        self.bad = bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC, help="기준면 JSON")
    ap.add_argument("--dry-run", action="store_true", help="넣고 되돌린다")
    args = ap.parse_args()

    if not args.src.exists():
        print(f"기준면 JSON 이 없다: {args.src}\n"
              f"  1단계를 먼저 돌린다 — `python tools/parse_biodatums.py` (호스트에서)",
              file=sys.stderr)
        return 2
    doc = load(args.src)
    try:
        with transaction.atomic():
            nr, nd, nz = put(doc)
            bad = verify(doc)
            if bad or args.dry_run:
                raise _Rollback(bad)
    except _Rollback as r:
        if r.bad:
            print(f"\n{args.src.name} — 되돌렸다")
            for b in r.bad:
                print(f"  ✗ {b}")
            print("\n반입이 어긋났다.", file=sys.stderr)
            return 1
        print(f"\n{args.src.name} — 문헌 {nr} · 기준면 {nd} · 대 {nz} (되돌렸다)")
        return 0
    print(f"\n{args.src.name} — 문헌 {nr} · 기준면 {nd} · 대 {nz}")
    print(f"  ✓ JSON 과 맞는다 (원본 {doc.get('source', {}).get('json', '?')} "
          f"sha256 {doc.get('source', {}).get('json_sha256', '?')[:12]}…)")
    print("이제 `check_db.py` 의 13번(기준면)을 본다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
