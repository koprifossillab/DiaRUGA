#!/usr/bin/env python3
"""가른 기재문을 반입용 사본 `atlas/descriptions/<도감>.json` 으로 옮긴다 (257).

    python tools/build_atlas_descriptions.py korean
    python tools/build_atlas_descriptions.py korean --dry-run

읽는 것은 NAS 의 `Diadiction/outputs/descriptions/korean_merged.json`
(`tools/merge_descriptions.py` 의 산출)이고, 내는 것은 저장소의
`atlas/descriptions/korean.json` 이다 — 이미지에 실려 가 `ops/import_atlas.py`
가 항목의 `extra` 에 얹는다.

**`atlas/*.json` 옆에 두지 않고 한 단 아래에 둔다** — 반입기가 그 디렉토리를
`glob("*.json")` 으로 훑는다(`atlas/occurrence/` 와 같은 이유).

## 싣는 것과 안 싣는 것

| 칸 | 무엇 |
|---|---|
| `description` | OCR 이 읽은 기재문 (`μ`·한자가 살아 있다 · 한글 오독이 있다) |
| `description_text` | PDF 텍스트 레이어의 기재문 (#169–480 · 한글이 낫고 `μ`·한자가 깨졌다) |

**어느 쪽도 고쳐 쓰지 않고 둘을 섞지도 않는다.** 섞는 규칙이 틀리면 원문에
없는 문장이 생긴다. 생태·분포는 색인이 이미 들고 있어 안 싣는다. 항목 사이의
과·목 기재와 검색표는 NAS 의 `korean_merged.json` 에 남아 있고 여기에는 안
싣는다 — 항목에 붙는 글이 아니다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = DIADICTION / "outputs/descriptions"
OUT = ROOT / "atlas/descriptions"


def korean() -> dict:
    index = json.loads((ROOT / "atlas/korean.json").read_text(encoding="utf-8"))
    merged = json.loads((SRC / "korean_merged.json").read_text(encoding="utf-8"))
    by_no = {e["item_no"]: e for e in index["entries"]}
    out, skipped = [], []
    for it in merged["items"]:
        e = by_no[it["item_no"]]
        ocr = ((it.get("ocr") or {}).get("description") or "").strip()
        text = ((it.get("text") or {}).get("description") or "").strip()
        if not ocr and not text:
            skipped.append(it["item_no"])
            continue
        d = {"seq": e["seq"], "item_no": e["item_no"], "name": e["name"]}
        if ocr:
            d["description"] = ocr
        if text:
            d["description_text"] = text
        d["description_source"] = " · ".join(
            x for x, on in (("OCR", ocr), ("PDF 텍스트 레이어", text)) if on)
        out.append(d)
    print(f"korean — 색인 {len(index['entries'])} · 기재문 {len(out)} "
          f"(OCR {sum('description' in d for d in out)} · "
          f"텍스트 레이어 {sum('description_text' in d for d in out)}) · "
          f"없는 번호 {' '.join(skipped) or '없음'}")
    return {"atlas": "korean",
            "source": "Diadiction/outputs/descriptions/korean_merged.json",
            "entries": out}


BUILDERS = {"korean": korean}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("atlas", choices=sorted(BUILDERS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    doc = BUILDERS[args.atlas]()
    if not args.dry_run:
        OUT.mkdir(parents=True, exist_ok=True)
        p = OUT / f"{args.atlas}.json"
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
