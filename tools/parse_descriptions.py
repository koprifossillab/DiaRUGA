#!/usr/bin/env python3
"""한국 도감 본문에서 **기재문**을 항목별로 가른다 (257).

    python tools/parse_descriptions.py              # 뽑아서 json 을 낸다
    python tools/parse_descriptions.py --dry-run    # 아무것도 안 쓰고 수만 센다
    python tools/parse_descriptions.py --source ocr # OCR 산출(Diadiction/ocr/)에서

색인(`md/korean_flora_diatom_index.md`)은 이름·도판·생태·분포만 들었고
**형태 기재는 한 번도 안 뽑았다.** 본문은 항목마다

    200. pl. 27   Coscinodiscus curvatulus GRUNOW
                                              <체모양원반 과>
    세포는 직경이 40~100이고 …                       ← 기재문
    생태 : …
    분포 : … 채집되었다.

이고, 항목과 항목 사이에 **속의 기재·검색표**가 끼어 있다.

## 버리는 것이 없다 — 그것을 수로 확인한다

읽은 줄은 전부 어느 한 자리에 간다:

| 자리 | 무엇 |
|---|---|
| `entries[].description` | 표제 줄과 `생태` 사이 |
| `entries[].ecology` · `distribution` | 색인이 이미 든 것과 같은 자리 (대조용) |
| `entries[].after` | `채집되었다` 뒤, 다음 표제 앞 — 다음 속의 기재·검색표 |
| `front` | 첫 항목 앞 (범례·목차·과의 기재) |
| `plates` | 도판 목록 쪽 (`Plate NN` 이 든 쪽) |
| `furniture` | 쪽 머리·꼬리 |

끝에 **들어온 글자 수 = 놓인 글자 수**를 대조하고 어긋나면 멈춘다.

## 두 원본

| `--source` | 읽는 것 | 덮는 항목 |
|---|---|---|
| `text` (기본) | PDF 텍스트 레이어 (`pdftotext -layout`) | #169–480 (PDF p.46–190) |
| `ocr` | `Diadiction/ocr/korean_flora_diatom/pNNNN.html` | 전부 (P21 의 OCR 서버) |

**둘은 서로를 대신하지 않는다.** 텍스트 레이어는 한글이 성하고 괄호 속 한자와
`μ` 가 깨져 있고, OCR 은 `μ` 와 한자를 읽지만 학명을 그럴듯하게 틀린다(P21 2절).
그래서 **둘 다 남기고** 같은 항목을 나란히 놓는다.

`*_raw` 는 원본이 낸 그대로이고, `_raw` 가 없는 칸이 읽는 값이다 — 줄바꿈을
잇고 공백을 한 칸으로 줄이는 것까지만 한다. **깨진 한자 괄호는 안 걷는다**
(걷으면 `(GRUN.)` 같은 저자 괄호와 가르는 규칙이 하나 더 생기고, 그 규칙이
틀리면 조용히 자료가 준다).
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION  # noqa: E402

PDF = DIADICTION / "origin/korean_flora_diatom.pdf"
OCR_DIR = DIADICTION / "ocr/korean_flora_diatom"
INDEX = Path(__file__).resolve().parent.parent / "atlas/korean.json"
OUT_DIR = DIADICTION / "outputs/descriptions"

FURNITURE = [
    re.compile(r'^\s*\d*\s*황색편\s*모조?\s*식물\s*문\s*\d*\s*$'),
    re.compile(r'^\s*\d*\s*한국\s*동\s*식\s*물\s*도\s*감.*$'),
]
PLATE_PAGE = re.compile(r'^\s*Plate\s+\d+\s*$', re.M)
# 번호 뒤 마침표가 빠진 자리가 있다 (#177). `pl.` 이 붙어 있어 검색표 줄과 안 섞인다
HEAD = re.compile(r'^\s*(\d{3})\.?\s*p[l!1][.,]?\s*(\d+)\s+(\S.*)$')
ECO = re.compile(r'^\s*생\s*태\s*[:：;]')
DIST = re.compile(r'^\s*[분문][포토]\s*[:：;]')
END = re.compile(r'채\s*집\s*되\s*었\s*다\s*[.,]?')
FAMILY = re.compile(r'^\s*[<〈＜《]\s*[^<>]{2,20}\s*과\s*[>〉＞》]?\s*$')


def pages_text() -> list[tuple[int, list[str]]]:
    n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(
        ["pdfinfo", str(PDF)], capture_output=True, text=True, check=True).stdout).group(1))
    out = []
    for p in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", str(PDF), "-"],
                           capture_output=True, text=True, check=True).stdout
        out.append((p, t.replace("\f", "").split("\n")))
    return out


_BLOCK = re.compile(r'</(?:p|div|li|h\d|tr|caption|table)\s*>|<br\s*/?>', re.I)
_TAG = re.compile(r'<[^>]+>')


def pages_ocr() -> list[tuple[int, list[str]]]:
    out = []
    for f in sorted(OCR_DIR.glob("p[0-9][0-9][0-9][0-9].html")):
        s = _BLOCK.sub("\n", f.read_text(encoding="utf-8"))
        s = htmllib.unescape(_TAG.sub("", s))
        out.append((int(f.stem[1:]), s.split("\n")))
    return out


def squeeze(lines: list[str]) -> str:
    return re.sub(r'\s+', ' ', ' '.join(lines)).strip()


def parse(pages: list[tuple[int, list[str]]]) -> dict:
    front, plates, furniture, entries = [], [], [], []
    cur, part = None, None
    n_in = n_out = 0

    def put(bucket: list, page: int, line: str):
        nonlocal n_out
        n_out += len(line.strip())
        bucket.append((page, line))

    for page, lines in pages:
        body = "\n".join(lines)
        n_in += sum(len(x.strip()) for x in lines)
        if PLATE_PAGE.search(body):
            for x in lines:
                if x.strip():
                    put(plates, page, x)
            continue
        for x in lines:
            if not x.strip():
                continue
            if any(r.match(x) for r in FURNITURE):
                put(furniture, page, x)
                continue
            m = HEAD.match(x)
            if m:
                cur = {"item_no": m.group(1), "plate": int(m.group(2)),
                       "name_raw": m.group(3).strip(), "pdf_page": page,
                       "name_more": [], "family": [], "description": [], "ecology": [],
                       "distribution": [], "after": []}
                entries.append(cur)
                part = "description"
                n_out += len(x.strip())
                cur["head_raw"] = x.strip()
                continue
            if cur is None:
                put(front, page, x)
                continue
            # 과 이름표는 표제 바로 아래에 온다. 그 사이에 낀 한두 줄은 **이름이
            # 길어 넘어온 줄**이다 (`subsp. subarctica O. F. MÜLLER`) — 기재가 아니다
            if part == "description" and not cur["family"] and FAMILY.match(x) \
                    and len(cur["description"]) <= 2:
                cur["name_more"].extend(cur["description"])
                cur["description"].clear()
                put(cur["family"], page, x)
                continue
            if part in ("description", "ecology") and ECO.match(x):
                part = "ecology"
            elif part in ("description", "ecology") and DIST.match(x):
                part = "distribution"
            put(cur[part], page, x)
            if part == "distribution" and END.search(x):
                part = "after"

    if n_in != n_out:
        raise SystemExit(f"글자 수가 어긋난다 — 들어온 것 {n_in} · 놓인 것 {n_out}")

    def flat(b):
        return [x for _, x in b]

    def pg(b):
        return sorted({p for p, _ in b})

    out_entries = []
    for e in entries:
        o = {"item_no": e["item_no"], "plate": e["plate"], "pdf_page": e["pdf_page"],
             "head_raw": e["head_raw"], "name_raw": squeeze([e["name_raw"]] + flat(e["name_more"])),
             "family_raw": squeeze(flat(e["family"]))}
        for k in ("description", "ecology", "distribution", "after"):
            o[k] = squeeze(flat(e[k]))
            o[k + "_raw"] = "\n".join(x.rstrip() for x in flat(e[k]))
            o[k + "_pages"] = pg(e[k])
        out_entries.append(o)
    return {
        "chars_in": n_in,
        "entries": out_entries,
        "front": [{"pdf_page": p, "line": x.rstrip()} for p, x in front],
        "plates": [{"pdf_page": p, "line": x.rstrip()} for p, x in plates],
        "furniture": [{"pdf_page": p, "line": x.rstrip()} for p, x in furniture],
    }


def report(d: dict, index: dict) -> None:
    want = [e["item_no"] for e in index["entries"]]
    got = [e["item_no"] for e in d["entries"]]
    seen = set()
    dup = [x for x in got if x in seen or seen.add(x)]
    es = d["entries"]
    print(f"표제 {len(got)}개 (색인 {len(want)}) · 겹침 {len(dup)} · "
          f"색인에 없는 번호 {len(set(got) - set(want))} · 못 찾은 번호 {len(set(want) - set(got))}")
    print(f"기재문이 있는 것 {sum(1 for e in es if e['description'])} · "
          f"생태 {sum(1 for e in es if e['ecology'])} · 분포 {sum(1 for e in es if e['distribution'])} · "
          f"뒤에 붙은 글 {sum(1 for e in es if e['after'])}")
    ln = sorted(len(e["description"]) for e in es) or [0]
    print(f"기재문 길이 — 가운데 {ln[len(ln) // 2]}자 · 가장 긴 것 {ln[-1]}자 · 빈 것 {ln.count(0)}")
    print(f"첫 항목 앞 {len(d['front'])}줄 · 도판 쪽 {len(d['plates'])}줄 · 쪽 머리 {len(d['furniture'])}줄 "
          f"· 글자 {d['chars_in']} (전부 놓였다)")
    if dup:
        print("  겹친 번호:", " ".join(dup[:30]))
    miss = sorted(set(want) - set(got), key=int)
    if miss:
        print("  못 찾은 번호:", " ".join(miss[:60]), "…" if len(miss) > 60 else "")
    odd = sorted(set(got) - set(want), key=int)
    if odd:
        print("  색인에 없는 번호:", " ".join(odd[:30]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("text", "ocr"), default="text")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pages = pages_text() if args.source == "text" else pages_ocr()
    if not pages:
        raise SystemExit(f"읽을 쪽이 없다 ({args.source})")
    d = parse(pages)
    d = {"atlas": "korean", "source": args.source, "pages_read": len(pages), **d}
    report(d, json.loads(INDEX.read_text(encoding="utf-8")))
    if not args.dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"korean_{args.source}.json"
        out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
