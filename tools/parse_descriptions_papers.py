#!/usr/bin/env python3
"""논문 스물셋과 동남극 도판집에서 분류군 항목을 가른다 (형태 기재 계열의 셋째).

    python tools/parse_descriptions_papers.py                 # 전부
    python tools/parse_descriptions_papers.py --only 1985     # 코드 앞부분이 맞는 것만
    python tools/parse_descriptions_papers.py --dry-run       # 아무것도 안 쓰고 수만 센다

본보기는 `parse_descriptions.py`(한국 도감)·`parse_descriptions_schmidt.py` 다.
거기서 `PageParser` 를 빌려 쓴다 — 칸(`div data-label`)과 줄을 가르는 것뿐이다.

## 버리는 것이 없다 — 그것을 수로 확인한다

OCR 이 읽은 줄(걷은 `.html`)은 전부 아래 셋 중 한 자리에 간다:

| 자리 | 무엇 |
|---|---|
| `entries[]` | 분류군 항목. `head_lines` + `fields[].lines` |
| `sections[]` | 항목이 아닌 본문 — 절 머리(`Section-Header`·`Title`)마다 끊어 줄을 통째로 둔다 |
| `furniture[]` | 쪽 머리·꼬리(`Page-Header`·`Page-Footer`) |

끝에 **들어온 글자 수(공백 뺀) = 놓인 글자 수**를 대조하고, 어긋나면 그 논문은
오류로 센다. 서버가 지어낸 `Image`·`Figure` 계열 칸은 자료로 쓰지 않으므로
`synthetic_dropped` 에 수만 남긴다. 걷은 쪽(`pNNNN.html`)과 서버 원본
(`pNNNN.raw.html`)의 글자 수 차이도 논문마다 적는다.

`*_raw` 는 태그를 뗀 줄을 `\\n` 으로 이은 것이고(수식 속 LaTeX 는 글자로 풀었다),
`_raw` 없는 칸은 줄을 잇고 공백을 한 칸으로 줄인 것까지만이다.
**`name_raw`·`synonymy_raw` 같은 이름 있는 칸은 `fields` 의 보기일 뿐이다** —
글자 수 대조는 `head_lines`·`fields` 에서만 한다.

## 항목의 모양이 논문마다 다르다

| `kind` | 논문 | 항목이 무엇인가 |
|---|---|---|
| `description` | 1936 · 1985 · 1993 챈틀 | 표제 + 이명·인용 + 기재문(+ Remarks 등 소제목) |
| `flora_ref` | 1992 철원 | 문단 하나 = 분류군 하나 (이름 : 인용 + `Remarks :`) |
| `floral_list` | 1990 · 1998 · 2002 Censarek | 이름 + 인용(+ `Basionym`·`Synonym`·`Remarks` 줄). **기재문은 없다** |

항목이 없는 논문(분포표·층서·지도 중심)은 `sections` 만 낸다 — 지어내지 않는다.

**학명을 OCR 로 확정하지 않는다.** `name_raw` 는 OCR 이 읽은 그대로이고, 색인
(`atlas/*.json`)과 이름으로 비교해 짝 지은 수·안 지은 목록만 낸다 (`index_pairing`).
고치지 않는다.
"""
from __future__ import annotations

import argparse
import difflib
import html as htmllib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION  # noqa: E402
import parse_descriptions_schmidt as S  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OCR = DIADICTION / "ocr"
PAPERS = DIADICTION / "papers"
OUT = DIADICTION / "outputs/descriptions/papers"
FURN = {"Page-Header", "Page-Footer"}
SYNTH = S.SYNTH
HEADLIKE = {"Section-Header", "Title"}

# 코드 → (pdf, 색인 접두사들)
PAPER_PDF = {p.stem: p for p in sorted(PAPERS.glob("*.pdf"))}
PAPER_PDF["pleistocene_east_antarctic_plates"] = DIADICTION / "origin/pleistocene_east_antarctic_plates.pdf"


def ns(s: str) -> int:
    return len(re.sub(r"\s", "", s))


def squeeze(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ── 쪽 읽기 ──────────────────────────────────────────────────────────────────
class Item:
    __slots__ = ("i", "page", "label", "text", "emph")

    def __init__(self, i, page, label, text, emph):
        self.i, self.page, self.label, self.text, self.emph = i, page, label, text, emph


def read_items(code: str) -> tuple[list[Item], dict]:
    """걷은 .html 전부 → 줄(Item) 목록. 서버가 지어낸 칸은 따로 센다."""
    d = OCR / code
    items: list[Item] = []
    synth = {"lines": 0, "chars": 0, "pages": set()}
    nfix = 0
    for f in sorted(d.glob("p[0-9][0-9][0-9][0-9].html")):
        pg = int(f.stem[1:])
        blocks, nf = S.parse_html(f.read_text(encoding="utf-8"))
        nfix += nf
        for b in blocks:
            for ln in b.lines:
                if b.label in SYNTH:
                    synth["lines"] += 1
                    synth["chars"] += ns(ln.text)
                    synth["pages"].add(pg)
                    continue
                items.append(Item(len(items), pg, b.label, ln.text, ln.emph))
    synth["pages"] = sorted(synth["pages"])
    return items, {"synthetic_dropped": synth, "malformed_label_fixed": nfix}


def raw_vs_stripped(code: str) -> dict:
    """서버 원본에만 있고 걷은 쪽에 없는 글자 수 — 칸 종류별."""
    d = OCR / code
    out: dict[str, int] = {}
    tot_raw = tot_html = 0
    for f in sorted(d.glob("p[0-9][0-9][0-9][0-9].raw.html")):
        h = f.with_name(f.name.replace(".raw.html", ".html"))
        raw_cnt: dict[str, int] = {}
        for b in S.parse_html(f.read_text(encoding="utf-8"))[0]:
            raw_cnt[b.label] = raw_cnt.get(b.label, 0) + sum(ns(l.text) for l in b.lines)
        html_cnt: dict[str, int] = {}
        if h.exists():
            for b in S.parse_html(h.read_text(encoding="utf-8"))[0]:
                html_cnt[b.label] = html_cnt.get(b.label, 0) + sum(ns(l.text) for l in b.lines)
        tot_raw += sum(raw_cnt.values())
        tot_html += sum(html_cnt.values())
        for lab, n in raw_cnt.items():
            diff = n - html_cnt.get(lab, 0)
            if diff:
                out[lab] = out.get(lab, 0) + diff
    return {"raw_chars": tot_raw, "stripped_chars": tot_html, "raw_only_by_label": out,
            "raw_only_total": tot_raw - tot_html}


def text_layer(pdf: Path) -> dict:
    """`pdftotext -layout` 쪽별. 글자가 없는 스캔은 has=False."""
    try:
        n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout).group(1))
        t = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                           check=True).stdout
    except Exception as e:  # noqa: BLE001
        return {"has": False, "error": str(e), "pages": {}}
    pages = t.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    chars = [ns(p) for p in pages]
    has = sum(chars) >= 40 * max(1, len(pages))  # 쪽당 평균 40자 미만이면 스캔으로 본다
    return {"has": has, "pdf_pages": n, "chars": sum(chars),
            "pages": {str(i + 1): p for i, p in enumerate(pages)} if has else {}}


# ── 이름 다루기 (비교용 — 원문은 안 고친다) ─────────────────────────────────
INFRA = {"var", "var.", "f", "f.", "fo", "fo.", "forma", "subsp", "subsp.", "status", "ssp", "ssp."}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def binomial_of(name: str) -> tuple[str, str] | None:
    """이름 → (속, 종소명). 저자·변종 앞까지만. 못 읽으면 None. 비교용이다 — 학명 확정이 아니다."""
    s = re.sub(r"\burlencode\b", " ", _fold(name)).replace("|", " ")
    s = re.sub(r"^[\W\d_]+", "", s)
    w = re.findall(r"[A-Za-z][A-Za-z\-]*\.?", s)
    if len(w) < 2:
        return None
    g, e = w[0].rstrip("."), w[1]
    if e[0].isupper() and (e.endswith(".") or len(e) < 4):
        return None  # 대문자로 시작하는 둘째 낱말은 저자 약자일 가능성이 크다 — 종소명으로 안 읽는다
    return g.lower(), e.rstrip(".").lower()


def infra_of(name: str) -> str | None:
    s = _fold(name)
    m = re.search(r"\b(?:var|f|fo|forma|subsp)\.?\s+([a-z][a-z\-]+)", s)
    return m.group(1).lower() if m else None


# ── 항목 틀 ──────────────────────────────────────────────────────────────────
def mk_entry(code, n, kind, head: list[Item], fields: list[tuple[str, list[Item]]], **extra) -> dict:
    """fields = [(label, [Item…])…]. 줄은 전부 `lines` 로 들고, 이름 있는 칸은 보기다."""
    fl = []
    for lab, its in fields:
        fl.append({"label": lab, "pdf_page": its[0].page if its else None,
                   "lines": [{"pdf_page": x.page, "label": x.label, "text_raw": x.text} for x in its],
                   "text_raw": "\n".join(x.text for x in its),
                   "text": squeeze(" ".join(x.text for x in its))})
    e = {"id": f"{code}#{n:03d}", "kind": kind,
         "pdf_page": head[0].page if head else (fields[0][1][0].page if fields and fields[0][1] else None),
         "head_lines": [{"pdf_page": x.page, "label": x.label, "text_raw": x.text} for x in head],
         "fields": fl}
    pages = sorted({x.page for x in head} | {x.page for _, its in fields for x in its})
    e["pdf_pages"] = pages
    e.update(extra)
    return e


def view(e: dict, label_rx: str) -> str | None:
    """fields 중 라벨이 맞는 것의 text_raw 를 잇는다 — 보기."""
    parts = [f["text_raw"] for f in e["fields"] if re.search(label_rx, f["label"], re.I)]
    return "\n".join(parts) if parts else None


def finish_entry(e: dict) -> dict:
    nm = e.get("name_raw") or ""
    e["name"] = squeeze(nm)
    e["synonymy_raw"] = view(e, r"^(synonym|basionym|citation|original|type)")
    e["description_raw"] = view(e, r"^(description|full description|emended|observations)")
    e["remarks_raw"] = view(e, r"^remarks?$")
    e["occurrence_raw"] = view(e, r"^(stratigraphic|occurrence|distribution|ecology)")
    return e


# ── 논문별 규칙 ──────────────────────────────────────────────────────────────
# 규칙은 (items) → (entries 만든 dict 목록, 항목이 가져간 Item 번호 집합, 메모) 를 낸다.
CIT_RX = re.compile(r"\(\d{4}\)|taf\.|Bacillar|Synopsis|Atlas|Diatom\.|\b\d{4}\b.*\bp\.", re.I)


def toc_names_1936(items: list[Item]) -> list[str]:
    toc: list[str] = []
    buf = ""
    for it in items:
        if it.page < 2 or it.page > 5 or not it.label.startswith("Table"):
            continue
        t = it.text.replace("\t", " ").strip()
        m = re.match(r"^(.*?)[ .…]*\.{2,}\s*(\d{1,2})\s*$", t) or re.match(r"^(.*?)\s*\t\s*(\d{1,2})\s*$", it.text.strip())
        if m:
            name = squeeze((buf + " " + m.group(1)).strip())
            buf = ""
            if name and not re.match(r"^(Abstract|General|Description|Bibliography)", name):
                toc.append(name)
        else:
            m2 = re.match(r"^(.*?)\s*\?\s*$", t)  # 끝 점이 빠진 줄(예: `... Grun. ?`)
            buf = (buf + " " + t).strip()
    return toc


def norm_key(s: str) -> str:
    s = re.sub(r"\burlencode\b", " ", _fold(s)).lower()
    s = re.sub(r"[^a-z ]", "", s)
    return re.sub(r"\s+", "", s)


def parse_1936(code, items):
    start = next((it.i for it in items if it.label in HEADLIKE and re.match(r"^DESCRIPTION OF SPECIES", it.text)), None)
    end = next((it.i for it in items if it.i > (start or 0) and it.label in HEADLIKE
                and re.match(r"^BIBLIOGRAPHY", it.text, re.I)), len(items))
    toc = toc_names_1936(items)
    memo = {"toc_names": toc, "region_items": [start, end]}
    if start is None:
        return [], set(), memo
    region = [it for it in items if start < it.i < end and it.label not in FURN]
    heads: list[tuple[int, str]] = []  # (region index, toc name)
    ptr = 0
    unmatched_toc = []
    for name in toc:
        k = norm_key(name)
        best = None
        for j in range(ptr, len(region)):
            it = region[j]
            if it.label not in ("Section-Header", "Text"):
                continue
            t = re.sub(r"^\|\s*", "", it.text)
            if CIT_RX.search(t) and "Plate" not in t[:len(name) + 20]:
                continue
            cand = norm_key(re.split(r"\bPlate\b", t)[0])
            if not cand:
                continue
            a = cand[:len(k)]
            r = difflib.SequenceMatcher(None, a, k).ratio()
            if r >= 0.86 and abs(len(cand) - len(k)) <= max(6, len(k) // 3):
                best = j
                break
            if j - ptr > 40:
                break
        if best is None:
            unmatched_toc.append(name)
            continue
        heads.append((best, name))
        ptr = best + 1
    memo["toc_unmatched_in_body"] = unmatched_toc
    entries, taken = [], set()
    for hi, (j, tname) in enumerate(heads):
        nxt = heads[hi + 1][0] if hi + 1 < len(heads) else len(region)
        head = [region[j]]
        body = [x for x in region[j + 1:nxt]]
        # 머리가 다음 쪽으로 넘어간 `Plate …` 줄
        while body and body[0].label in ("Text", "Section-Header") and re.match(r"^Plate\s*\d", body[0].text):
            head.append(body.pop(0))
        # 이명·인용 줄과 기재문
        fields: list[tuple[str, list[Item]]] = []
        cur_lab = None
        for x in body:
            if x.label not in ("Text", "Section-Header", "List-Item", "Footnote"):
                continue
            first_of_page = (not fields and False)
            if cur_lab is None:
                # 인용 줄은 머리와 같은 속 이름으로 시작한다 (OCR 이 속명을 틀려도 앞 글자가 닮는다)
                hk = norm_key(re.sub(r"^\|\s*", "", head[0].text))[:7]
                xk = norm_key(x.text)[:7]
                is_cit = (difflib.SequenceMatcher(None, hk, xk).ratio() >= 0.75
                          or (bool(re.search(r"\(\d{4}\)", x.text)) and " nov" not in head[0].text))
                cur_lab = "synonymy" if is_cit else "description"
                fields.append((cur_lab, [x]))
                continue
            cont = bool(re.match(r"^(\(|\d|[a-z])", x.text)) and (x.page != fields[-1][1][-1].page)
            if cur_lab == "synonymy" and cont:
                fields[-1][1].append(x)
            elif cur_lab == "synonymy":
                cur_lab = "description"
                fields.append((cur_lab, [x]))
            else:
                fields[-1][1].append(x)
        e = mk_entry(code, len(entries) + 1, "description", head, fields)
        full = " ".join(h.text for h in head)
        full = re.sub(r"^\|\s*", "", full)
        m = re.split(r"\s+Plate\s*\d", full, maxsplit=1)
        e["name_raw"] = m[0].strip()
        e["plate_raw"] = ("Plate " + full[len(m[0]):].strip().split("Plate", 1)[-1].strip()) if len(m) > 1 else None
        e["toc_name"] = tname
        entries.append(finish_entry(e))
        taken.update(x.i for x in head)
        taken.update(x.i for _, its in fields for x in its)
    return entries, taken, memo


# 1985 — 항목 머리는 Section-Header, 본문 줄은 `Label.` 로 연다
LBL1985 = re.compile(r"^(Basionym|Synonyms?|Original description|Full description|Emended description|Description|"
                     r"Holotype|Paratype|Type locality|Type specimen|Stratigraphic occurrences?|Occurrences?|Observations?|"
                     r"Remarks|Etymology|Distribution|Dimensions?|Comparison|Comments?)\s*[.:]\s*(.*)$", re.S)
NOT_GENUS = re.compile(r"^(Although|This|The|These|Type|Two|Previous|It|In|Another|Possible|Some|Both|Because|However|"
                       r"Similar|See|Specimens?|Valves?|Frustules?|Most|Many|Other|Their|There|Thus|When|While|Species|Sample|Only|"
                       r"Such|Here|Further|Also|Thin|Large|Small)\b")
SP_HEAD = re.compile(r"^[A-Z][a-z]+\s+(?!n\.|emend|Simonsen|gen\.)[a-z][a-z\-]+\b|^[A-Z][a-z]+\s+sp\.|^Genus\s|^[A-Z][a-z]+\s+n\.\s*gen")


def generic_header_entries(code, items, *, zone: tuple[int, int], head_rx: re.Pattern, lbl_rx: re.Pattern,
                           skip_heads=lambda t: False, kind="description", cont_head_rx=None, stop_rx=None):
    """Section-Header 가 항목 머리인 논문(1985·1993 챈틀 일부). zone = 항목이 있는 쪽 범위(포함)."""
    lo, hi = zone
    idx = [it for it in items if lo <= it.page <= hi]
    heads = []
    for it in idx:
        if it.label in HEADLIKE and head_rx.search(it.text) and not skip_heads(it.text):
            heads.append(it)
    return idx, heads


def parse_1985(code, items):
    # 항목 영역: `Crucidenticula n. gen.` (쪽 2) 부터 ACKNOWLEDGMENTS 앞까지
    s = next((it.i for it in items if it.label in HEADLIKE and it.page == 2 and it.text.startswith("Crucidenticula n. gen")), None)
    e_ = next((it.i for it in items if it.label in HEADLIKE and it.text.startswith("ACKNOWLEDG")), len(items))
    memo = {"zone_items": [s, e_]}
    if s is None:
        return [], set(), memo
    zone = [it for it in items if s <= it.i < e_]
    UPPER = re.compile(r"^[A-Z0-9 ,.\-()']+$")
    heads = []
    zl = [x for x in zone if x.label not in FURN]
    TAXON_MARK = re.compile(r"n\.\s*(comb|sp|gen)|nom\.|stat\.|\(Plate")
    for k, it in enumerate(zl):
        t = it.text.strip()
        nxt = zl[k + 1] if k + 1 < len(zl) else None
        if it.label in HEADLIKE:
            if UPPER.match(t) and not t.startswith("Genus"):
                continue  # 큰 절 제목 (OTHER ZONAL MARKER SPECIES 등)
            if re.match(r"^\(?\s*Plate", t) or re.match(r"^n\. comb", t):
                continue  # 머리의 꼬리
            if re.match(r"^(Genus\s|[A-Z][a-z]+\s)", t):
                heads.append(it)
        elif it.label == "Text":
            # 머리가 Section-Header 로 안 읽힌 항목 — 이름 모양이면서 표지(n. comb. 등)나 다음 줄의 `(Plate` 가 받친다
            if (SP_HEAD.match(t) and not LBL1985.match(t) and not NOT_GENUS.match(t) and ns(t) < 260
                    and (TAXON_MARK.search(t) or (nxt is not None and re.match(r"^\(?\s*Plate", nxt.text)))):
                heads.append(it)
    ends = [it.i for it in zone if it.label in HEADLIKE and UPPER.match(it.text.strip())
            and not it.text.startswith("Genus") and it.i > s]
    entries, taken = [], set()
    HEADLBLS = ("Text", "Section-Header", "List-Item")
    for hi, h in enumerate(heads):
        nxt_head = heads[hi + 1].i if hi + 1 < len(heads) else e_
        nxt_end = min([x for x in ends if x > h.i] + [e_])
        stop = min(nxt_head, nxt_end)
        rng = [x for x in zone if h.i <= x.i < stop]
        head = [rng[0]]
        k = 1
        while k < len(rng) and (rng[k].label in HEADLIKE or rng[k].label == "Text") and (
                re.match(r"^\(?\s*Plate", rng[k].text) or re.match(r"^n\. comb", rng[k].text)):
            head.append(rng[k]); k += 1
        fields: list[tuple[str, list[Item]]] = []
        for x in rng[k:]:
            if x.label not in HEADLBLS:
                continue  # 그림 캡션·표·꼬리말은 절에 남긴다
            m = LBL1985.match(x.text)
            if m:
                fields.append((m.group(1).strip(), [x]))
            elif fields:
                fields[-1][1].append(x)
            else:
                fields.append(("(body)", [x]))
        e = mk_entry(code, len(entries) + 1, "description", head, fields)
        nm = " ".join(re.sub(r"\s*\(\s*Plate.*$", "", x.text) for x in head if not re.match(r"^\(?\s*Plate", x.text))
        pl = " ".join(m.group(0) for x in head for m in [re.search(r"\(\s*Plate[^)]*\)?", x.text)] if m)
        e["name_raw"] = nm
        e["plate_raw"] = pl or None
        entries.append(finish_entry(e))
        taken.update(x.i for x in head)
        taken.update(x.i for _, its in fields for x in its)
    return entries, taken, memo


# 1993 챈틀 — 머리 다음 줄이 `Pl. …`
PL_RX = re.compile(r"^\(?\s*Pl\s*\.?\s*\d", re.I)
YEAR_RX = re.compile(r"^\s*(1[5-9]\d\d|20\d\d)[a-z]?\s")
RANK_RX = re.compile(r"^(Phylum|Class|Order|Suborder|Family|Subgenus|Genus|GENERA|Subfamily)\b")


def parse_1993(code, items):
    s = next((it.i for it in items if it.label in HEADLIKE and it.text.strip() == "DESCRIPTION"), None)
    e_ = next((it.i for it in items if it.i > (s or 0) and it.label in HEADLIKE and re.match(r"^(REFERENCES|ACKNOWLEDG)", it.text)), len(items))
    memo = {"zone_items": [s, e_]}
    if s is None:
        return [], set(), memo
    # 도판 캡션: `PLATE N` 머리 뒤로 그 쪽 끝까지는 항목에서 뺀다 (절에 남는다). 항목은 도판 쪽을 건너 이어진다
    plate_hdr: dict[int, int] = {}
    for it in items:
        if s < it.i < e_ and it.label in ("Text", "Section-Header") and re.match(r"^PLATE\s*\d", it.text):
            plate_hdr.setdefault(it.page, it.i)
    memo["plate_caption_pages_skipped"] = sorted(plate_hdr)
    zone = [it for it in items if s < it.i < e_ and it.label in ("Text", "Section-Header", "List-Item", "List-Group")
            and not (it.page in plate_hdr and it.i >= plate_hdr[it.page])]
    heads = []
    head_cont: dict[int, Item] = {}  # 머리가 두 줄인 항목 (`… Ralf` / `in Pritchard, 1861`)
    for k, a in enumerate(zone):
        b = zone[k + 1] if k + 1 < len(zone) else None
        c = zone[k + 2] if k + 2 < len(zone) else None
        if b is None:
            continue
        if PL_RX.match(a.text) or YEAR_RX.match(a.text) or RANK_RX.match(a.text) or re.match(r"^(Remarks|Description)", a.text):
            continue
        if PL_RX.match(b.text) and re.match(r"^[A-Z]", a.text) and ns(a.text) < 140:
            heads.append(a)
        elif (c is not None and PL_RX.match(c.text) and re.match(r"^(in|ex|et|&)\s", b.text) and re.match(r"^[A-Z]", a.text)
              and ns(a.text) < 140):
            heads.append(a)
            head_cont[a.i] = b
    # `sp.` 처럼 `Pl.` 이 다음 쪽 머리에 걸려도 놓치지 않도록, 머리 위치는 zone 안에서의 순서다
    entries, taken = [], set()
    allzone = [it for it in items if s < it.i < e_]
    stops = [it.i for it in allzone if it.label in HEADLIKE and (RANK_RX.match(it.text) or re.match(r"^GENERA", it.text))]
    stops += [it.i for it in allzone if it.label == "Text" and (RANK_RX.match(it.text) or re.match(r"^Phylum|^Class ", it.text))]
    for hi, h in enumerate(heads):
        nxt = heads[hi + 1].i if hi + 1 < len(heads) else e_
        stop = min([nxt] + [x for x in stops if x > h.i])
        rng = [x for x in zone if h.i <= x.i < stop]
        head = [rng[0]]
        body = rng[1:]
        if h.i in head_cont and body and body[0].i == head_cont[h.i].i:
            head.append(body.pop(0))
        fields: list[tuple[str, list[Item]]] = []
        cur = None
        for x in body:
            t = x.text
            if PL_RX.match(t) and cur is None and not fields:
                fields.append(("Plate", [x])); cur = "Plate"
            elif YEAR_RX.match(t):
                if cur == "Synonymy":
                    fields[-1][1].append(x)
                else:
                    fields.append(("Synonymy", [x])); cur = "Synonymy"
            elif re.match(r"^Remarks?\s*[:.]", t):
                fields.append(("Remarks", [x])); cur = "Remarks"
            elif re.match(r"^Description\s*[:.]", t):
                fields.append(("Description", [x])); cur = "Description"
            elif fields:
                fields[-1][1].append(x)
            else:
                fields.append(("(body)", [x])); cur = "(body)"
        e = mk_entry(code, len(entries) + 1, "description", head, fields)
        e["name_raw"] = " ".join(x.text for x in head)
        e["plate_raw"] = view(e, r"^Plate$")
        e["synonymy_raw"] = None
        entries.append(finish_entry(e))
        e["synonymy_raw"] = view(e, r"^Synonymy$")
        taken.update(x.i for x in head)
        taken.update(x.i for _, its in fields for x in its)
    return entries, taken, memo


# 1992 — 문단 하나가 분류군 하나. 목록이 도판 쪽(캡션)을 사이에 끼고 이어진다
FLORA_NEW = re.compile(r"^[A-Z][a-z]+\s+(?:[a-z][a-z\-]{2,}|sp\.|spp\.|cf\.|\()")


def parse_1992(code, items):
    s = next((it.i for it in items if it.label in HEADLIKE and it.text.strip() == "FLORA REFERENCES"), None)
    e_ = next((it.i for it in items if it.i > (s or 0) and it.label in HEADLIKE and "Other diatom taxa" in it.text), len(items))
    memo = {"zone_items": [s, e_]}
    if s is None:
        return [], set(), memo
    # 도판 캡션: `Plate N` 머리 뒤로 그 쪽 끝까지 (축척·Fig. 목록)
    skip_pages: dict[int, int] = {}
    for it in items:
        if s < it.i < e_ and it.label in HEADLIKE and re.match(r"^Plate\s*\d", it.text, re.I):
            skip_pages.setdefault(it.page, it.i)
    zone = []
    for it in items:
        if not (s < it.i < e_) or it.label not in ("Text", "List-Item", "List-Group"):
            continue
        if it.page in skip_pages and it.i > skip_pages[it.page]:
            continue
        zone.append(it)
    memo["plate_caption_pages_skipped"] = sorted(skip_pages)
    memo["intro_lines"] = 1
    paras = zone[1:]  # 첫 문단은 서문
    groups: list[list[Item]] = []
    for it in paras:
        if not groups or FLORA_NEW.match(it.text):
            groups.append([it])
        else:
            groups[-1].append(it)  # 쪽·도판을 건너 이어지는 꼬리
    entries, taken = [], set()
    for g in groups:
        t0 = g[0].text
        m = re.split(r"\s*:\s*", t0, maxsplit=1)
        name = m[0].strip() if len(m) > 1 else t0
        e = mk_entry(code, len(entries) + 1, "flora_ref", [], [("Entry", list(g))])
        txt = "\n".join(x.text for x in g)
        mr = re.search(r"\bRemarks?\s*:", txt)
        e["name_raw"] = name
        e["remarks_raw_inline"] = txt[mr.start():] if mr else None
        e["plate_inline_raw"] = (re.findall(r"\[\s*Plate[^\]]*\]?", txt) or [None])[0]
        e = finish_entry(e)
        e["remarks_raw"] = e["remarks_raw_inline"]
        entries.append(e)
        taken.update(x.i for x in g)
    return entries, taken, memo


# 분류군 목록형 — 1990 · 1998 · 2002 Censarek
SUB_RX = re.compile(r"^(Basionym|Synonyms?|Remarks?|Note)\s*[:.]", re.I)
NEWENT_RX = re.compile(r"^[A-Z][A-Za-zÀ-ɏ\-]+\s+(?:[a-z][a-z\-]{2,}|sp\.|spp\.|cf\.|aff\.|\()")


def list_entries(code, items, zones: list[tuple[str, str, int]], note: str):
    """zones = [(시작 절 제목 정규식, 끝 절 제목 정규식, 건너뛸 서문 줄 수)]."""
    entries, taken, memo = [], set(), {"zones": []}
    for srx, erx, skip in zones:
        s = next((it.i for it in items if it.label in HEADLIKE and re.search(srx, it.text)), None)
        if s is None:
            memo["zones"].append({"start": srx, "found": False})
            continue
        e_ = next((it.i for it in items if it.i > s and it.label in HEADLIKE and re.search(erx, it.text)), len(items))
        lines = [it for it in items if s < it.i < e_ and it.label in ("Text", "List-Item", "List-Group")]
        intro, lines = lines[:skip], lines[skip:]
        groups: list[list[Item]] = []
        for it in lines:
            if SUB_RX.match(it.text) and groups:
                groups[-1].append(it)
            elif NEWENT_RX.match(it.text) or not groups:
                groups.append([it])
            else:
                groups[-1].append(it)  # 줄바꿈으로 이어진 꼬리
        for g in groups:
            fields: list[tuple[str, list[Item]]] = [("Citation", [g[0]])]
            for x in g[1:]:
                m = SUB_RX.match(x.text)
                if m:
                    fields.append((m.group(1).capitalize(), [x]))
                else:
                    fields[-1][1].append(x)
            e = mk_entry(code, len(entries) + 1, "floral_list", [], fields)
            t0 = g[0].text
            ym = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", t0[:110])
            e["name_raw"] = t0[:ym.end()] if ym else re.split(r"[;:]", t0)[0][:100]
            e["zone"] = srx
            entries.append(finish_entry(e))
            taken.update(x.i for x in g)
        memo["zones"].append({"start": srx, "found": True, "intro_lines": len(intro), "entries": len(groups),
                              "pdf_pages": [lines[0].page, lines[-1].page] if lines else None})
        # 서문 줄은 절 본문에 남는다 — taken 에 안 넣는다
    return entries, taken, memo


def parse_1990(code, items):
    return list_entries(code, items, [(r"^TAXONOMIC NOTES AND FLORAL", r"^REFERENCES", 1)], "")


def parse_1998(code, items):
    return list_entries(code, items, [(r"^Floral list", r"^References", 1)], "")


def parse_censarek(code, items):
    return list_entries(code, items, [(r"^2\.8\.1 New combinations", r"^2\.8\.2", 1),
                                      (r"^2\.8\.2 Floral list", r"^Chapter 2|^2\.9|^3\.", 0)], "")


def parse_2002z(code, items):
    return list_entries(code, items, [(r"^Appendix\. Taxonomic reference list", r"^References", 1)], "")


RULES = {
    "2002_zielinski_rouxia_lod": parse_2002z,
    "1936_skvortzov_ampen_neogene": parse_1936,
    "1985_akiba_yanagisawa_dsdp87_zonal_markers": parse_1985,
    "1990_gersonde_burckle_odp113_weddell": parse_1990,
    "1992_lee_galmal_quaternary_flora": parse_1992,
    "1993_lee_chaetoceros_yeonil": parse_1993,
    "1998_yanagisawa_akiba_nw_pacific_neogene_codes": parse_1998,
    "2002_censarek_so_miocene_thesis": parse_censarek,
}


# ── 절 나누기 ────────────────────────────────────────────────────────────────
def build_sections(items: list[Item], taken: set[int]):
    secs: list[dict] = []
    furniture: list[dict] = []
    cur = None
    for it in items:
        if it.label in FURN:
            furniture.append({"pdf_page": it.page, "label": it.label, "text_raw": it.text})
            continue
        if it.i in taken:
            if cur is not None:
                cur["entry_pages"].add(it.page)
                cur["had_taken"] = True
            continue
        if it.label in HEADLIKE:
            if cur is not None and not cur["lines"] and not cur.get("had_taken"):
                cur["title_raw"].append(it.text)  # 연달아 온 머리는 한 절 제목
                cur["pdf_page_end"] = it.page
                continue
            cur = {"title_raw": [it.text], "pdf_page_start": it.page, "pdf_page_end": it.page, "lines": [],
                   "entry_pages": set()}
            secs.append(cur)
            continue
        if cur is None:
            cur = {"title_raw": ["(머리 앞)"], "pdf_page_start": it.page, "pdf_page_end": it.page, "lines": [],
                   "entry_pages": set()}
            secs.append(cur)
        cur["lines"].append({"pdf_page": it.page, "label": it.label, "text_raw": it.text})
        cur["pdf_page_end"] = max(cur["pdf_page_end"], it.page)
    out = []
    for n, s in enumerate(secs, 1):
        lines = s.pop("lines")
        ep = sorted(s.pop("entry_pages"))
        out.append({"id": n, "title": squeeze(" / ".join(s["title_raw"])), "title_raw": s["title_raw"],
                    "pdf_page_start": s["pdf_page_start"], "pdf_page_end": s["pdf_page_end"],
                    "entry_pages_inside": ep, "n_lines": len(lines),
                    "n_chars": sum(ns(x["text_raw"]) for x in lines) + sum(ns(t) for t in s["title_raw"]),
                    "lines": lines, "text_raw": "\n".join(x["text_raw"] for x in lines),
                    "text": squeeze(" ".join(x["text_raw"] for x in lines))})
    return out, furniture


def recount(doc: dict) -> dict:
    """쓴 구조에서 다시 글자 수를 센다 — 들어온 수와 맞대어 보는 쪽."""
    n_entry = n_sec = n_furn = 0
    for e in doc["entries"]:
        n_entry += sum(ns(x["text_raw"]) for x in e["head_lines"])
        n_entry += sum(ns(x["text_raw"]) for f in e["fields"] for x in f["lines"])
    for s in doc["sections"]:
        n_sec += sum(ns(x["text_raw"]) for x in s["lines"]) + sum(ns(t) for t in s["title_raw"])
    n_furn = sum(ns(x["text_raw"]) for x in doc["furniture"])
    return {"entries": n_entry, "sections": n_sec, "furniture": n_furn, "total": n_entry + n_sec + n_furn}


# ── 색인과 비교 ──────────────────────────────────────────────────────────────
def index_files(code: str) -> list[Path]:
    yr = code[:4]
    keys = {"1936": ["1936-skvortzov"], "1975": ["1975-lee-pohang"], "1985": ["1985-akiba"], "1986": ["1986-lee-sekorea"],
            "1990": ["1990-gersonde"], "1991": ["1991-lee-yeonil"], "1992": ["1992-lee-galmal"],
            "1996": ["1996-lee-bransfield"], "2001": ["2001-park"], "2017": ["2017-yun"]}
    out = []
    pre = []
    if code.startswith("1993_lee"):
        pre = ["1993-lee-chaetoceros"]
    elif code.startswith("1993_bae"):
        pre = ["1993-bae-southsea"]
    elif code.startswith("1994"):
        pre = ["1994-lee-namyangman"]
    elif code.startswith("2002_censarek"):
        pre = ["2002-censarek"]
    elif code.startswith("2002_zielinski"):
        pre = ["2002-zielinski"]
    else:
        pre = keys.get(yr, [])
    for p in pre:
        out += sorted((REPO / "atlas").glob(p + "*.json"))
    return out


def pair_index(code: str, entries: list[dict]) -> dict:
    files = index_files(code)
    if not files:
        return {"index_file": None, "note": "이 논문의 색인(atlas/<연도>-*.json)이 없다"}
    idx = []
    for f in files:
        for e in json.load(open(f))["entries"]:
            idx.append({"name": e.get("name"), "binomial": e.get("binomial"), "infra": e.get("infra"), "seq": e.get("seq")})
    res = {"index_file": [str(f.relative_to(REPO)) for f in files], "index_entries": len(idx), "parsed_entries": len(entries)}
    if not entries:
        res["note"] = "가른 항목이 없어 짝 지을 것이 없다"
        res["index_names"] = [i["name"] for i in idx]
        return res

    def key_of(name):
        b = binomial_of(name or "")
        return b

    by_key: dict[tuple, list[int]] = {}
    for n, e in enumerate(entries):
        k = key_of(e.get("name_raw"))
        if k:
            by_key.setdefault(k, []).append(n)
    paired, used_e = [], set()
    unpaired_idx = []
    for i in idx:
        b = binomial_of(i["binomial"] or i["name"] or "")
        hit = None
        if b and b in by_key:
            # 변종이 있으면 변종까지 같은 것을 우선
            cands = by_key[b]
            ii = (i["infra"] or "")
            iv = infra_of(i["name"] or "") or (infra_of(ii) if ii else None)
            exact = [n for n in cands if infra_of(entries[n].get("name_raw") or "") == iv]
            pool = [n for n in (exact or cands) if n not in used_e] or (exact or cands)
            hit = pool[0]
            kind = "exact" if exact else "binomial_only"
        if hit is None:
            unpaired_idx.append(i["name"])
            continue
        used_e.add(hit)
        paired.append({"index": i["name"], "entry": entries[hit]["name_raw"], "entry_id": entries[hit]["id"], "match": kind})
    # 이름이 조금 다른 것 — 철자가 다른 짝 후보를 "다르다" 로 적는다
    diffs = []
    ent_names = {n: (binomial_of(e.get("name_raw") or "") or ("", "")) for n, e in enumerate(entries) if n not in used_e}
    still = []
    for nm in unpaired_idx:
        bi = binomial_of(nm or "")
        s1 = " ".join(bi) if bi else (nm or "")
        best = None
        for n, bb in ent_names.items():
            s2 = " ".join(bb)
            r = difflib.SequenceMatcher(None, s1, s2).ratio()
            if r >= 0.85 and (best is None or r > best[0]):
                best = (r, n)
        if best:
            diffs.append({"index": nm, "entry": entries[best[1]]["name_raw"], "entry_id": entries[best[1]]["id"],
                          "ratio": round(best[0], 3)})
        else:
            still.append(nm)
    near = {d["entry_id"] for d in diffs}
    unpaired_entries = [{"id": e["id"], "name_raw": e.get("name_raw"), "pdf_page": e["pdf_page"]}
                        for n, e in enumerate(entries) if n not in used_e and e["id"] not in near]
    res.update({"paired": len(paired), "paired_exact": sum(1 for p in paired if p["match"] == "exact"),
                "paired_binomial_only": sum(1 for p in paired if p["match"] == "binomial_only"),
                "spelling_differs": diffs, "unpaired_index": still, "unpaired_entries": unpaired_entries,
                "pairs": paired})
    return res


# ── 동남극 도판집 ────────────────────────────────────────────────────────────
def parse_plates(code, items):
    return [], set(), {"note": "캡션 전문을 쪽별로 남긴다 — sections 에 쪽 단위로"}


# ── 한 논문 ──────────────────────────────────────────────────────────────────
def do_paper(code: str) -> dict:
    pdf = PAPER_PDF.get(code)
    items, meta = read_items(code)
    pages = sorted({it.page for it in items})
    entries, taken, memo = (RULES.get(code) or (lambda c, i: ([], set(), {})))(code, items)
    secs, furn = build_sections(items, taken)
    doc = {"code": code, "pdf": str(pdf) if pdf else None, "ocr_dir": str(OCR / code),
           "ocr_pages": len(pages), "rule": RULES[code].__name__ if code in RULES else "(항목 규칙 없음 — 절만)",
           "rule_memo": memo, "entries": entries, "sections": secs, "furniture": furn}
    doc["synthetic_dropped"] = meta["synthetic_dropped"]
    doc["raw_vs_stripped"] = raw_vs_stripped(code)
    tl = text_layer(pdf) if pdf else {"has": False}
    doc["text_layer"] = tl
    rc = recount(doc)
    total_in = sum(ns(it.text) for it in items)
    doc["accounting"] = {"chars_in": total_in, "chars_out": rc, "match": total_in == rc["total"],
                         "malformed_label_fixed": meta["malformed_label_fixed"]}
    if tl.get("has"):
        ocr_by_page: dict[int, int] = {}
        for it in items:
            ocr_by_page[it.page] = ocr_by_page.get(it.page, 0) + ns(it.text)
        doc["text_layer_vs_ocr_chars"] = {"layer_total": tl["chars"], "ocr_total": total_in}
    doc["index_pairing"] = pair_index(code, entries)
    # 텍스트 레이어가 있는 논문 — OCR 이 읽은 항목 이름이 같은 쪽(±1)의 텍스트 레이어에 있는가
    if tl.get("has") and entries:
        def tkey(x):
            return re.sub(r"[^a-z]", "", _fold(x).lower())
        layer = {int(k): tkey(v) for k, v in tl["pages"].items()}
        chk = {"checked": 0, "found": 0, "not_found": []}
        for e in entries:
            nm = tkey(re.sub(r"\burlencode\b", "", e.get("name_raw") or ""))[:22]
            if len(nm) < 8:
                continue
            chk["checked"] += 1
            pg = e["pdf_page"]
            if any(nm in layer.get(q, "") for q in (pg - 1, pg, pg + 1)):
                chk["found"] += 1
            else:
                chk["not_found"].append({"id": e["id"], "pdf_page": pg, "name_raw": e.get("name_raw")})
        doc["name_vs_text_layer"] = chk
        # 같은 쪽 텍스트 레이어에서 가장 닮은 `속 종소명` 짝 — OCR 철자와 다르면 둘 다 남긴다 (확정하지 않는다)
        for e in entries:
            b = binomial_of(re.sub(r"\burlencode\b", "", e.get("name_raw") or ""))
            if not b:
                continue
            words: list[str] = []
            for q in (e["pdf_page"] - 1, e["pdf_page"], e["pdf_page"] + 1):
                words += re.findall(r"[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f\-]+", tl["pages"].get(str(q), ""))
            best, bs = None, 0.0
            tgt = " ".join(b)
            for a1, a2 in zip(words, words[1:]):
                cand = (a1 + " " + a2).lower()
                if abs(len(cand) - len(tgt)) > 3:
                    continue
                r = difflib.SequenceMatcher(None, _fold(cand), tgt).ratio()
                if r > bs:
                    best, bs = a1 + " " + a2, r
            if best and bs >= 0.85:
                e["text_layer_binomial"] = best
                e["text_layer_binomial_differs"] = _fold(best).lower() != tgt
    if code.startswith("pleistocene_east_antarctic"):
        cap: dict[str, list] = {}
        for it in items:
            if it.label not in FURN:
                cap.setdefault(str(it.page), []).append({"label": it.label, "text_raw": it.text})
        doc["captions_by_page"] = cap
        doc["pages_without_text"] = [pg for pg in pages if str(pg) not in cap]
    # 항목 밖 절에 남은, 항목 본문처럼 생긴 줄 — 못 가른 것으로 센다
    orphan_rx = re.compile(r"^(Remarks?|Description|Synonyms?|Basionym|Holotype|Paratype|Type locality)\s*[.:]|^(1[5-9]|20)\d\d[a-z]?\s+[A-Z]")
    doc["unassigned"] = []
    if entries:
        for sc in secs:
            for ln in sc["lines"]:
                if orphan_rx.match(ln["text_raw"]) and sc["title"] not in ("REFERENCES", "References"):
                    doc["unassigned"].append({"pdf_page": ln["pdf_page"], "section": sc["title"][:60], "label": ln["label"],
                                              "text_raw": ln["text_raw"]})
    return doc


def write_md(path: Path, doc: dict) -> None:
    L = [f"# {doc['code']}", "",
         f"- 규칙: `{doc['rule']}` · OCR {doc['ocr_pages']}쪽 · 항목 {len(doc['entries'])}개 · 절 {len(doc['sections'])}개",
         f"- 글자 수 대조: 들어온 {doc['accounting']['chars_in']} = 놓인 {doc['accounting']['chars_out']['total']} "
         f"({'맞다' if doc['accounting']['match'] else '어긋난다'})", ""]
    if doc["entries"]:
        L.append("## 항목")
        for e in doc["entries"]:
            L += ["", f"### {e['id']} · p.{e['pdf_page']} · {e.get('name_raw') or '(이름 없음)'}"]
            if e.get("plate_raw"):
                L.append(f"- 도판: {e['plate_raw']}")
            for f in e["fields"]:
                L.append(f"- **{f['label']}** (p.{f['pdf_page']}): {f['text']}")
        L.append("")
    L.append("## 절")
    for s in doc["sections"]:
        L += ["", f"### [{s['id']}] {s['title']} (p.{s['pdf_page_start']}–{s['pdf_page_end']} · {s['n_chars']}자"
              + (f" · 항목 쪽 {s['entry_pages_inside']}" if s["entry_pages_inside"] else "") + ")", ""]
        for ln in s["lines"]:
            L.append(f"p.{ln['pdf_page']} [{ln['label']}] {ln['text_raw'][:2000]}")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="코드 앞부분")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    codes = [d.name for d in sorted(OCR.iterdir()) if d.name in PAPER_PDF]
    if a.only:
        codes = [c for c in codes if c.startswith(a.only)]
    OUT.mkdir(parents=True, exist_ok=True)
    inv = []
    bad = 0
    for c in codes:
        doc = do_paper(c)
        ac = doc["accounting"]
        pr = doc["index_pairing"]
        flag = "" if ac["match"] else "  ★글자 수 어긋남"
        print(f"{c[:44]:44} 쪽 {doc['ocr_pages']:3} 절 {len(doc['sections']):3} 항목 {len(doc['entries']):3} "
              f"in {ac['chars_in']:7} out {ac['chars_out']['total']:7} 합성버림 {doc['synthetic_dropped']['chars']:5}{flag}")
        if not ac["match"]:
            bad += 1
        inv.append({"code": c, "ocr_pages": doc["ocr_pages"], "text_layer": doc["text_layer"].get("has"),
                    "rule": doc["rule"], "sections": len(doc["sections"]), "entries": len(doc["entries"]),
                    "entry_pages": [min(e["pdf_pages"][0] for e in doc["entries"]),
                                    max(e["pdf_pages"][-1] for e in doc["entries"])] if doc["entries"] else None,
                    "unassigned": len(doc["unassigned"]), "name_vs_text_layer": ({k: (v if k != "not_found" else len(v)) for k, v in doc["name_vs_text_layer"].items()} if "name_vs_text_layer" in doc else None), "accounting": ac, "synthetic_dropped": doc["synthetic_dropped"],
                    "raw_vs_stripped": doc["raw_vs_stripped"],
                    "index_pairing": {k: v for k, v in pr.items() if k not in ("pairs",)}})
        if not a.dry_run:
            (OUT / f"{c}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            write_md(OUT / f"{c}.md", doc)
    if not a.dry_run:
        (OUT / "_inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"논문 {len(codes)} · 글자 수 어긋남 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
