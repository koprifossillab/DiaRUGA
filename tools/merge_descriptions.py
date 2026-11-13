#!/usr/bin/env python3
"""한국 도감 기재문의 두 원본(텍스트 레이어 · OCR)을 항목마다 나란히 놓는다 (257).

    python tools/merge_descriptions.py            # korean_merged.json · korean_descriptions.md ·
                                                  # korean_name_diffs.json·.md 를 낸다
    python tools/merge_descriptions.py --dry-run  # 수만 센다

입력은 `tools/parse_descriptions.py` 가 낸 `korean_text.json` · `korean_ocr.json` 이다.
**어느 쪽이 맞다고 정하지 않는다** — 칸을 나란히 두고 `diff` 에 어긋난 정도를 수로만 적는다.

`diff` 는 기재문에서 **한글 · 숫자 · 단위(`μ` `~` `%` `°`)** 만 남기고 잰다. 학명(라틴 글자)과
한자는 일부러 뺀다 — 한자는 텍스트 레이어에서 깨지고, 학명은 OCR 이 그럴듯하게 틀리는
자리라 둘 다 "어느 쪽이 틀렸는가" 를 이 도구가 정할 수 없다. 칸마다:

| 키 | 뜻 |
|---|---|
| `hangul_ratio` | 한글 음절만 이어 붙여 `difflib` 로 잰 닮은 정도 (1.0 = 같다) |
| `digits_only_text` · `digits_only_ocr` | 숫자 토큰(`12`, `3.5`)이 한쪽에만 있는 것 (겹치는 만큼은 뺀다) |
| `mu_text` · `mu_ocr` | `μ`·`µ` 의 개수 |
| `cjk_text` · `cjk_ocr` | 한자의 개수 |
| `empty_paren_text` · `empty_paren_ocr` | 괄호 속이 통째로 빈 `()` 의 개수 (한자가 깨져 사라진 자리) |
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_worms import DIADICTION  # noqa: E402

OUT_DIR = DIADICTION / "outputs/descriptions"
INDEX = Path(__file__).resolve().parent.parent / "atlas/korean.json"

HANGUL = re.compile(r'[가-힣]')
KEEP = re.compile(r'[가-힣0-9.~μµ%°]')
NUM = re.compile(r'\d+(?:\.\d+)?')
MU = re.compile(r'[μµ]')
CJK = re.compile(r'[㐀-䶿一-鿿]')
EMPTY_PAREN = re.compile(r'\(\s*\)')
COLOR = re.compile(r'\[?〔?色圖\]?〕?')
FIELDS = ("description", "ecology", "distribution")


def side(e: dict | None) -> dict | None:
    if e is None:
        return None
    return {k: v for k, v in e.items() if k != "item_no"}


def diff_field(a: str, b: str) -> dict:
    ha, hb = "".join(HANGUL.findall(a)), "".join(HANGUL.findall(b))
    na, nb = collections.Counter(NUM.findall(a)), collections.Counter(NUM.findall(b))
    return {
        "len_text": len(a), "len_ocr": len(b),
        "hangul_text": len(ha), "hangul_ocr": len(hb),
        "hangul_ratio": round(difflib.SequenceMatcher(None, ha, hb, autojunk=False).ratio(), 4)
        if ha or hb else None,
        "digits_only_text": sorted((na - nb).elements()),
        "digits_only_ocr": sorted((nb - na).elements()),
        "mu_text": len(MU.findall(a)), "mu_ocr": len(MU.findall(b)),
        "cjk_text": len(CJK.findall(a)), "cjk_ocr": len(CJK.findall(b)),
        "empty_paren_text": len(EMPTY_PAREN.findall(a)), "empty_paren_ocr": len(EMPTY_PAREN.findall(b)),
    }


def fold(name: str) -> str:
    """표제 이름을 비교용으로 접는다 — 악센트·대소문자·기호·공백을 뺀다."""
    n = COLOR.sub("", name)
    n = unicodedata.normalize("NFKD", n)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', n.lower())


def name_kind(head: str, idx: str) -> str | None:
    """None = 같다. 아니면 어긋난 모양."""
    h, i = fold(head), fold(idx)
    if h == i:
        return None
    if i and h.startswith(i):
        return "index_shorter"      # 색인이 이름을 자른 자리 (`var.` 이하·저자)
    if h and i.startswith(h):
        return "heading_shorter"
    r = difflib.SequenceMatcher(None, h, i, autojunk=False).ratio()
    return "spelling" if r >= 0.85 else "different"


def build(text: dict, ocr: dict, index: dict) -> tuple[dict, list, list]:
    te = {e["item_no"]: e for e in text["entries"]}
    oe = {e["item_no"]: e for e in ocr["entries"]}
    items = []
    unassigned = []
    ocr_nos = sorted(oe, key=int)
    for ix in index["entries"]:
        n = ix["item_no"]
        t, o = te.get(n), oe.get(n)
        it = {"item_no": n, "name": ix["name"],
              "index_plate": (ix.get("placements") or [{}])[0].get("plate"),
              "text": side(t), "ocr": side(o)}
        if t and o:
            it["diff"] = {f: diff_field(t[f], o[f]) for f in FIELDS}
        items.append(it)
        if o is None:
            below = [m for m in ocr_nos if int(m) < int(n)]
            prev = oe[below[-1]] if below else None
            why = "OCR 에서 표제를 못 찾았다"
            if prev and prev["after"]:
                it["possible_in_after_of"] = prev["item_no"]
                why += f" — #{prev['item_no']} 의 `after`(쪽 {prev['after_pages']})에 이 항목의 본문이 들어 있을 수 있다"
            elif not prev or n == index["entries"][-1]["item_no"]:
                why += " — 발췌본이 이 앞에서 끝난다(색인 note)"
            unassigned.append({"item_no": n, "name": ix["name"], "source": "ocr", "reason": why})
        if t is None and int(n) <= 480:
            unassigned.append({"item_no": n, "name": ix["name"], "source": "text",
                               "reason": "텍스트 레이어에서 표제를 못 찾았다"})
    names = []
    for ix in index["entries"]:
        n = ix["item_no"]
        for src, e in (("text", te.get(n)), ("ocr", oe.get(n))):
            if e is None:
                continue
            k = name_kind(e["name_raw"], ix["name"])
            if k:
                names.append({"item_no": n, "source": src, "kind": k, "index_name": ix["name"],
                              "heading_name": e["name_raw"],
                              "syn_line": bool(re.search(r'\bSyn\.', e["name_raw"])),
                              "pdf_page": e["pdf_page"]})
    return {"items": items}, unassigned, names


def front_body(d: dict) -> list[dict]:
    """첫 항목 앞 줄 중 규조강 기재부터 (범례·목차·다른 문은 뺀다)."""
    fr = d["front"]
    for i, x in enumerate(fr):
        if "BACILLARIOPHYCEAE" in x["line"]:
            return fr[i:]
    return []


def summarize(items: list[dict]) -> dict:
    both = [it for it in items if it.get("diff")]
    agg: dict = {"both": len(both)}
    for f in FIELDS:
        rs = sorted(it["diff"][f]["hangul_ratio"] for it in both if it["diff"][f]["hangul_ratio"] is not None)
        if not rs:
            continue
        agg[f] = {
            "n": len(rs), "ratio_median": rs[len(rs) // 2], "ratio_min": rs[0],
            "ratio_lt_0.5": sum(r < 0.5 for r in rs), "ratio_lt_0.8": sum(r < 0.8 for r in rs),
            "ratio_ge_0.95": sum(r >= 0.95 for r in rs),
            "digits_differ": sum(1 for it in both if it["diff"][f]["digits_only_text"] or it["diff"][f]["digits_only_ocr"]),
            "mu_text": sum(it["diff"][f]["mu_text"] for it in both),
            "mu_ocr": sum(it["diff"][f]["mu_ocr"] for it in both),
            "cjk_text": sum(it["diff"][f]["cjk_text"] for it in both),
            "cjk_ocr": sum(it["diff"][f]["cjk_ocr"] for it in both),
            "empty_paren_text": sum(it["diff"][f]["empty_paren_text"] for it in both),
            "empty_paren_ocr": sum(it["diff"][f]["empty_paren_ocr"] for it in both),
        }
    return agg


def md_quote(s: str) -> str:
    return "> " + s.replace("\n", "\n> ") if s else "> (없음)"


def write_md(items: list[dict], text: dict, ocr: dict, path: Path) -> None:
    L = ["# 한국동식물도감 제9권 규조 — 형태 기재문 (OCR · 텍스트 레이어 나란히)", "",
         "`tools/merge_descriptions.py` 가 냈다. **어느 쪽이 맞다고 정하지 않았다** — 두 원본을 그대로 놓았다.",
         "OCR 은 `μ` 와 한자를 읽지만 학명·라벨 글자를 곧잘 틀리고(`[ầ錄]` 같은 것),",
         "텍스트 레이어(#169–480)는 한글이 성하지만 `μ` 가 빠지고 괄호 속 한자가 깨져 있다.",
         "제목은 색인(`atlas/korean.json`)의 이름이다. 표제 줄의 실제 글자는 `korean_name_diffs.md`.", ""]
    fo, ft = front_body(ocr), front_body(text)
    L += ["## 규조강 · 목 · 과의 첫 기재와 검색표 (첫 항목 앞)", "",
          "**OCR**", "", md_quote("\n".join(x["line"] for x in fo if x["line"].strip())), ""]
    if ft:
        L += ["**텍스트 레이어**", "", md_quote("\n".join(x["line"].strip() for x in ft if x["line"].strip())), ""]
    for it in items:
        t, o = it["text"], it["ocr"]
        L += [f"## {it['item_no']}. {it['name']}", ""]
        meta = [f"색인 도판 {it['index_plate']}"]
        if o:
            meta.append(f"OCR 쪽 {o['pdf_page']}" + (f" · 표제 pl. {o['plate']}" if o['plate'] is not None else " · 표제에 pl. 없음"))
        if t:
            meta.append(f"텍스트 쪽 {t['pdf_page']} · 표제 pl. {t['plate']}")
        if o and o["family_raw"]:
            meta.append(f"과: {o['family_raw']}")
        L += [" · ".join(meta), ""]
        if not o:
            L += [f"**OCR 에서 표제를 못 찾았다.**" + (f" #{it['possible_in_after_of']} 의 뒤에 이어진 글에 들어 있을 수 있다."
                  if it.get("possible_in_after_of") else " 발췌본에 본문이 없다."), ""]
        for label, e in (("OCR", o), ("텍스트 레이어", t)):
            if not e:
                continue
            L += [f"**{label} — 기재문**", "", md_quote(e["description"]), ""]
            for k, kk in (("ecology", "생태"), ("distribution", "분포")):
                if e[k]:
                    L += [f"- {label} {kk}: {e[k]}"]
            if e["ecology"] or e["distribution"]:
                L += [""]
            if e["after"]:
                L += [f"**{label} — 이 항목 뒤에 이어진 글 (쪽 {e['after_pages']}) — 다음 과·목의 기재·검색표**", "",
                      md_quote(e["after"]), ""]
        if it.get("diff"):
            d = it["diff"]["description"]
            L += [f"*기재문 한글 닮은 정도 {d['hangul_ratio']} · μ(텍스트/OCR) {d['mu_text']}/{d['mu_ocr']} · "
                  f"한자 {d['cjk_text']}/{d['cjk_ocr']}*", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def write_names_md(names: list[dict], path: Path) -> None:
    L = ["# 표제 이름이 색인과 다른 것", "",
         "`korean_merged.json` 과 같은 때에 `tools/merge_descriptions.py` 가 냈다. **색인도 원문도 고치지 않았다.**",
         "", "| 종류 | 뜻 |", "|---|---|",
         "| index_shorter | 표제 이름이 색인 이름으로 시작한다 — 색인이 뒤(`var.` 이하·저자)를 잘랐다 |",
         "| heading_shorter | 색인 이름이 표제 이름으로 시작한다 — 표제가 짧다(줄 나뉨으로 못 읽었을 수 있다) |",
         "| spelling | 닮았으나 철자가 다르다 (OCR·스캔 글자 오류 또는 원문 표기) |",
         "| different | 많이 다르다 — 쪽을 직접 봐야 한다 |", "",
         "`Syn.` 은 표제 이름 칸에 `Syn.` 줄이 딸려 들어온 것이다.", "",
         "| 번호 | 원본 | 종류 | Syn. | 색인 이름 | 표제 이름 | 쪽 |", "|---|---|---|---|---|---|---|"]
    for n in names:
        L.append(f"| {n['item_no']} | {n['source']} | {n['kind']} | {'●' if n['syn_line'] else ''} | "
                 f"{n['index_name']} | {n['heading_name']} | {n['pdf_page']} |".replace("\n", " "))
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    text = json.loads((OUT_DIR / "korean_text.json").read_text(encoding="utf-8"))
    ocr = json.loads((OUT_DIR / "korean_ocr.json").read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    body, unassigned, names = build(text, ocr, index)
    summ = summarize(body["items"])
    out = {"atlas": "korean", "sources": {"text": text["source"], "ocr": ocr["source"]},
           "summary": summ, "unassigned": unassigned, **body,
           "front_text": front_body(text), "front_ocr": front_body(ocr)}
    kinds = collections.Counter((n["source"], n["kind"]) for n in names)
    print(f"항목 {len(body['items'])} · 두 원본 다 있는 것 {summ['both']} · 못 가른 것 {len(unassigned)}")
    for f in FIELDS:
        if f in summ:
            print(f"  {f}: {summ[f]}")
    print("표제 이름이 색인과 다른 것:", dict(kinds), "· Syn. 줄", sum(n["syn_line"] for n in names))
    if args.dry_run:
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "korean_merged.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "korean_name_diffs.json").write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(body["items"], text, ocr, OUT_DIR / "korean_descriptions.md")
    write_names_md(names, OUT_DIR / "korean_name_diffs.md")
    print("→", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
