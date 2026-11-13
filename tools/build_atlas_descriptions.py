#!/usr/bin/env python3
"""가른 기재문을 반입용 사본 `atlas/descriptions/<도감>.json` 으로 옮긴다 (257).

    python tools/build_atlas_descriptions.py korean
    python tools/build_atlas_descriptions.py schmidt
    python tools/build_atlas_descriptions.py papers
    python tools/build_atlas_descriptions.py all --dry-run

읽는 것은 NAS 의 `Diadiction/outputs/descriptions/` 에 있는 가르기 산출이고
(한국 `korean_merged.json` · Schmidt `schmidt_ocr.json` · 논문 `papers/<코드>.json`),
내는 것은 저장소의 `atlas/descriptions/<색인 파일 이름>.json` 이다 — 이미지에
실려 가 `ops/import_atlas.py` 가 항목의 `extra` 에 얹는다. **파일 이름이 색인
파일 이름과 같아야 짝이 된다**(`atlas/1936-skvortzov.json` ↔
`atlas/descriptions/1936-skvortzov.json`).

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

**Schmidt·논문은 OCR(`description`)만 싣는다.** Schmidt 는 텍스트 레이어가
없고, 논문 중 텍스트 레이어가 있는 1985 는 두 단 조판에 그림 캡션이 끼어
`pdftotext` 의 줄이 단을 넘나든다 — 항목 경계를 그 위에서 다시 잡으면 남의
글이 섞인다. 쓰는 규칙은 아래 `schmidt()`·`papers()` 머리에 있다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
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


# ── Schmidt ──────────────────────────────────────────────────────────────
#
# Schmidt 해설은 "그림 — 이름 — 산지 — 짧은 비고" 한 줄씩이다(형태 기재라 할
# 글은 거의 없다 — REPORT_schmidt). 색인 배치(권, 해설 쪽, 그림 번호)와 해설 줄의
# 그림 번호가 겹치는 것(`fig_matched`)만 싣는다. 쪽만 맞는 것(`page_only`)은 그
# 쪽의 어느 줄인지 모르고, 번호가 안 맞는 것(`fig_unmatched`)·해설 쪽이 없는 것
# (`no_page`)은 붙일 줄이 없다. **번호가 맞아도 색인 종소명이 그 줄에 없으면 안
# 싣는다**(OCR 철자 · `—` 표시 · 번호 우연 일치를 가르지 못했다) — 목록으로 남긴다.

SEP = " ／ "


def _schmidt_figs():
    from parse_descriptions_schmidt import parse_index_figs   # 같은 펼침 규칙을 쓴다
    return parse_index_figs


def schmidt() -> list[tuple[str, dict]]:
    parse_index_figs = _schmidt_figs()
    index = json.loads((ROOT / "atlas/schmidt.json").read_text(encoding="utf-8"))
    ocr = json.loads((SRC / "schmidt_ocr.json").read_text(encoding="utf-8"))
    pairing = json.loads((SRC / "schmidt_index_pairing.json").read_text(encoding="utf-8"))
    want_state = {(e["seq"], i): p["state"] for e in pairing["entries"]
                  for i, p in enumerate(e["placements"])}
    by_page: dict[tuple[str, int], list[dict]] = {}
    sec_pages = set()
    for b in ocr["bands"]:
        for sec in b["sections"]:
            sec_pages.update((b["band"], pg) for pg in sec["pdf_pages"])
            for it in sec["items"]:
                if it["kind"] == "entry":
                    by_page.setdefault((b["band"], it["pdf_page"]), []).append(it)

    out, skipped = [], []
    states = Counter()
    for e in index["entries"]:
        parts = []
        for i, p in enumerate(e["placements"]):
            key = (p["volume"], p["pdf_page"])
            figs = parse_index_figs(p.get("figures"))
            if key not in sec_pages:
                state, hit = "no_page", []
            elif figs is None:
                state, hit = "page_only", []
            else:
                hit = [it for it in by_page.get(key, [])
                       if figs & (set(it["figs"]) | set(it.get("figs_inline", [])))]
                state = "fig_matched" if hit else "fig_unmatched"
            # 가르기 작업자의 짝과 같은 규칙인가 — 어긋나면 사본을 안 낸다
            if want_state.get((e["seq"], i)) != state:
                raise SystemExit(f"schmidt seq {e['seq']} 자리 {i}: 짝이 보고서와 다르다 "
                                 f"({state} ↔ {want_state.get((e['seq'], i))})")
            states[state] += 1
            if state != "fig_matched":
                continue
            line = " ".join(it["text"] for it in hit)
            ep = (e["binomial"] or e["name"]).split()[-1].lower()
            if ep not in line.lower():
                states["epithet_missing"] += 1
                skipped.append({"seq": e["seq"], "name": e["name"], "volume": p["volume"],
                                "plate": p["plate"], "figures": p["figures"],
                                "pdf_page": p["pdf_page"], "line": line})
                continue
            parts.append((p, line))
        if not parts:
            continue
        if len(e["placements"]) > 1:
            text = SEP.join(f"Taf. {p['plate']}, Fig. {p['figures']}: {ln}" for p, ln in parts)
        else:
            text = parts[0][1]
        out.append({"seq": e["seq"], "name": e["name"], "description": text,
                    "description_source": "OCR (Schmidt 해설면 · 그림 번호로 짝 지은 줄)"})
    print(f"schmidt — 색인 {len(index['entries'])} · 기재문 {len(out)} · 자리 {dict(states)} "
          f"· 종소명이 줄에 없어 안 얹은 자리 {len(skipped)}")
    doc = {"atlas": "schmidt",
           "source": "Diadiction/outputs/descriptions/schmidt_ocr.json "
                     "(tools/parse_descriptions_schmidt.py)",
           "entries": out}
    return [("schmidt", doc, {"skipped_epithet_missing": skipped, "states": dict(states)})]


# ── 논문 ──────────────────────────────────────────────────────────────────
#
# 분류군별 **기재문이 있는 논문만** 싣는다 — 가르기 산출의 항목 종류가
# `description`(1936·1985·1993 챈틀)·`flora_ref`(1992 · 인용 + Remarks + Ecology)인
# 것이다. `floral_list`(1990·1998·Censarek·Zielinski)는 이름과 인용뿐이라 기재가
# 아니다 — 파일을 안 만든다. 짝은 **이름이 정확히 맞는 것만**: 속 + 종소명 +
# 종하 등급과 그 이름(대소문자·공백·저자명은 안 본다). 한쪽에서라도 같은 열쇠가
# 둘이면 어느 것인지 모르므로 안 얹는다 — 다만 **색인** 쪽만 겹치고(같은 종이
# 도판 캡션 꼬리·저자 표기만 달리 두 번 실린 행) 논문 쪽 항목이 하나면 어느
# 기재인지는 안 갈려서 그 행들 모두에 얹는다. 철자가 한 글자라도 다르면 안 얹는다.

PAPERS = {   # 가르기 산출 코드 → 색인 파일 이름
    "1936_skvortzov_ampen_neogene": "1936-skvortzov",
    "1985_akiba_yanagisawa_dsdp87_zonal_markers": "1985-akiba-yanagisawa",
    "1992_lee_galmal_quaternary_flora": "1992-lee-galmal",
    "1993_lee_chaetoceros_yeonil": "1993-lee-chaetoceros",
}
DESC_KINDS = {"description", "flora_ref"}
RANKS = {"var": "var", "fo": "f", "f": "f", "forma": "f", "subsp": "subsp",
         "ssp": "subsp", "status": "status"}
_W = re.compile(r"[^\w]+")


def name_key(name: str) -> str | None:
    """`Eunotia monodon Ehr. var. koreana var. nov.?` → `eunotia monodon var koreana`.

    저자명은 등급 표지 사이에 끼어 있어도 건너뛴다 — 등급 표지(var. · fo. ·
    subsp. · status) 바로 뒤 낱말만 이름으로 본다. `nov` 는 이름이 아니다.
    """
    toks = [t for t in (_W.sub("", x).lower() for x in name.replace("(", " (").split()) if t]
    raw = name.split()
    if len(toks) < 2 or not raw[0][:1].isupper():
        return None
    out = [toks[0]]
    j = 1
    if toks[j] in ("cf", "aff") and j + 1 < len(toks):
        out.append(toks[j])
        j += 1
    out.append(toks[j])
    if toks[j] in ("sp", "spp") and j + 1 < len(toks) and re.fullmatch(r"[a-z0-9]{1,2}", toks[j + 1]) \
            and raw[min(j + 1, len(raw) - 1)].rstrip(".").isalnum() \
            and (raw[min(j + 1, len(raw) - 1)][:1].isupper() or raw[min(j + 1, len(raw) - 1)][:1].isdigit()):
        out.append(toks[j + 1])
        return " ".join(out)
    k = j + 1
    while k < len(toks):
        r = RANKS.get(toks[k])
        if r and k + 1 < len(toks) and toks[k + 1] not in ("nov", "n") and toks[k + 1].isalpha():
            out += [r, toks[k + 1]]
            k += 2
            continue
        k += 1
    return " ".join(out)


def _entry_text(e: dict) -> str:
    parts = [h["text_raw"] for h in e.get("head_lines", [])] + [f["text"] for f in e["fields"]]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def papers() -> list[tuple[str, dict]]:
    res = []
    for code, stem in PAPERS.items():
        src = json.loads((SRC / "papers" / f"{code}.json").read_text(encoding="utf-8"))
        index = json.loads((ROOT / "atlas" / f"{stem}.json").read_text(encoding="utf-8"))
        ents = [e for e in src["entries"] if e["kind"] in DESC_KINDS]
        ikeys = Counter(name_key(e["name"]) for e in index["entries"])
        pkeys = Counter(name_key(e["name"]) for e in ents)
        by_key = {name_key(e["name"]): e for e in ents}
        out, notes = [], {"index_no_key": [], "index_dup_attached": [], "paper_dup_key": [],
                          "index_not_in_paper": [], "paper_not_in_index": []}
        used = set()
        for e in index["entries"]:
            k = name_key(e["name"])
            if k is None:
                notes["index_no_key"].append(e["name"])
                continue
            if k not in pkeys:
                notes["index_not_in_paper"].append(e["name"])
                continue
            if pkeys[k] > 1:
                notes["paper_dup_key"].append(e["name"])
                continue
            pe = by_key[k]
            text = _entry_text(pe)
            if not text:
                continue
            used.add(k)
            if ikeys[k] > 1:
                # 색인에 같은 이름이 둘 이상(도판 캡션 꼬리·저자 표기만 다른 행)이다.
                # 논문 쪽 항목이 하나뿐이라 어느 기재인지는 안 갈린다 — 둘 다에 얹고 적어 둔다
                notes["index_dup_attached"].append(e["name"])
            out.append({"seq": e["seq"], "name": e["name"], "description": text,
                        "description_source": f"OCR ({code} · 항목 {pe['id'].split('#')[-1]}"
                                              f" · PDF p.{'–'.join(map(str, sorted({pe['pdf_pages'][0], pe['pdf_pages'][-1]})))})"})
        notes["paper_not_in_index"] = [e["name"] for e in ents if name_key(e["name"]) not in used]
        print(f"{stem} — 색인 {len(index['entries'])} · 가른 기재 {len(ents)} · 얹음 {len(out)} · "
              + " · ".join(f"{k} {len(v)}" for k, v in notes.items()))
        doc = {"atlas": stem,
               "source": f"Diadiction/outputs/descriptions/papers/{code}.json "
                         "(tools/parse_descriptions_papers.py)",
               "entries": out}
        res.append((stem, doc, notes))
    return res


def korean_builder() -> list[tuple[str, dict]]:
    return [("korean", korean(), None)]


BUILDERS = {"korean": korean_builder, "schmidt": schmidt, "papers": papers}
NOTES = SRC / "build_notes"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("atlas", choices=sorted(BUILDERS) + ["all"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    names = sorted(BUILDERS) if args.atlas == "all" else [args.atlas]
    for name in names:
        for stem, doc, notes in BUILDERS[name]():
            if args.dry_run:
                continue
            if not doc["entries"]:
                print(f"  {stem}: 얹을 것이 없어 파일을 안 만든다")
                continue
            OUT.mkdir(parents=True, exist_ok=True)
            p = OUT / f"{stem}.json"
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"→ {p}")
            if notes:
                # 안 얹은 것의 목록 — 저장소 밖(NAS)에 둔다. atlas/descriptions 는 반입기가 훑는다
                NOTES.mkdir(parents=True, exist_ok=True)
                q = NOTES / f"{stem}.json"
                q.write_text(json.dumps(notes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"  안 얹은 것 → {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
