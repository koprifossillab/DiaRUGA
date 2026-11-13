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
# OCR — `p. 22`(l 이 빠짐) · 번호 뒤 `pl.` 자체가 없는 표제(`263. Rhizosolenia …`)도 있다.
# 뒤엣것은 도판 쪽의 캡션과 모양이 같아서 **앞 항목 번호 + 1 일 때만** 표제로 본다
HEAD_OCR = re.compile(r'^\s*(\d{3})\.?\s*p[l!1I]?[.,]?\s*(\d+)\s+(\S.*)$')
HEAD_NOPL = re.compile(r'^\s*(\d{3})\.\s+([A-Z]\S*\s+\S.*)$')
ECO = re.compile(r'^\s*생\s*태\s*[:：;]')
DIST = re.compile(r'^\s*[분문][포토]\s*[:：;]')
END = re.compile(r'채\s*집\s*되\s*었\s*다\s*[.,]?')
FAMILY = re.compile(r'^\s*[<〈＜《⟨]\s*[^<>]{2,20}\s*과\s*[>〉＞》⟩]?\s*$')
FAMILY_OCR = re.compile(r'^\s*[<〈＜《⟨〔\[［]\s*[^<>〔〕\[\]]{2,20}\s*과\s*[>〉＞》⟩〕\]］]?\s*$')
# OCR 쪽 — 라벨이 `〔생태〕:` `[분포] :` 로 대괄호에 싸여 있고, 글자는 곧잘 깨진다
# (`[ầ錄]` · `【 Cree】` · `☆리썬 :` · `궤태:` · `〔문포]:`). 그래서 **글자가 아니라 자리**로
# 본다: 기재문 다음의 첫 라벨은 생태, 그 다음은 분포. 분포는 글자가 읽히면 그것으로도 안다
_SYM = '〔\\[［【☆※★◆■○◎●□▮▯▪◇'
_C = r'〕\]］】'
_BR = (rf'(?:[{_SYM}](?!\s*色\s*圖)(?![^{_C}\n]{{0,14}}과\s*[{_C}])\s*[^{_C}:：;\n]{{0,14}}?\s*(?:[{_C}]\s*[{_SYM}]?\s*[:：;]?|[{_SYM}]?\s*[:：;])'
       rf'|[^\s:：;\n]{{1,8}}[{_C}]\s*[:：;]'          # 여는 괄호를 못 읽은 것 (`.mov] :`)
       r'|\(\s*[^()\n]{1,6}\s*\)\s*[:：;])')
_PLAIN = r'[^\s.:：;()\[\]〔〕]{1,6}(?:\s[^\s.:：;()\[\]〔〕]{1,6})?\s*[:：;]'
OCR_LABEL = re.compile(rf'^\s*({_BR}|{_PLAIN})')
OCR_DIST = re.compile(r'[분문][포토초]')
OCR_ECO = re.compile(r'생\s*태')
# 라벨이 줄 한가운데 있을 수 있다 (`… 한다. 생태: 이 종은 …`) — 거기서 끊는다.
# 기호 없는 한글 라벨은 앞 문장이 마침표로 끝났을 때만 (`크기: ` 같은 본문을 안 자르려고)
OCR_INLINE = re.compile(rf'(?:(?<=\S)\s+(?={_BR})|(?<=\S)\s+(?=(?:생\s*태|[분문][포토초])\s*[:：;])|(?<=[.)])\s+(?={_PLAIN}))')
COLOR_PLATE = re.compile(r'^\s*[〔\[]\s*色\s*圖\s*[〕\]]\s*$')


class Furn(str):
    """OCR 의 Page-Header·Page-Footer 칸에서 온 줄 — 쪽 머리·꼬리다."""


def pages_text() -> list[tuple[int, list[str]]]:
    n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(
        ["pdfinfo", str(PDF)], capture_output=True, text=True, check=True).stdout).group(1))
    out = []
    for p in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", str(PDF), "-"],
                           capture_output=True, text=True, check=True).stdout
        out.append((p, t.replace("\f", "").split("\n")))
    return out


_BLOCK = re.compile(r'</(?:p|div|li|h\d|tr|caption|table|ul|ol)\s*>|<br\s*/?>', re.I)
_TAG = re.compile(r'<[^>]+>')
_MATH = re.compile(r'<math>(.*?)</math>', re.S)
# 서버가 숫자·단위를 LaTeX 로 적는다 (`10\text{ }\mu`, `5\sim 7`, `110^{\circ}`) — 이 말뜻만 푼다
_TEX = [(re.compile(r'\\text\{([^{}]*)\}'), r'\1'), (re.compile(r'\^\{\\circ\}|\\circ'), '°'),
        (re.compile(r'\\mu(?![a-z])'), 'μ'), (re.compile(r'\\sim(?![a-z])'), '~'),
        (re.compile(r'\\langle(?![a-z])'), '〈'), (re.compile(r'\\rangle(?![a-z])'), '〉'),
        (re.compile(r'\\[ ,;]'), ' ')]


def tex_plain(m: re.Match) -> str:
    t = m.group(1)
    for rx, rep in _TEX:
        t = rx.sub(rep, t)
    return t
_DIV = re.compile(r'<div\b[^>]*data-label="([^"]*)"[^>]*>(.*?)</div>(?=\s*(?:<div\b|$))', re.S)
_HDR = ("Page-Header", "Page-Footer")


def ocr_lines(html: str) -> list[str]:
    """걷은 .html 한 쪽 → 줄. 칸(`div`)마다 끊고, 머리·꼬리 칸은 `Furn` 으로 표시한다.

    바꾸는 것은 둘뿐이다: `<math>` 속 LaTeX 를 글자로 푼다(`\\mu`→`μ` 등 `_TEX`), 태그를 뗀다(+HTML 엔티티)."""
    out: list[str] = []
    pos = 0
    for m in _DIV.finditer(html):
        label, inner = m.group(1), _MATH.sub(tex_plain, m.group(2))
        inner = htmllib.unescape(_TAG.sub("", _BLOCK.sub("\n", inner)))
        cls = Furn if label in _HDR else str
        out.extend(cls(x) for x in inner.split("\n"))
        pos = m.end()
    rest = html[pos:].strip()
    if rest:  # div 로 안 싸인 꼬리가 있으면 버리지 않고 줄로 둔다
        out.extend(htmllib.unescape(_TAG.sub("", _BLOCK.sub("\n", _MATH.sub(tex_plain, rest)))).split("\n"))
    return out


def pages_ocr() -> list[tuple[int, list[str]]]:
    return [(int(f.stem[1:]), ocr_lines(f.read_text(encoding="utf-8")))
            for f in sorted(OCR_DIR.glob("p[0-9][0-9][0-9][0-9].html"))]


def squeeze(lines: list[str]) -> str:
    return re.sub(r'\s+', ' ', ' '.join(lines)).strip()


def split_inline(lines: list[str]):
    """OCR 줄을 라벨 앞에서 자른다. 반환 `(조각, 글자 수)` — 끊는 자리의 공백은 조각에
    안 남으므로 **뒤 조각이 그만큼을 더해서** 센다. 글자 수 대조가 그대로 성립한다."""
    for x in lines:
        cuts = [] if isinstance(x, Furn) or not x.strip() else list(OCR_INLINE.finditer(x))
        if not cuts:
            yield x, None
            continue
        starts = [0] + [m.end() for m in cuts]
        ends = [m.start() for m in cuts] + [len(x)]
        for i, (a, b) in enumerate(zip(starts, ends)):
            piece = x[a:b]
            yield piece, len(piece.strip()) + (cuts[i - 1].end() - cuts[i - 1].start() if i else 0)


def parse(pages: list[tuple[int, list[str]]], ocr: bool = False) -> dict:
    front, plates, furniture, entries = [], [], [], []
    cur, part = None, None
    n_in = n_out = 0

    def put(bucket: list, page: int, line: str, n: int | None = None):
        nonlocal n_out
        n_out += len(line.strip()) if n is None else n
        bucket.append((page, line))

    for page, lines in pages:
        body = "\n".join(lines)
        n_in += sum(len(x.strip()) for x in lines)
        if PLATE_PAGE.search(body):
            for x in lines:
                if x.strip():
                    put(plates, page, x)
            continue
        for x, n_x in (split_inline(lines) if ocr else ((y, None) for y in lines)):
            if not x.strip():
                continue
            if isinstance(x, Furn) or any(r.match(x) for r in FURNITURE):
                put(furniture, page, x, n_x)
                continue
            m = (HEAD_OCR if ocr else HEAD).match(x)
            nopl = None
            if ocr and not m and entries and part is not None:
                nopl = HEAD_NOPL.match(x)
                if nopl and int(nopl.group(1)) != int(entries[-1]["item_no"]) + 1:
                    nopl = None
            if m or nopl:
                mm = m or nopl
                cur = {"item_no": mm.group(1), "plate": int(m.group(2)) if m else None,
                       "name_raw": (m.group(3) if m else nopl.group(2)).strip(), "pdf_page": page,
                       "name_more": [], "family": [], "description": [], "ecology": [],
                       "distribution": [], "after": []}
                entries.append(cur)
                part = "description"
                n_out += len(x.strip()) if n_x is None else n_x
                cur["head_raw"] = x.strip()
                continue
            if cur is None:
                put(front, page, x, n_x)
                continue
            # 과 이름표는 표제 바로 아래에 온다. 그 사이에 낀 한두 줄은 **이름이
            # 길어 넘어온 줄**이다 (`subsp. subarctica O. F. MÜLLER`) — 기재가 아니다
            if part == "description" and not cur["family"] and (FAMILY_OCR if ocr else FAMILY).match(x) \
                    and len(cur["description"]) <= 2:
                # `[色圖]`(원색 도판 표시)만 있는 줄은 OCR 에서는 기재문 쪽에 둔다.
                # 텍스트 레이어 쪽은 이미 낸 산출(312항목)이 그것을 이름 쪽에 넣어
                # 두었고 그 결과를 바꾸지 않는다 (257 — 사람이 정할 일, 보고서)
                keep = [(p, y) for p, y in cur["description"] if ocr and COLOR_PLATE.match(y)]
                cur["name_more"].extend(t for t in cur["description"] if t not in keep)
                cur["description"][:] = keep
                put(cur["family"], page, x, n_x)
                continue
            lab = OCR_LABEL.match(x) if ocr else None
            if ocr and part in ("description", "ecology") and lab:
                txt = lab.group(1)
                if OCR_DIST.search(txt) and (part == "ecology" or END.search(x)):
                    part = "distribution"
                elif OCR_ECO.search(txt):
                    part = "ecology"
                else:  # 못 읽은 라벨 — 자리로 안다
                    part = "distribution" if part == "ecology" else "ecology"
            elif not ocr and part in ("description", "ecology") and ECO.match(x):
                part = "ecology"
            elif not ocr and part in ("description", "ecology") and DIST.match(x):
                part = "distribution"
            put(cur[part], page, x, n_x)
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
    d = parse(pages, ocr=args.source == "ocr")
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
