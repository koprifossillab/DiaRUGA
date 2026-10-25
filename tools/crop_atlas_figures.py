#!/usr/bin/env python3
"""한국 도감 도판에서 그림을 항목 번호별로 잘라낸다 (240).

    W=/tmp/kor-crops                       # 작업 자리 (크롭·대조 시트·보고)
    python tools/crop_atlas_figures.py labels --work $W                 # 호스트
    deploy/host/... 아님 — 아래 docker 한 줄로 ocr · cut 을 돈다
    python tools/crop_atlas_figures.py publish --work $W [--apply]      # 호스트

`ocr`·`cut` 은 cv2 가 필요해 파이프라인 이미지에서 돈다(호스트 venv 에는 없다).
경로를 컨테이너 안팎에서 같게 물리면 명령을 그대로 옮겨 쓸 수 있다:

    docker run --rm --user $(id -u):$(id -g) \\
        -v /data3/DiaRUGA/atlas:/data3/DiaRUGA/atlas:ro -v $PWD:$PWD:ro -v $W:$W \\
        -w $PWD koprifossillab/diaruga-pipeline:v0.5.3 \\
        python tools/crop_atlas_figures.py cut --work $W

## 왜 `crop_plates.py` 를 안 쓰나

`crop_plates.py`(161)는 **상자마다 그림 번호를 사람이 적는다**(`ASSIGN`). 논문은
그림 번호와 학명의 짝을 캡션에서 따로 옮겨야 해서 그럴 수밖에 없었다. 한국 도감은
**그림 번호가 곧 항목 번호(169–680)이고 그림 바로 아래에 찍혀 있다** — 번호의
좌표만 알면 짝이 정해진다. 사람은 기계가 틀린 자리만 고친다.

## 단계

1. **`labels`** — 그림 번호의 좌표. PDF 41–190 은 텍스트 레이어에 있다
   (`pdftotext -bbox`). 같은 줄의 숫자 조각(`40 3`)은 잇고, 마침표 붙은 번호는
   **쪽 아래에 몰린 것만** 캡션으로 친다(`405.` 하나가 쪽 가운데에 찍혀 캡션 윗변이
   쪽 한가운데로 잡힌 적이 있다)
2. **`ocr`** — 텍스트 레이어가 없는 쪽(191–269, 16쪽). 사내 OCR 서버는 좌표를
   **블록 단위**로만 줘서(P21 · 175) 번호 하나하나를 못 짚는다. 대신 1단계 쪽의
   번호 상자에서 숫자 견본(0–9)을 떼어 **상관계수로 읽는다.** 진짜 번호는 글자마다
   0.77 이상, 그림 속 줄무늬는 0.30 이하라 갈림이 깨끗하다(문턱 0.6)
3. **`cut`** — 잉크 덩어리를 번호에 붙인다:
   - 번호가 덩어리 상자 **안**에 있으면 그것(Chaetoceros 는 강모 사이에 번호를 찍는다)
   - 아니면 **아래쪽** 가장 가까운 번호(가로 여유 30pt)
   - 번호가 둘 걸린 덩어리는 팽창을 줄여 다시 가른다(닿은 원 셋이 하나가 됐다)
   - 그림 상자 안에 통째로 든 주인 없는 조각은 그 그림의 속 무늬다
   - 크롭에서 **남의 번호에 붙은 잉크와 남의 번호 글자는 흰색으로 지운다**
4. **`publish`** — 크롭을 `Diadiction/plate/plate_korean_pl<N>_fig<번호>_<학명>.png`
   로 둔다(논문 도판과 같은 관례 · 다음 사람이 `plate/` 에서 찾는다). `<N>` 은
   **그림이 실제로 놓인 도판**이다 — 색인의 `pl.` 가 틀린 자리가 있다(`korean_pages.toml`
   의 `[plate_fix]`). 뷰어 쪽 복사는 `sync_paper_plate_images.py` 가 한다

## 사람이 고친 것 — `atlas/korean_crop_fixes.toml`

기계가 틀린 자리만 적는다. 쪽(PDF 쪽 번호)마다 `fix` 목록과 `note`:

- `[x, y, "번호"]` — 그 점의 덩어리를 그 번호로. `"-"` 면 버린다(**주인을 모를 때
  틀리게 붙이는 것보다 낫다**)
- `[x0, y0, x1, y1, "번호"]` — 사각형 안의 잉크를 떼어 그 번호로(닿아서 끝까지 안
  갈린 그림 · 텍스트 레이어가 번호를 놓친 그림)

좌표는 **PDF 포인트, 왼쪽 위 원점**이다(`pdftotext -bbox` 와 같다). 대조 시트를
보고 짚는다 — 시트는 높이 1400 이라 `pt = 시트값 × 716.16 / 1400`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PDF = Path("/nfs/temp-share/DiaRUGA/Diadiction/origin/korean_flora_diatom.pdf")
PLATE_DIR = Path("/nfs/temp-share/DiaRUGA/Diadiction/plate")
ATLAS_ROOT = Path(os.environ.get("DIARUGA_ATLAS_ROOT", "/data3/DiaRUGA/atlas"))
PAGE_PNG = ATLAS_ROOT / "korean" / "main"
KOREAN_JSON = REPO / "atlas" / "korean.json"
KR_PAGES = REPO / "atlas" / "korean_pages.toml"
FIXES = REPO / "atlas" / "korean_crop_fixes.toml"

PW, PH = 497.28, 716.16          # 쪽 크기 (pt)
NUM = re.compile(r"[1-7]\d\d\.?")
SHEET_H = 1400                   # 대조 시트 높이


def plate_pages() -> dict[int, int]:
    """도판 → PDF 쪽 (`korean_pages.toml` 의 [plates])."""
    import tomllib
    d = tomllib.loads(KR_PAGES.read_text(encoding="utf-8"))
    return {int(k): v for k, v in d["plates"].items()}


def korean_items() -> tuple[dict[str, str], dict[str, set[str]]]:
    """항목 번호 → 이름, 쪽 → 색인이 그 쪽에 두는 번호들."""
    d = json.loads(KOREAN_JSON.read_text(encoding="utf-8"))
    names, where = {}, {}
    for e in d["entries"]:
        names[e["item_no"]] = e["name"]
        for p in e["placements"]:
            if p.get("pdf_plate_page"):
                where.setdefault(str(p["pdf_plate_page"]), set()).add(e["item_no"])
    return names, where


# ───────────────────────────────────────────────────────── 1. labels (호스트)

def cmd_labels(work: Path) -> int:
    pages = sorted({int(p) for p in plate_pages().values()})
    out, empty = {}, []
    for p in pages:
        x = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-bbox", str(PDF), "-"],
                           capture_output=True, text=True, check=True).stdout
        words = [[float(a), float(b), float(c), float(d), w] for a, b, c, d, w in re.findall(
            r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<', x)]
        # 같은 줄에서 붙어 있는 숫자 조각을 잇는다 (`40 3` → 403, `22 0` → 220)
        # **텍스트 레이어에 쪽 한 구석을 통째로 덮는 가짜 글자 상자가 있다**
        # (p93 은 14–298 × 83–345pt). 글자 상자 안의 잉크는 크롭 단계가 지우므로
        # 그대로 두면 그림 반쪽이 예외 없이 사라진다(277). 글자는 20pt 를 안 넘는다
        words = [w for w in words if w[3] - w[1] <= 20]
        merged, used = [], set()
        for i, a in enumerate(words):
            if i in used:
                continue
            if re.fullmatch(r"\d{1,2}", a[4]):
                for j, b in enumerate(words):
                    if j != i and j not in used and re.fullmatch(r"\d{1,2}\.?", b[4]) \
                       and abs(a[1] - b[1]) < 3 and 0 <= b[0] - a[2] < 7 \
                       and NUM.fullmatch(a[4] + b[4]):
                        a = [a[0], min(a[1], b[1]), b[2], max(a[3], b[3]), a[4] + b[4]]
                        used.add(j)
                        break
            merged.append(a)
        if not any(NUM.fullmatch(w[4]) for w in merged):
            empty.append(p)              # 텍스트 레이어가 없다 — 2단계 몫
            continue
        dotted = [w for w in merged if re.fullmatch(r"[1-7]\d\d\.", w[4])]
        bottom = max((w[1] for w in dotted), default=PH)
        cap_top = min((w[1] for w in dotted if w[1] >= bottom - 120), default=PH)
        labels = [w[:4] + [w[4].rstrip(".")] for w in merged
                  if NUM.fullmatch(w[4]) and w[1] < cap_top - 2]
        out[str(p)] = dict(w=PW, h=PH, labels=labels, cap_top=cap_top,
                           words=[w[:4] for w in merged])
    work.mkdir(parents=True, exist_ok=True)
    (work / "labels_text.json").write_text(json.dumps(out))
    (work / "pages_ocr.txt").write_text(",".join(map(str, empty)))
    print(f"텍스트 레이어 {len(out)}쪽 → labels_text.json · 없는 {len(empty)}쪽 → ocr 단계")
    return 0


# ─────────────────────────────────────────────────── 2. ocr (컨테이너 · cv2)

def cmd_ocr(work: Path) -> int:
    import cv2
    import numpy as np

    TW, TH, THR = 20, 28, 160

    def page(p):
        im = cv2.imread(str(PAGE_PNG / f"p{int(p):04d}.png"), cv2.IMREAD_GRAYSCALE)
        return im, im.shape[1] / PW

    def comps(ink):
        n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
        return lab, [tuple(int(v) for v in st[i]) + (i,) for i in range(1, n)]

    def norm(lab, c):
        x, y, w, h, _, i = c
        ids = list(i) if isinstance(i, frozenset) else [i]
        g = np.isin(lab[y:y + h, x:x + w], ids).astype(np.float32)
        g = cv2.resize(g, (TW, TH), interpolation=cv2.INTER_AREA)
        g -= g.mean()
        n = np.linalg.norm(g)
        return g / n if n else g

    # 견본 — 텍스트 레이어 쪽의 번호 상자를 글자 셋으로 가른 것
    T = json.loads((work / "labels_text.json").read_text())
    samples: dict[str, list] = {str(d): [] for d in range(10)}
    gh = []
    for p, d in T.items():
        im, s = page(p)
        ink = (im < THR).astype(np.uint8)
        for x0, y0, x1, y1, w in d["labels"]:
            X0, Y0, X1, Y1 = int(x0 * s) - 3, int(y0 * s) - 3, int(x1 * s) + 3, int(y1 * s) + 3
            sub = ink[Y0:Y1, X0:X1].copy()
            lab, cs = comps(sub)
            cs = sorted([c for c in cs if c[3] > 0.35 * (Y1 - Y0)], key=lambda c: c[0])
            if len(cs) != 3:
                continue
            for c, ch in zip(cs, w):
                samples[ch].append(norm(lab, c))
                gh.append(c[3] / s)
    HM = float(np.median(gh))                       # 글자 높이 (pt)
    TPL = [(k, v) for k, vs in samples.items() for v in vs]
    print("견본", {k: len(v) for k, v in samples.items()}, f"글자 높이 {HM:.2f}pt")

    def read(g):
        best: dict[str, float] = {}
        for k, v in TPL:
            best[k] = max(best.get(k, -1.0), float((g * v).sum()))
        r = sorted(best.items(), key=lambda kv: -kv[1])
        return r[0][0], r[0][1]

    out = {}
    pages = [p for p in (work / "pages_ocr.txt").read_text().strip().split(",") if p]
    for p in pages:
        im, s = page(p)
        ink = (im < THR).astype(np.uint8)
        lab, cs = comps(ink)
        area = {c[5]: c[4] for c in cs}
        hmin, hmax = 0.8 * HM * s, 1.2 * HM * s
        # 끊긴 글자(5 의 윗줄)를 잇는다 — 가로로 겹치고 세로로 붙은 조각
        pcs = sorted([c[:5] + (frozenset([c[5]]),) for c in cs
                      if c[3] <= hmax and c[2] <= 2.0 * HM * s and c[4] >= 4], key=lambda c: c[0])
        par = list(range(len(pcs)))
        bb = [list(c[:4]) for c in pcs]

        def root(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(len(pcs)):
            for j in range(i + 1, len(pcs)):
                if pcs[j][0] > pcs[i][0] + pcs[i][2]:
                    break
                ri, rj = root(i), root(j)
                if ri == rj:
                    continue
                a, b = bb[ri], bb[rj]
                ov = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
                vg = max(a[1], b[1]) - min(a[1] + a[3], b[1] + b[3])
                y0, y1 = min(a[1], b[1]), max(a[1] + a[3], b[1] + b[3])
                x0, x1 = min(a[0], b[0]), max(a[0] + a[2], b[0] + b[2])
                if ov >= 0.6 * min(a[2], b[2]) and vg <= 0.3 * HM * s \
                   and y1 - y0 <= hmax and x1 - x0 <= 0.95 * HM * s:
                    par[rj] = ri
                    bb[ri] = [x0, y0, x1 - x0, y1 - y0]
        grp: dict[int, list] = {}
        for i, c in enumerate(pcs):
            g = grp.setdefault(root(i), [0, frozenset()])
            g[0] += c[4]
            g[1] = g[1] | c[5]
        pcs = [tuple(bb[r]) + (g[0], g[1]) for r, g in grp.items()]
        # 붙어 버린 두 글자 — 폭이 두 배쯤인 덩어리를 가운데의 가장 얇은 세로줄에서 가른다
        for c in [c for c in pcs if hmin <= c[3] <= hmax and 0.95 * HM * s < c[2] <= 2.0 * HM * s]:
            x, y, w, h, a, ids = c
            col = np.isin(lab[y:y + h, x:x + w], list(ids)).sum(0)
            lo, hi = int(0.3 * w), int(0.7 * w)
            cut = lo + int(np.argmin(col[lo:hi]))
            pcs.append((x, y, cut, h, a, ids | {-1}))
            pcs.append((x + cut, y, w - cut, h, a, ids | {-2}))
        glyph = sorted([c for c in pcs if hmin <= c[3] <= hmax and 0.08 * HM * s <= c[2] <= 0.95 * HM * s],
                       key=lambda c: c[0])
        dots = [c for c in cs if c[3] <= 0.3 * HM * s and c[2] <= 0.3 * HM * s and c[4] >= 4]
        used, groups = set(), []
        for c in glyph:
            if c[5] in used:
                continue
            g = [c]
            while True:
                last, nxt = g[-1], None
                for d in glyph:
                    if d[5] in used or d in g:
                        continue
                    gap = d[0] - (last[0] + last[2])
                    if -2 <= gap <= 0.6 * HM * s and abs((d[1] + d[3]) - (last[1] + last[3])) <= 0.15 * HM * s:
                        if nxt is None or d[0] < nxt[0]:
                            nxt = d
                if nxt is None:
                    break
                g.append(nxt)
            if len(g) == 3:
                used.update(d[5] for d in g)
                groups.append(g)
        recs = []
        for g in groups:
            r = [read(norm(lab, c)) for c in g]
            x0 = min(c[0] for c in g); y0 = min(c[1] for c in g)
            x1 = max(c[0] + c[2] for c in g); y1 = max(c[1] + c[3] for c in g)
            per = any(0 <= d[0] - x1 <= 0.5 * HM * s and abs((d[1] + d[3]) - y1) <= 0.2 * HM * s
                      for d in dots)
            recs.append(dict(box=[x0 / s, y0 / s, x1 / s, y1 / s], txt="".join(k for k, _ in r),
                             score=min(v for _, v in r), ids=set().union(*(c[5] for c in g)), period=per))
        py = sorted(c["box"][1] for c in recs if c["period"])
        cap_top = min((y for y in py if y >= py[-1] - 90), default=PH) if py else PH

        def isolated(rec, m=0.4):
            # 둘레에 다른 잉크가 있으면 그림 속 줄무늬다
            b = [int(v * s) for v in rec["box"]]
            mm = int(m * HM * s)
            win = lab[max(0, b[1] - mm):b[3] + mm, max(0, b[0] - mm):b[2] + mm]
            return all(i == 0 or i in rec["ids"] or area[i] < 30 for i in np.unique(win))
        # 머리줄(y<80pt)의 "Pla" 가 810 으로 읽힌 적이 있다
        labels = [r for r in recs if 80 < r["box"][1] < cap_top - 2 and r["score"] >= 0.6 and isolated(r)]
        caps = [r for r in recs if r["box"][1] >= cap_top - 2]
        # 글자 상자(words) — 크롭이 글자를 그림 조각으로 잡지 않게. 둘레가 빈 글자 묶음만
        small = sorted([c for c in cs if c[3] <= 1.3 * HM * s and c[2] <= 1.3 * HM * s and c[4] >= 6],
                       key=lambda c: c[0])
        bigs = [c for c in cs if c[3] > 5 * HM * s]
        seen, words = set(), []
        for c in small:
            if c[5] in seen:
                continue
            g = [c]
            seen.add(c[5])
            grew = True
            while grew:
                grew = False
                gx0 = min(e[0] for e in g); gx1 = max(e[0] + e[2] for e in g)
                gy0 = min(e[1] for e in g); gy1 = max(e[1] + e[3] for e in g)
                for d in small:
                    if d[5] not in seen and gx0 - 0.5 * HM * s <= d[0] <= gx1 + 0.5 * HM * s \
                       and d[1] < gy1 + 0.2 * HM * s and d[1] + d[3] > gy0 - 0.2 * HM * s:
                        g.append(d); seen.add(d[5]); grew = True
            gx0 = min(e[0] for e in g); gx1 = max(e[0] + e[2] for e in g)
            gy0 = min(e[1] for e in g); gy1 = max(e[1] + e[3] for e in g)
            if gy1 - gy0 < 0.4 * HM * s:
                continue
            m = int(0.35 * HM * s)
            win = lab[max(0, gy0 - m):gy1 + m, max(0, gx0 - m):gx1 + m]
            if {i for i in set(np.unique(win)) - {0} - {e[5] for e in g} if area[i] >= 30}:
                continue
            if any(b[0] <= gx0 and gx1 <= b[0] + b[2] and b[1] <= gy0 and gy1 <= b[1] + b[3] for b in bigs):
                continue
            words.append([gx0 / s, gy0 / s, gx1 / s, gy1 / s])
        # 머리줄 "Plate NN" 을 한 상자로
        hd = sorted([c for c in cs if (c[1] + c[3]) < 85 * s and 0.8 * HM * s <= c[3] <= 2 * HM * s
                     and c[2] < 3 * HM * s and c[4] >= 30], key=lambda c: c[0])
        best: list = []
        for i, c0 in enumerate(hd):
            g = [c0]
            for d in hd[i + 1:]:
                if d[0] - (g[-1][0] + g[-1][2]) > 5 * HM * s:
                    break
                if abs((d[1] + d[3]) - (c0[1] + c0[3])) <= 0.4 * HM * s:
                    g.append(d)
            if len(g) > len(best):
                best = g
        if len(best) >= 4:
            words.append([min(c[0] for c in best) / s, min(c[1] for c in best) / s,
                          max(c[0] + c[2] for c in best) / s, max(c[1] + c[3] for c in best) / s])
        words += [r["box"] for r in labels + caps]
        out[p] = dict(w=PW, h=PH, labels=[r["box"] + [r["txt"]] for r in labels],
                      cap_top=cap_top, words=words)
        print(f"p{p} 번호 {len(labels)}")
    (work / "labels_ocr.json").write_text(json.dumps(out))
    return 0


# ─────────────────────────────────────────────────── 3. cut (컨테이너 · cv2)

GROW, THR, MARGIN_PT, MIN_AREA, PAD = 15, 200, 30, 1500, 24


def cmd_cut(work: Path, only: list[str] | None) -> int:
    import cv2
    import numpy as np

    names, where = korean_items()
    L = {}
    for f in ("labels_text.json", "labels_ocr.json"):
        if (work / f).exists():
            L.update(json.loads((work / f).read_text()))
    import tomllib
    FX = tomllib.loads(FIXES.read_text(encoding="utf-8")) if FIXES.exists() else {}
    (work / "crops").mkdir(exist_ok=True)
    (work / "sheets").mkdir(exist_ok=True)
    report, bad = {}, 0
    for p in sorted(L, key=int):
        if only and p not in only:
            continue
        d = L[p]
        fixes = FX.get(p, {}).get("fix", [])
        im = cv2.imread(str(PAGE_PNG / f"p{int(p):04d}.png"), cv2.IMREAD_GRAYSCALE)
        H, W = im.shape
        s = W / d["w"]
        ink = (im < THR).astype(np.uint8)
        ink[int((d["cap_top"] - 4) * s):, :] = 0
        for x0, y0, x1, y1 in d["words"]:
            ink[max(0, int(y0 * s) - 3):int(y1 * s) + 3, max(0, int(x0 * s) - 3):int(x1 * s) + 3] = 0
        labs = [(w, (x0 + x1) / 2 * s, y0 * s, y1 * s) for x0, y0, x1, y1, w in d["labels"]]

        def claims(x, y, w_, h_):
            return sum(1 for _, lx, ly, _ in labs if x <= lx <= x + w_ and y <= ly <= y + h_ + 30 * s)

        # 덩어리 — 번호가 둘 이상 걸린 덩어리는 팽창을 줄여 다시 가른다 (15 → 7 → 3 → 1)
        lab = np.zeros(ink.shape, np.int32)
        nxt = 1
        todo = [(np.ones(ink.shape, bool), GROW)]
        while todo:
            region, g = todo.pop()
            sub = (ink.astype(bool) & region).astype(np.uint8)
            blob = cv2.dilate(sub, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (g, g))) if g > 1 else sub
            blob &= region.astype(np.uint8)
            n_, lab_, st_, _ = cv2.connectedComponentsWithStats(blob, 8)
            for i in range(1, n_):
                x, y, w_, h_, a = st_[i]
                m = lab_ == i
                if g > 1 and a >= MIN_AREA and claims(x, y, w_, h_) >= 2:
                    todo.append((m, g // 2 if g > 3 else 1))
                    continue
                lab[m] = nxt
                nxt += 1
        # 오려내기 — 사람이 사각형으로 떼어 낸 잉크는 새 덩어리
        carved = {}
        for f in fixes:
            if len(f) != 5:
                continue
            X0, Y0, X1, Y1 = (int(v * s) for v in f[:4])
            m = np.zeros(ink.shape, bool)
            m[Y0:Y1, X0:X1] = True
            m &= lab > 0
            if not m.any():
                raise SystemExit(f"p{p} 오려내기 {f} 에 잉크가 없다")
            lab[m] = nxt
            carved[nxt] = f[4]
            nxt += 1
        st = np.zeros((nxt, 5), np.int64)
        for i in range(1, nxt):
            ys, xs = np.nonzero(lab == i)
            if len(xs):
                st[i] = [xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1, len(xs)]

        groups: dict[str, list[int]] = {}
        orphan: list[int] = []
        for i in range(1, nxt):
            x, y, w_, h_, a = st[i]
            if a < MIN_AREA or i in carved:
                continue
            if (x < 0.03 * W or x + w_ > 0.97 * W) and w_ < 0.03 * W:
                continue                                   # 스캔 테두리
            inside = [(abs(ly - (y + h_)) + 0.5 * abs(lx - (x + w_ / 2)), w) for w, lx, ly, _ in labs
                      if x <= lx <= x + w_ and y <= ly <= y + h_]
            cand = inside or [(ly - (y + h_), w) for w, lx, ly, _ in labs
                              if ly >= y + h_ - 30 * s and x - MARGIN_PT * s <= lx <= x + w_ + MARGIN_PT * s]
            if cand:
                groups.setdefault(min(cand)[1], []).append(i)
            else:
                orphan.append(i)
        for i, w in carved.items():
            groups.setdefault(w, []).append(i)
        # 점 짚기 — 버린 덩어리는 따로 모은다. 상자가 번호 글자까지 넓어지면
        # 버린 그림이 다시 들어올 수 있어 크롭에서 지워야 한다(p209 의 544)
        dropped: list[int] = []
        for f in fixes:
            if len(f) != 3:
                continue
            X, Y = int(f[0] * s), int(f[1] * s)
            i = int(lab[Y, X])
            if not i:
                near = lab[max(0, Y - 40):Y + 40, max(0, X - 40):X + 40]
                ids = near[near > 0]
                if not len(ids):
                    raise SystemExit(f"p{p} 점 {f} 둘레에 덩어리가 없다")
                i = int(np.bincount(ids).argmax())
            for g in groups.values():
                if i in g:
                    g.remove(i)
            if i in orphan:
                orphan.remove(i)
            if f[2] != "-":
                groups.setdefault(f[2], []).append(i)
            else:
                dropped.append(i)
        groups = {w: g for w, g in groups.items() if g}
        # 덩어리를 못 받은 번호는 가장 가까운 고아를 받는다 (40pt 안)
        for w, lx, ly, _ in labs:
            if w in groups or not orphan:
                continue

            def gap(i):
                x, y, w_, h_ = st[i][:4]
                return np.hypot(max(x - lx, 0, lx - x - w_), max(y - ly, 0, ly - y - h_))
            b = min(orphan, key=gap)
            if gap(b) <= 40 * s:
                groups[w] = [b]
                orphan.remove(b)

        def bbox(ids):
            return (min(st[i][0] for i in ids), min(st[i][1] for i in ids),
                    max(st[i][0] + st[i][2] for i in ids), max(st[i][1] + st[i][3] for i in ids))
        # 그림 상자 안에 통째로 든 고아는 그 그림의 속 무늬다
        for i in list(orphan):
            x, y, w_, h_ = st[i][:4]
            for g in groups.values():
                X0, Y0, X1, Y1 = bbox(g)
                if X0 <= x and Y0 <= y and x + w_ <= X1 and y + h_ <= Y1:
                    g.append(i)
                    orphan.remove(i)
                    break

        sheet = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        rng = np.random.default_rng(int(p))
        made = []
        for w, ids in groups.items():
            x0, y0, x1, y1 = bbox(ids)
            t = next((t for t in labs if t[0] == w), None)
            if t:                                          # 번호도 크롭에 담는다
                _, lx, _, ly1 = t
                x0, x1, y1 = min(x0, lx - 40), max(x1, lx + 40), max(y1, ly1 + 4)
            x0, y0 = max(0, int(x0) - PAD), max(0, int(y0) - PAD)
            x1, y1 = min(W, int(x1) + PAD), min(H, int(y1) + PAD, int((d["cap_top"] - 3) * s))
            ours = w in names
            c = tuple(int(v) for v in rng.integers(0, 190, 3)) if ours else (150, 150, 150)
            cv2.rectangle(sheet, (x0, y0), (x1, y1), c, 6)
            cv2.putText(sheet, w, (x0 + 8, y0 + 64), cv2.FONT_HERSHEY_SIMPLEX, 2.2, c, 6)
            if not ours:
                continue                                   # 도감 밖 항목(159–166 등)
            crop = im[y0:y1, x0:x1].copy()
            theirs = [j for ww, g in groups.items() if ww != w for j in g] + dropped
            crop[np.isin(lab[y0:y1, x0:x1], theirs)] = 255
            for a0, b0, a1, b1, ww in d["labels"]:
                if ww != w:
                    crop[max(0, int(b0 * s) - 6 - y0):max(0, int(b1 * s) + 6 - y0),
                         max(0, int(a0 * s) - 6 - x0):max(0, int(a1 * s) + 6 - x0)] = 255
            cv2.imwrite(str(work / "crops" / f"p{int(p):04d}_{w}.png"), crop)
            made.append(w)
        for i in orphan:
            x, y, w_, h_, _ = st[i]
            cv2.rectangle(sheet, (int(x), int(y)), (int(x + w_), int(y + h_)), (0, 0, 255), 10)
        cv2.imwrite(str(work / "sheets" / f"p{int(p):04d}.jpg"),
                    cv2.resize(sheet, (W * SHEET_H // H, SHEET_H)))
        got = {w for w in (t[0] for t in labs) if w in names} | set(made)
        want = where.get(p, set())
        r = dict(made=sorted(made), empty=sorted(got - set(made)), orphans=len(orphan),
                 not_in_index=sorted(got - want), index_only=sorted(want - got))
        report[p] = r
        flag = r["empty"] or r["orphans"] or r["not_in_index"] or r["index_only"]
        bad += bool(r["empty"])
        print(f"p{p} 크롭 {len(made):2d}" + (f"  빈 {r['empty']}" if r["empty"] else "")
              + (f"  고아 {r['orphans']}" if r["orphans"] else "")
              + (f"  색인이 이 쪽에 안 둠 {r['not_in_index']}" if r["not_in_index"] else "")
              + (f"  색인만 {r['index_only']}" if r["index_only"] else "") + ("  <--" if flag else ""))
    (work / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    n = sum(len(r["made"]) for r in report.values())
    print(f"\n크롭 {n}개 · 대조 시트 {work / 'sheets'}")
    return 1 if bad else 0


# ───────────────────────────────────────────────────────── 4. publish (호스트)

def slug(name: str) -> str:
    """`crop_plates.slug` 와 같다 — 학명 표기는 지키고 기호만 걷는다."""
    s = name
    for a in "().,?":
        s = s.replace(a, "")
    s = re.sub(r"\s+", "_", s.strip())
    return re.sub(r"[^A-Za-z0-9_\-]", "", s)


def cmd_publish(work: Path, apply: bool) -> int:
    names, _ = korean_items()
    page_plate = {v: k for k, v in plate_pages().items()}
    plan = {}
    for f in sorted((work / "crops").glob("p*_*.png")):
        m = re.fullmatch(r"p(\d{4})_(\d{3})\.png", f.name)
        page, item = int(m.group(1)), m.group(2)
        plate = page_plate[page]
        dest = PLATE_DIR / f"plate_korean_pl{plate}_fig{item}_{slug(names[item])}.png"
        if item in plan:
            raise SystemExit(f"{item} 이 두 쪽에 있다: {plan[item][0].name} · {f.name}")
        plan[item] = (f, dest)
    old = {p.name for p in PLATE_DIR.glob("plate_korean_pl*_fig*_*.png")}
    new = {d.name for _, d in plan.values()}
    print(f"크롭 {len(plan)}개 → {PLATE_DIR}  (새로 {len(new - old)} · 바뀜 {len(new & old)} · "
          f"남는 옛것 {len(old - new)})")
    for n in sorted(old - new)[:10]:
        print("  옛것(안 지운다 — 손으로 본다):", n)
    if not apply:
        print("(--apply 를 주면 쓴다)")
        return 0
    import shutil
    for src, dest in plan.values():
        shutil.copyfile(src, dest)
    print("썼다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["labels", "ocr", "cut", "publish"])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--only", help="쪽 몇만 (쉼표) — cut")
    ap.add_argument("--apply", action="store_true", help="publish 를 실제로 쓴다")
    a = ap.parse_args()
    if a.step == "labels":
        return cmd_labels(a.work)
    if a.step == "ocr":
        return cmd_ocr(a.work)
    if a.step == "cut":
        return cmd_cut(a.work, a.only.split(",") if a.only else None)
    return cmd_publish(a.work, a.apply)


if __name__ == "__main__":
    raise SystemExit(main())
