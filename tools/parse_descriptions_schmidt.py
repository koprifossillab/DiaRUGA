#!/usr/bin/env python3
"""Schmidt 『Atlas der Diatomaceenkunde』 해설면(Erläuterungen)을 항목별로 가른다.

    python tools/parse_descriptions_schmidt.py            # 읽어서 json·md 를 낸다
    python tools/parse_descriptions_schmidt.py --dry-run  # 아무것도 안 쓰고 수만 센다

OCR 서버가 읽은 `Diadiction/ocr/Band1..4/pNNNN.html`(도판면 산문을 걷은 것)을 읽는다.
본보기는 `parse_descriptions.py`(한국 도감)이고 원칙도 같다 — **버리는 글이 없다.**
들어온 글자(공백을 뺀 글자 수)가 어느 한 자리에 놓였는지 세어 어긋나면 멈춘다.

## Schmidt 해설면의 모양

짝수 쪽이 해설, 바로 다음 홀수 쪽이 도판이다. 해설면은 머리(`Erläuterungen zu A.
Schmidt's Atlas … Tafel N.`) 아래에 **그림 번호 — 이름 — 산지 — 짧은 비고**가
한 줄(`<li>` 또는 `<p>`)씩 온다. 시대에 따라 모양이 다르다 — Band3·4(Fricke 판)는
산지가 소제목(`1-11. Nordsee.`)이고 이름이 목록 옆 칸에 따로 있다. 그래서 줄의 모양을
**한 가지로 가정하지 않고** 줄마다 가른다:

| 자리 | 무엇 |
|---|---|
| `sections[].header` | `Tafel` 머리 · 발행일 · 배율 문구 — 첫 그림 줄 앞까지 |
| `sections[].items[kind=entry]` | 그림 번호로 시작하는 줄 (`figs_raw`·`name_raw`·`text_raw`) |
| `sections[].items[kind=group]` | 그림 번호로 시작하는 소제목 (`1-11. Nordsee.`) |
| `sections[].items[kind=note]` | 그림 번호 없는 글 (이름 칸·본문) |
| `sections[].items[kind=footnote]` | 각주 칸 |
| `front` | 첫 Tafel 앞 (머리말) |
| `verzeichnis` | 해설이 끝난 뒤의 `Vorwort`·색인 쪽 |
| `plate_text` | 도판면에 얹힌 글 (캡션·서명) |
| `synthetic` | `Image`·`Figure`·`Complex-Image`·`Diagram` 칸의 산문 — **서버가 지어낸 것이라 자료로 안 쓴다.** 걷은 .html 에 남은 것을 가둬 두고 수만 센다 |
| `furniture` | 쪽 머리·꼬리 |
| `unassigned` | 가르지 못한 줄 |

`name_raw` 는 **줄 맨 앞의 굵은·기울인 글씨(이름)** 에서, 없으면 첫 쉼표 앞에서
따온다(`name_src`). **어느 쪽도 이름이라고 확정하지 않는다** — 산지가 앞에 오는 판이
있어서다. 쪽·그림 번호가 열쇠이고 이름은 보기용이다. 학명은 OCR 이 그럴듯하게
틀리므로 고치지도, 맞다고 하지도 않는다.

`*_raw` 는 OCR 줄 그대로(HTML 안의 서식 공백만 줄였다), `_raw` 없는 칸은 줄을 잇고
공백을 한 칸으로 줄인 것이다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION  # noqa: E402
from parse_descriptions import _MATH, tex_plain  # noqa: E402  (LaTeX → 글자 풀이를 같이 쓴다)

OCR = DIADICTION / "ocr"
INDEX = Path(__file__).resolve().parent.parent / "atlas/schmidt.json"
OUT_DIR = DIADICTION / "outputs/descriptions"
BANDS = ["Band1", "Band2", "Band3", "Band4"]

FURN = {"Page-Header", "Page-Footer"}
SYNTH = {"Image", "Figure", "Complex-Image", "Diagram", "Picture", "Blank Page"}
IMGBLOCK = {"Image", "Figure", "Complex-Image", "Picture"}

BREAK = {"p", "br", "ol", "ul", "table", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
         "blockquote", "hr", "caption", "tbody", "thead", "dl", "dt", "dd", "pre"}
EMPH = {"b", "i", "em", "strong", "u"}


def nonspace(s: str) -> int:
    return len(re.sub(r"\s", "", s))


class Line:
    __slots__ = ("text", "emph", "li", "h")

    def __init__(self, li: bool, h: int | None):
        self.text, self.emph, self.li, self.h = "", [], li, h


class Block:
    def __init__(self, label: str):
        self.label, self.lines = label, []


class PageParser(HTMLParser):
    """한 쪽 .html → 칸(`div data-label`)과 줄. 바꾸는 것은 없다 — 태그를 떼고 줄을 가를 뿐이다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.depth = 0
        self.cur: Line | None = None
        self.pend_li = False
        self.pend_h: int | None = None
        self.emph_depth = 0
        self.emph_open = False

    def _block(self) -> Block:
        if not self.blocks or self.depth == 0 and self.blocks[-1].label != "(none)":
            if self.depth == 0:
                self.blocks.append(Block("(none)"))
        return self.blocks[-1]

    def _newline(self):
        self.cur = None
        self.emph_open = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            if self.depth == 0:
                self._newline()
                self.blocks.append(Block(a.get("data-label") or "?"))
            self.depth += 1
            return
        if tag == "li":
            self._newline()
            self.pend_li = True
        elif tag in BREAK:
            self._newline()
            if tag[0] == "h" and len(tag) == 2 and tag[1].isdigit():
                self.pend_h = int(tag[1])
        elif tag in ("td", "th"):
            if self.cur is not None and self.cur.text.strip():
                self.cur.text += "\t"
        elif tag in EMPH:
            self.emph_depth += 1

    def handle_endtag(self, tag):
        if tag == "div":
            self.depth = max(0, self.depth - 1)
            if self.depth == 0:
                self._newline()
            return
        if tag in EMPH:
            self.emph_depth = max(0, self.emph_depth - 1)
            self.emph_open = False
        elif tag in BREAK or tag in ("li", "tr"):
            self._newline()

    def handle_data(self, data):
        if not data.strip():
            if self.cur is not None and data:
                self.cur.text += " "
            return
        if not self.blocks:
            self.blocks.append(Block("(none)"))
        blk = self.blocks[-1]
        if self.cur is None:
            self.cur = Line(self.pend_li, self.pend_h)
            self.pend_li, self.pend_h = False, None
            blk.lines.append(self.cur)
        d = re.sub(r"[ \n\r]+", " ", data)
        self.cur.text += d
        if self.emph_depth > 0:
            if self.emph_open and self.cur.emph:
                self.cur.emph[-1] += d
            else:
                self.cur.emph.append(d)
                self.emph_open = True
        else:
            self.emph_open = False


MALFORMED = re.compile(r'data-label>([A-Za-z-]+)"')


def parse_html(html: str) -> tuple[list[Block], int]:
    """→ (칸 목록, 닫는 따옴표가 깨진 속성을 고친 수). 칸 안 빈 줄은 버린다(글자가 없다)."""
    html, nfix = MALFORMED.subn(r'data-label="\1"', html)
    html = _MATH.sub(tex_plain, html)
    p = PageParser()
    p.feed(html)
    p.close()
    for b in p.blocks:
        for ln in b.lines:
            ln.text = ln.text.strip(" ")
        b.lines = [ln for ln in b.lines if ln.text.strip()]
    return [b for b in p.blocks if b.lines], nfix


# ── 줄의 모양 ─────────────────────────────────────────────────────────────────
TAFEL_VAL = r"[0-9IVXLl]{1,4}[a-z]?(?:\s*(?:[-–—]|u\.|und|&)\s*[0-9IVXLl]{1,4})?"
TAFEL = re.compile(rf"^\s*(?:Heft\s*\d+\s*[,.]?\s*)?Tafel\s+({TAFEL_VAL})\s*[.:]?\s*$")
TITLE = re.compile(r"^\s*(?:Vorl[aä]ufige\s+)?Erl[aä]uterungen\.?\s*$", re.I)
VERZ_TITLE = re.compile(r"^\s*Verzeichnis\.?\s*$", re.I)
SERIE_TITLE = re.compile(r"^\s*SERIE\s+[IVX]+\s*$", re.I)
FIG = re.compile(r"^\s*(\d{1,3}[a-z]?(?:\s*(?:[-–—,;.&]|u\.|und)\s*\d{1,3}[a-z]?)*)\s*[.)]\s*(.*)$", re.S)
FIG_SOFT = re.compile(r"^\s*(\d{1,3}[a-z]?(?:\s*(?:[-–—,;.&]|u\.|und)\s*\d{1,3}[a-z]?)*)\s*[.)]?\s*(.*)$", re.S)
INLINE_FIG = re.compile(r"(?:^|[,;]\s+)(\d{1,3}[a-z]?)\.\s+(?=[A-ZÄÖÜa-zäöü])")
VORWORT = re.compile(r"^\s*Vorwort\.?\s*$", re.I)


def expand_figs(raw: str) -> list[str]:
    """`13—15` → 13 14 15, `1. 2` → 1 2, `3a` → 3a. 읽는 것만 한다."""
    out: list[str] = []
    for part in re.split(r"\s*(?:[,;.&]|u\.|und)\s*", raw):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)[a-z]?\s*[-–—]\s*(\d+)[a-z]?", part)
        if m and 0 <= int(m.group(2)) - int(m.group(1)) <= 80:
            out.extend(str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1))
        else:
            out.append(part)
    return out


def split_entry(ln: Line, strict: bool):
    m = (FIG if strict else FIG_SOFT).match(ln.text)
    if not m:
        return None
    return m.group(1).strip(), m.group(2)


def name_of(ln: Line, rest: str) -> tuple[str, str]:
    """(name_raw, name_src). 줄 맨 앞의 굵은·기울인 글씨 → 없으면 첫 쉼표 앞 → 없으면 ''."""
    for e in ln.emph:
        e = re.sub(r"^\s*\d[\d\s.,;&a-z\-–—]*?[.)]\s*", "", e).strip()
        if re.search(r"[A-Za-zÄÖÜäöüß]{3,}", e):
            return e, "emph"
    head = rest.split(",")[0].strip() if "," in rest else ""
    return (head, "comma") if head else ("", "none")


def tafel_int(raw: str | None) -> int | None:
    return int(raw) if raw and raw.isdigit() else None


# ── 한 권을 읽는다 ────────────────────────────────────────────────────────────
def read_band(band: str) -> dict:
    files = sorted((OCR / band).glob("p[0-9][0-9][0-9][0-9].html"))
    sections: list[dict] = []
    front, verz, plate_text, synth, furn, unassigned, pages_info = [], [], [], [], [], [], []
    n_in = n_out = 0
    fixes = 0
    cur: dict | None = None
    verz_mode = False
    prev_role = None

    def put(bucket: list, page: int, text: str, **kw):
        nonlocal n_out
        n_out += nonspace(text)
        bucket.append({"pdf_page": page, "line": text, **kw})

    for f in files:
        page = int(f.stem[1:])
        blocks, nfix = parse_html(f.read_text(encoding="utf-8", errors="replace"))
        fixes += nfix
        n_in += sum(nonspace(ln.text) for b in blocks for ln in b.lines)
        body = [b for b in blocks if b.label not in FURN and b.label not in SYNTH]
        for b in blocks:
            if b.label in FURN:
                for ln in b.lines:
                    put(furn, page, ln.text)
            elif b.label in SYNTH:
                for ln in b.lines:
                    put(synth, page, ln.text, block=b.label)
        # 도판면 판별은 서버 원본(raw)의 칸 이름으로 한다 — 걷은 쪽에서는 Image 칸이 이미 빠져 있다
        raw_f = f.with_name(f.stem + ".raw.html")
        raw_labels = set(re.findall(r'data-label="([^"]*)"', raw_f.read_text(encoding="utf-8", errors="replace"))) \
            if raw_f.exists() else set()
        has_img = bool(raw_labels & IMGBLOCK) or any(b.label in IMGBLOCK for b in blocks)
        head_lines = [ln.text for b in body for ln in b.lines][:14]
        tafel_raw, has_title = None, False
        for t in head_lines:
            m = TAFEL.match(t)
            if m and tafel_raw is None:
                tafel_raw = m.group(1).strip()
            if TITLE.search(t):
                has_title = True
        if not body:
            role = "blank" if not has_img else "plate"
        elif any(VERZ_TITLE.match(t) for t in head_lines) and cur is not None:
            role, verz_mode = "verzeichnis", True
        elif any(SERIE_TITLE.match(t) for t in head_lines):
            role = "front"   # 시리즈 속표지 (Serie IX 등)
        elif tafel_raw is not None or has_title:
            role = "explanation"
        elif has_img:
            role = "plate"
        elif any(VORWORT.match(ln.text) for b in body for ln in b.lines):
            role, verz_mode = "verzeichnis", cur is not None
            if not verz_mode:
                role = "front"
        elif verz_mode:
            role = "verzeichnis"
        elif cur is not None and prev_role in ("explanation", "continuation"):
            role = "continuation"
        else:
            role = "front" if cur is None else "unassigned"
        if role == "explanation":
            verz_mode = False
        pages_info.append({"pdf_page": page, "role": role, "tafel_header": tafel_raw})
        prev_role = role if body else prev_role

        if role in ("plate", "blank"):
            for b in body:
                for ln in b.lines:
                    put(plate_text, page, ln.text, block=b.label)
            continue
        if role == "front":
            for b in body:
                for ln in b.lines:
                    put(front, page, ln.text, block=b.label)
            continue
        if role == "verzeichnis":
            for b in body:
                for ln in b.lines:
                    put(verz, page, ln.text, block=b.label)
            continue
        if role == "unassigned":
            for b in body:
                for ln in b.lines:
                    put(unassigned, page, ln.text, block=b.label, reason="소속 없는 쪽")
            continue

        if role == "explanation":
            cur = {"band": band, "tafel_raw": tafel_raw, "tafel": tafel_int(tafel_raw),
                   "tafel_header_read": tafel_raw is not None, "start_pdf_page": page,
                   "pdf_pages": [page], "header": [], "items": [], "_state": "header"}
            sections.append(cur)
        else:  # continuation
            cur["pdf_pages"].append(page)

        last_entry = None  # 같은 칸 안에서 이어 붙일 항목
        for b in body:
            last_entry = None
            for ln in b.lines:
                txt = ln.text
                is_list = b.label == "List-Group"
                if b.label == "Footnote":
                    put_item(cur, "footnote", page, ln, b.label)
                    n_out += nonspace(txt)
                    continue
                if cur["_state"] == "header":
                    se = split_entry(ln, strict=True) if (is_list or ln.li or b.label == "Section-Header") else None
                    if not (is_list or ln.li) and se is None:
                        n_out += nonspace(txt)
                        cur["header"].append({"pdf_page": page, "line": txt, "block": b.label})
                        continue
                    cur["_state"] = "body"
                if is_list or ln.li:
                    se = split_entry(ln, strict=not ln.li)
                    if se:
                        last_entry = put_item(cur, "entry", page, ln, b.label, se)
                    elif last_entry is not None:
                        last_entry["text_raw"] += "\n" + txt
                        last_entry["_lines"].append(ln)
                    else:
                        put_item(cur, "note", page, ln, b.label)
                    n_out += nonspace(txt)
                    continue
                # 목록 칸이 아니어도(`Text` 칸 하나가 한 줄) 그림 번호로 시작하면 항목이다
                se = split_entry(ln, strict=True) if b.label in ("Section-Header", "Text", "Table") else None
                kind = "note" if se is None else ("group" if b.label == "Section-Header" else "entry")
                last_entry = put_item(cur, kind, page, ln, b.label, se) if kind == "entry" else \
                    (put_item(cur, kind, page, ln, b.label, se) and None)
                n_out += nonspace(txt)

    # 서버 원본(raw)과 걷은 쪽의 글자 수 — 걷은 것이 지어낸 산문만 뺐는지 본다
    raw_total = raw_synth = 0
    for f in files:
        rf = f.with_name(f.stem + ".raw.html")
        if not rf.exists():
            continue
        rb, _ = parse_html(rf.read_text(encoding="utf-8", errors="replace"))
        for b in rb:
            n = sum(nonspace(ln.text) for ln in b.lines)
            raw_total += n
            if b.label in SYNTH:
                raw_synth += n
    stripped_synth = sum(nonspace(x["line"]) for x in synth)
    raw_stats = {"raw_chars": raw_total, "raw_chars_in_synthetic_blocks": raw_synth,
                 "stripped_chars": n_in, "stripped_chars_in_synthetic_blocks": stripped_synth,
                 "raw_only_nonsynthetic": (raw_total - raw_synth) - (n_in - stripped_synth)}
    if n_in != n_out:
        raise SystemExit(f"{band}: 글자 수가 어긋난다 — 들어온 것 {n_in} · 놓인 것 {n_out}")
    for s in sections:
        del s["_state"]
        for it in s["items"]:
            lines = it.pop("_lines")
            it["text"] = re.sub(r"\s+", " ", it["text_raw"]).strip()
            if it["kind"] == "entry":
                it["emph_raw"] = [e.strip() for ln in lines for e in ln.emph if e.strip()]
    return {"band": band, "pages_read": len(files), "chars_in": n_in, "chars_out": n_out,
            "sections": sections, "front": front, "verzeichnis": verz, "plate_text": plate_text,
            "synthetic": synth, "furniture": furn, "unassigned": unassigned,
            "pages": pages_info, "malformed_label_fixes": fixes, "raw_vs_stripped": raw_stats}


def put_item(sec: dict, kind: str, page: int, ln: Line, label: str, se: tuple[str, str] | None = None) -> dict:
    it = {"kind": kind, "pdf_page": page, "block": label, "text_raw": ln.text, "_lines": [ln]}
    if se:
        figs_raw, rest = se
        it["figs_raw"] = figs_raw
        it["figs"] = expand_figs(figs_raw)
        if kind == "entry":
            it["name_raw"], it["name_src"] = name_of(ln, rest)
            # `3. Ventrale, 4. dorsale Gürtelbandseite.` — 한 줄에 그림 둘이 든 자리. 앞 번호는 figs 에 안 넣고 따로 둔다
            it["figs_inline"] = [m.group(1) for m in INLINE_FIG.finditer(rest)]
    sec["items"].append(it)
    return it


# ── 색인과의 대조 ─────────────────────────────────────────────────────────────
def tafel_diffs(bands: list[dict], index: dict) -> list[dict]:
    """쪽마다 새 OCR 의 Tafel 머리와 색인의 Tafel 을 나란히 놓는다. 어느 쪽이 맞다고 정하지 않는다."""
    idx: dict[tuple[str, int], set[int]] = {}
    for e in index["entries"]:
        for p in e["placements"]:
            if p.get("pdf_page") and p.get("plate") is not None:
                idx.setdefault((p["volume"], p["pdf_page"]), set()).add(int(p["plate"]))
    out = []
    for b in bands:
        seen_pages = set()
        for s in b["sections"]:
            for pg in s["pdf_pages"]:
                seen_pages.add(pg)
                ocr_t = s["tafel"] if pg == s["start_pdf_page"] else None
                want = idx.get((b["band"], pg))
                if ocr_t is None and pg == s["start_pdf_page"]:
                    out.append({"band": b["band"], "pdf_page": pg, "ocr_tafel_raw": s["tafel_raw"],
                                "index_tafel": sorted(want) if want else None, "kind": "ocr_unreadable"})
                elif pg == s["start_pdf_page"] and (not want or ocr_t not in want):
                    out.append({"band": b["band"], "pdf_page": pg, "ocr_tafel_raw": s["tafel_raw"],
                                "index_tafel": sorted(want) if want else None,
                                "kind": "index_missing" if not want else "differs"})
                elif pg != s["start_pdf_page"] and want and s["tafel"] not in want:
                    out.append({"band": b["band"], "pdf_page": pg, "ocr_tafel_raw": s["tafel_raw"],
                                "index_tafel": sorted(want), "kind": "continuation_differs"})
        for (vol, pg), want in idx.items():
            if vol == b["band"] and pg not in seen_pages:
                out.append({"band": vol, "pdf_page": pg, "ocr_tafel_raw": None,
                            "index_tafel": sorted(want), "kind": "no_explanation_section"})
    return sorted(out, key=lambda r: (r["band"], r["pdf_page"]))


def parse_index_figs(s: str | None) -> set[str] | None:
    return set(expand_figs(s)) if s else None


def pair_index(bands: list[dict], index: dict) -> dict:
    """색인 배치(placement)마다 (권, 해설 쪽)의 항목과 그림 번호로 짝을 짓는다."""
    by_page: dict[tuple[str, int], list[dict]] = {}
    for b in bands:
        for s in b["sections"]:
            for it in s["items"]:
                if it["kind"] == "entry":
                    by_page.setdefault((b["band"], it["pdf_page"]), []).append(it)
    sec_pages = {(b["band"], pg) for b in bands for s in b["sections"] for pg in s["pdf_pages"]}
    res = []
    for e in index["entries"]:
        pls = []
        for p in e["placements"]:
            key = (p["volume"], p["pdf_page"])
            figs = parse_index_figs(p.get("figures"))
            its = by_page.get(key, [])
            if key not in sec_pages:
                state = "no_page"
                hit = []
            elif figs is None:
                state = "page_only"
                hit = []
            else:
                hit = [i for i in its if figs & (set(i["figs"]) | set(i.get("figs_inline", [])))]
                state = "fig_matched" if hit else "fig_unmatched"
            spell = None
            if hit:
                ep = (e["binomial"] or e["name"]).split()[-1].lower()
                blob = " ".join(i["text"] for i in hit).lower()
                spell = "ok" if ep in blob else "differs"
            pls.append({"plate": p["plate"], "pdf_page": p["pdf_page"], "volume": p["volume"],
                        "figures": p.get("figures"), "state": state, "epithet_in_text": spell,
                        "ocr_fig_lines": [i["text"][:90] for i in hit][:3]})
        res.append({"seq": e["seq"], "name": e["name"], "placements": pls})
    return {"entries": res}


EXPECT = {"Band1": range(1, 145), "Band2": range(145, 241), "Band3": range(241, 337),
          "Band4": list(range(337, 421)) + list(range(433, 481))}   # 421–432 는 미간행 (Band2 p.2 판권)


def sequence_checks(bands: list[dict]) -> dict:
    """Tafel 번호가 읽힌 순서가 책의 순서와 맞는가. 어느 쪽이 맞다고 정하지 않고 늘어놓기만 한다."""
    out = {}
    for b in bands:
        secs = b["sections"]
        got = [s["tafel"] for s in secs if s["tafel"] is not None]
        exp = list(EXPECT[b["band"]])
        cnt = Counter(got)
        breaks = []
        prev = None
        for s in secs:
            t = s["tafel"]
            if t is None:
                continue
            if prev is not None and t != prev + 1 and not (prev == 420 and t == 433):
                breaks.append({"pdf_page": s["start_pdf_page"], "prev": prev, "read": t})
            prev = t
        out[b["band"]] = {
            "sections": len(secs), "tafel_unread": [s["start_pdf_page"] for s in secs if s["tafel"] is None],
            "missing_from_expected": sorted(set(exp) - set(got)),
            "outside_expected": sorted(set(got) - set(exp)),
            "duplicates": sorted(t for t, c in cnt.items() if c > 1),
            "sequence_breaks": breaks}
    return out


def pairing_summary(pairing: dict) -> dict:
    """색인 항목 단위 분류 — 하나라도 그림 번호로 짝이 지어지면 paired."""
    cls = {}
    for e in pairing["entries"]:
        st = {p["state"] for p in e["placements"]}
        cls[e["seq"]] = ("paired" if "fig_matched" in st else "page_only" if "page_only" in st
                         else "fig_unmatched" if "fig_unmatched" in st else "no_page")
    diff = [(e["seq"], e["name"], p["volume"], p["pdf_page"], p["plate"], p["figures"], p["ocr_fig_lines"])
            for e in pairing["entries"] for p in e["placements"] if p["epithet_in_text"] == "differs"]
    return {"entry_class": cls, "counts": dict(Counter(cls.values())),
            "placements_spelling": dict(Counter(p["epithet_in_text"] for e in pairing["entries"]
                                                for p in e["placements"] if p["epithet_in_text"])),
            "spelling_differs": diff}


def write_pairing_md(path: Path, pairing: dict, summ: dict) -> None:
    out = ["# Schmidt 색인(atlas/schmidt.json) ↔ 새 OCR 해설 항목 짝짓기", "",
           "열쇠는 (권, PDF 해설 쪽, 그림 번호)다. 이름 철자는 **비교만 했고** 고치지 않았다.", "",
           f"색인 항목 단위: {summ['counts']}", f"배치 단위 철자 비교(종소명이 짝 지어진 줄에 있나): {summ['placements_spelling']}", ""]
    for cl, title in (("fig_unmatched", "해설 쪽은 있으나 그림 번호가 안 맞은 것"), ("no_page", "해설 쪽이 읽히지 않은 것")):
        out += [f"## {title}", ""]
        for e in pairing["entries"]:
            if summ["entry_class"][e["seq"]] == cl:
                for p in e["placements"]:
                    out.append(f"- #{e['seq']} {e['name']} · {p['volume']} p.{p['pdf_page']} (Tafel {p['plate']}, 그림 {p['figures']}) → {p['state']}")
        out.append("")
    out += ["## 짝은 지어졌으나 종소명이 그 줄에 없는 것 (철자 차이 또는 줄이 이름을 안 든 것)", ""]
    for seq, name, vol, pg, pl, fg, lines in summ["spelling_differs"]:
        out.append(f"- #{seq} {name} · {vol} p.{pg} (Tafel {pl}, 그림 {fg}) ⇒ OCR 줄: {' ‖ '.join(lines)}")
    path.write_text("\n".join(out), encoding="utf-8")


# ── 출력 ──────────────────────────────────────────────────────────────────────
def write_md(path: Path, bands: list[dict]) -> None:
    out = ["# Schmidt, Atlas der Diatomaceenkunde — 해설 항목 (OCR)", "",
           "`tools/parse_descriptions_schmidt.py` 가 낸 것을 사람이 읽도록 옮긴 것이다. 글은 OCR 그대로다 —",
           "**학명 철자는 OCR 이 틀릴 수 있고 고치지 않았다.** Tafel 번호도 OCR 값이다(열쇠는 PDF 쪽).", ""]
    for b in bands:
        out += [f"# {b['band']}", ""]
        for s in b["sections"]:
            pgs = ", ".join(map(str, s["pdf_pages"]))
            out.append(f"## {b['band']} · Tafel {s['tafel_raw'] or '(못 읽음)'} · PDF p.{pgs}")
            out.append("")
            for h in s["header"]:
                out.append(f"> {h['line']}")
            if s["header"]:
                out.append("")
            for it in s["items"]:
                if it["kind"] == "entry":
                    out.append(f"- **{it['figs_raw']}** · {it['text']}")
                elif it["kind"] == "group":
                    out.append(f"\n### {it['text']}")
                elif it["kind"] == "footnote":
                    out.append(f"- *(각주 p.{it['pdf_page']})* {it['text']}")
                else:
                    out.append(f"- *(글 p.{it['pdf_page']})* {it['text']}")
            out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    bands = [read_band(b) for b in BANDS]
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    diffs = tafel_diffs(bands, index)
    pairing = pair_index(bands, index)
    seq = sequence_checks(bands)
    for k, v in seq.items():
        print(f"{k}: 절 {v['sections']} · 못 읽은 Tafel 쪽 {v['tafel_unread']} · 기대 범위에서 안 읽힌 것 {v['missing_from_expected']} "
              f"· 범위 밖 {v['outside_expected']} · 겹침 {v['duplicates']} · 순서 끊김 {len(v['sequence_breaks'])}")

    tot = {"pages": 0, "chars": 0, "sections": 0, "entries": 0, "groups": 0, "notes": 0, "footnotes": 0}
    kinds = Counter(i["kind"] for b in bands for s in b["sections"] for i in s["items"])
    for b in bands:
        ents = sum(1 for s in b["sections"] for i in s["items"] if i["kind"] == "entry")
        print(f"{b['band']}: 쪽 {b['pages_read']} · 글자 {b['chars_in']} (전부 놓였다) · Tafel 절 {len(b['sections'])} · "
              f"항목 {ents} · 못 가른 줄 {len(b['unassigned'])} · 지어낸 칸 글자 "
              f"{sum(nonspace(x['line']) for x in b['synthetic'])} · 깨진 속성 고침 {b['malformed_label_fixes']}")
        print("   raw 대 걷은 쪽:", b["raw_vs_stripped"])
        print("   쪽 역할:", dict(Counter(p["role"] for p in b["pages"])))
        tot["pages"] += b["pages_read"]
        tot["chars"] += b["chars_in"]
        tot["sections"] += len(b["sections"])
        tot["entries"] += ents
    tot.update(groups=kinds["group"], notes=kinds["note"], footnotes=kinds["footnote"])
    print("합계:", tot)
    st = Counter(p["state"] for e in pairing["entries"] for p in e["placements"])
    summ = pairing_summary(pairing)
    print("색인 항목 단위:", summ["counts"], "· 배치 철자:", summ["placements_spelling"])
    print("색인 배치 짝:", dict(st), "· Tafel 대조 어긋남", len(diffs))
    if args.dry_run:
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "schmidt_ocr.json").write_text(json.dumps(
        {"atlas": "schmidt", "source": "ocr", "totals": tot, "sequence_checks": seq, "bands": bands}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "schmidt_tafel_diffs.json").write_text(json.dumps(diffs, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "schmidt_index_pairing.json").write_text(json.dumps(pairing, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "schmidt_index_pairing.json").write_text(json.dumps({**pairing, "summary": summ}, ensure_ascii=False, indent=1), encoding="utf-8")
    write_pairing_md(OUT_DIR / "schmidt_index_pairing.md", pairing, summ)
    write_md(OUT_DIR / "schmidt_descriptions.md", bands)
    print("→", OUT_DIR)
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
