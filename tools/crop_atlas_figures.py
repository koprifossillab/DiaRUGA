#!/usr/bin/env python3
"""도감 도판에서 그림을 번호별로 잘라낸다 — 한국 도감(240) · Schmidt(241).

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

## Schmidt (`--book schmidt`, 241)

텍스트 레이어가 없다. 그림 번호는 CRNN 으로 읽고 사람이 327쪽을 다 보고 확정했다
(작업 자리의 `labels/<권>_<쪽>.json` — 이미지 픽셀). `cut` 이 한국 도감과 다른 것:

- **판 테두리** — 허프로 찾는다. 손으로 그어 기울고 끊긴 것이 있어서다. 같은 줄의 조각을
  묶어 쪽 길이의 55% 를 넘고 **양옆이 비어 있어야** 테두리다. 그림의 곧은 솔기·윤곽을
  지우면 그림이 쪼개진다. 머리글 밑줄 위는 통째로 지운다
- **번호 ↔ 그림은 하나씩 짝짓는다** — 번호 상자에서 덩어리의 잉크 픽셀까지 거리로 먼저
  짝짓고, 그 짝에서 "번호가 그림 상자의 어디에 놓이나" 를 쪽마다 배워 다시 짝짓는다.
  같은 권 안에서도 쪽마다 번호가 위·아래·옆으로 갈려 방향 규칙으로는 안 됐다
- 번호 상자는 이웃 글자까지 넓힌다(판독기가 두 자리 번호에 한 글자 폭 상자를 낸다)
- 크롭에서 **내 덩어리·내 번호 말고는 다 지운다**(흐린 남의 그림 조각이 주인 없이 남는다)
- `publish --book schmidt` 는 색인 자리(학명 · 쪽 · 그림 범위)마다 범위의 그림을 원 배율로
  이어 붙인 한 장을 낸다. 이름은 Tafel 대신 권·쪽(`b4p155`) — Tafel 은 OCR 이다(126)
- 사람 정정은 `atlas/schmidt_crop_fixes.toml`(색인 그림 표기의 OCR 오류 · 쪽지 지우기)

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
SCHMIDT_JSON = REPO / "atlas" / "schmidt.json"
SC_FIXES = REPO / "atlas" / "schmidt_crop_fixes.toml"
# 권마다 번호를 놓는 자리 — 검토자 넷이 쪽을 다 보고 적은 것. 기계가 쪽마다 판정한
# `side` 는 거의 다 mixed 로 나와(줄마다 높이가 들쭉날쭉) 안 쓴다
SC_SIDE = {"band1": "above+mixed",   # 위쪽 가장자리(왼쪽~오른쪽), 그림에 닿는 것이 많다
           "band2": "mixed",
           "band3": "below+mixed",   # 오른쪽 아래 모서리. 앞쪽 몇 쪽은 위·옆
           "band4": "below+mixed"}   # 바로 아래 가운데. 큰 판은 오른쪽 아래
SC_UNIT = 1.0                    # Schmidt 쪽의 거리 단위 (px) — 그림이 빽빽해 한국 도감처럼 1pt≈4px 로 잡으면 이웃을 삼킨다(155쪽: 5px 이면 47/66 · 1px 이면 66/66)

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
SC_GROW = 31


def load_pages(book: str, work: Path) -> list[dict]:
    """쪽마다 번호·글자 상자를 **이미지 픽셀**로 맞춰 하나의 모양으로 낸다.

    한국 도감은 PDF pt 로 적혀 있어(`labels_*.json` · 정정표) 여기서 픽셀로 바꾼다.
    Schmidt 는 처음부터 픽셀이다(`labels/<권>_<쪽>.json` · 텍스트 레이어가 없다).
    `u` 는 거리 문턱(30·40)의 한 단위가 몇 픽셀인가다 — 한국 도감의 1pt 에 맞춘다.
    """
    import tomllib
    out = []
    if book == "korean":
        names, where = korean_items()
        L = {}
        for f in ("labels_text.json", "labels_ocr.json"):
            if (work / f).exists():
                L.update(json.loads((work / f).read_text()))
        FX = tomllib.loads(FIXES.read_text(encoding="utf-8")) if FIXES.exists() else {}
        for p in sorted(L, key=int):
            d = L[p]
            png = PAGE_PNG / f"p{int(p):04d}.png"
            out.append(dict(key=p, png=png, tag=f"p{int(p):04d}", w=d["w"], cap_top=d["cap_top"],
                            words=d["words"], labels=[x[:5] for x in d["labels"]],
                            fixes=FX.get(p, {}).get("fix", []), side="below", frame=False,
                            names=names, want=where.get(p, set())))
        return out
    want = schmidt_figures()
    FX = tomllib.loads(SC_FIXES.read_text(encoding="utf-8")) if SC_FIXES.exists() else {}
    for f in sorted((work / "labels").glob("band*_*.json")):
        d = json.loads(f.read_text())
        band, page = d["page"].split("/")
        out.append(dict(key=d["page"], png=ATLAS_ROOT / "schmidt" / band / f"p{int(page):04d}.png",
                        tag=f"{band}_p{int(page):04d}", w=d["w"], cap_top=d["h"], u=SC_UNIT,
                        # 번호 글자는 cut 이 상자를 넓힌 뒤에 잉크에서 뺀다(`widen_labels`)
                        words=d.get("junk", []) + FX.get(d["page"], {}).get("junk", []),
                        labels=[x[:5] for x in d["labels"]],
                        fixes=FX.get(d["page"], {}).get("fix", []), side=SC_SIDE[band],
                        frame=True, names=None, want=want.get(d["page"], set())))
    return out


def schmidt_figures() -> dict[str, set[str]]:
    """쪽("band4/155") → 색인이 그 쪽에서 부르는 그림 번호 (범위를 편 것)."""
    d = json.loads(SCHMIDT_JSON.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for e in d["entries"]:
        for p in e["placements"]:
            if p["figures"] and p["pdf_plate_page"]:
                out.setdefault(f"{p['volume'].lower()}/{p['pdf_plate_page']}", set()).update(
                    figure_numbers(p["figures"]))
    return out


def fsafe(w: str) -> str:
    """번호 → 파일 이름 조각. Schmidt 의 변형 그림 `22*` 의 별표는 NAS(SMB)가 못 받는다."""
    return w.replace("*", "s")


def figure_numbers(s: str) -> list[str]:
    """색인의 그림 표기 → 번호들. `1—8` · `21, 22` · `54.55`(OCR 이 쉼표를 마침표로 읽었다) · `6b`."""
    out = []
    for part in re.split(r"[,;.]\s*", s):
        part = part.strip()
        if m := re.fullmatch(r"(\d+)\s*[—–-]\s*(\d+)", part):
            out += [str(i) for i in range(int(m[1]), int(m[2]) + 1)]
        elif m := re.fullmatch(r"[—–-]?\s*(\d+[a-z]?\*?)", part):
            out.append(m[1])
    return out


def widen_labels(ink, labels: list) -> list:
    """번호 상자를 같은 줄의 이웃 글자까지 넓힌다 (Schmidt · 픽셀 좌표).

    판독기가 두 자리 번호에서 한 글자 폭 상자만 내는 일이 많다(band1 에서 2,444 중
    741). 값은 맞아도 나머지 글자가 잉크에 남아 남의 크롭에 들어간다. 상자와 겹치거나
    한 글자 폭 안에 있는, 높이가 비슷하고 같은 줄에 있는 잉크 조각을 붙인다.
    """
    import cv2
    out = []
    for lab_ in labels:
        x0, y0, x1, y1, w = lab_
        h = y1 - y0
        X0, Y0 = max(0, int(x0 - 1.4 * h)), max(0, int(y0 - 0.4 * h))
        X1, Y1 = int(x1 + 1.4 * h), int(y1 + 0.4 * h)
        n, _, st, _ = cv2.connectedComponentsWithStats(ink[Y0:Y1, X0:X1], 8)
        a0, b0, a1, b1 = x0, y0, x1, y1
        for i in range(1, n):
            cx, cy, cw, ch, area = st[i]
            gx0, gy0 = X0 + cx, Y0 + cy
            if area < 12 or ch > 1.3 * h or ch < 0.7 * h or cw > 1.0 * h:
                continue                                   # 글자 높이가 아니다 — 그림 선·줄무늬
            if min(y1, gy0 + ch) - max(y0, gy0) < 0.7 * ch:
                continue                                   # 같은 줄이 아니다
            if gx0 + cw < x0 - 0.35 * h or gx0 > x1 + 0.35 * h:
                continue                                   # 글자 사이 간격보다 멀다
            mx, my = gx0 + cw / 2, gy0 + ch / 2
            if any(o is not lab_ and o[0] <= mx <= o[2] and o[1] <= my <= o[3] for o in labels):
                continue                                   # 이웃 번호의 글자다
            a0, b0, a1, b1 = min(a0, gx0), min(b0, gy0), max(a1, gx0 + cw), max(b1, gy0 + ch)
        out.append([a0, b0, a1, b1, w])
    return out


def cmd_cut(work: Path, only: list[str] | None, book: str) -> int:
    import cv2
    import numpy as np

    (work / "crops").mkdir(exist_ok=True)
    (work / "sheets").mkdir(exist_ok=True)
    report, bad = {}, 0
    for d in load_pages(book, work):
        p = d["key"]
        if only and p not in only:
            continue
        fixes = d["fixes"]
        im = cv2.imread(str(d["png"]), cv2.IMREAD_GRAYSCALE)
        H, W = im.shape
        s = W / d["w"]                                     # 적힌 좌표 → 픽셀
        u = d.get("u", s)                                  # 거리 문턱의 단위 (한국 도감 1pt)
        ink = (im < THR).astype(np.uint8)
        ink[int((d["cap_top"] - 4) * s):, :] = 0
        if d["frame"]:
            # 판 테두리 (Schmidt). 스캔이 기울어 한 줄로 곧게 안 잡힌다 — 120px 짜리 직선
            # 조각을 찾아 잇고, **쪽 길이의 1/3 넘게 이어진 것만** 테두리로 친다.
            # 규조 껍질의 곧은 윤곽도 조각으로는 걸리지만 그렇게 길지 않다
            # 판 테두리 (Schmidt). 손으로 그어 기울고 끊긴 것(band3)이 있어 형태학 직선
            # 검출로는 안 잡힌다 — 허프로 찾고 **쪽 길이의 55% 를 넘는** 가로·세로선만 친다.
            # 점묘 그림의 곧은 솔기(raphe)가 쪽 높이의 절반 가까이 뻗어, 그보다 짧게 잡거나
            # "가장자리 띠" 로 받으면 그림이 반으로 쪼개졌다(band3/11). 반 해상도에서 찾는다
            # 줄일 때 평균을 내면 1px 테두리가 흐려져 놓친다(band1/161) — 팽창 뒤 솎는다
            half = cv2.dilate(ink, np.ones((3, 3), np.uint8))[::2, ::2]
            segs = cv2.HoughLinesP(half * 255, 1, np.pi / 720, threshold=200,
                                   minLineLength=int(0.125 * min(H, W)), maxLineGap=20)
            frame = np.zeros_like(ink)
            top = None
            # 끊긴 테두리는 0.3–0.4 짜리 조각으로 나온다(band1/161) — 같은 줄(30px 안)에
            # 늘어선 조각을 묶어 덮는 길이를 더한다. 묶음은 쪽 바깥 15% 띠 안에서만 —
            # 위아래로 쌓인 그림의 솔기도 한 줄에 선다
            def lonely(cl, along):
                """테두리는 양옆이 비어 있다 — 그림의 곧은 윤곽선은 한쪽에 무늬가 차 있다
                (band3/141 의 긴 그림 1 이 가장자리 띠에서 테두리로 지워졌다).
                선을 따라 20px 마다 양옆 8–40px 띠의 잉크 밀도를 잰다"""
                side_a, side_b = [], []
                for *_, (x1_, y1_, x2_, y2_) in cl:
                    n_ = max(2, int(np.hypot(x2_ - x1_, y2_ - y1_) / 20))
                    for k in range(n_):
                        cx, cy = int(x1_ + (x2_ - x1_) * k / n_), int(y1_ + (y2_ - y1_) * k / n_)
                        if along == 1:
                            side_a.append(ink[cy, max(0, cx - 40):max(0, cx - 8)].mean() if cx > 8 else 0)
                            side_b.append(ink[cy, cx + 8:cx + 40].mean() if cx + 8 < W else 0)
                        else:
                            side_a.append(ink[max(0, cy - 40):max(0, cy - 8), cx].mean() if cy > 8 else 0)
                            side_b.append(ink[cy + 8:cy + 40, cx].mean() if cy + 8 < H else 0)
                # 평균이 아니라 중앙값 — 그림이 테두리에 군데군데 닿아도 테두리다(band1/19·137)
                return max(np.median(side_a), np.median(side_b)) < 0.05

            lines = {0: [], 1: []}                          # 0 가로 · 1 세로
            for x1_, y1_, x2_, y2_ in (segs.reshape(-1, 4).tolist() if segs is not None else []):
                x1_, y1_, x2_, y2_ = 2 * x1_, 2 * y1_, 2 * x2_, 2 * y2_
                ang = abs(np.degrees(np.arctan2(y2_ - y1_, x2_ - x1_))) % 180
                if min(ang, 180 - ang) < 3:
                    lines[0].append(((y1_ + y2_) / 2, min(x1_, x2_), max(x1_, x2_), (x1_, y1_, x2_, y2_)))
                elif abs(ang - 90) < 3:
                    lines[1].append(((x1_ + x2_) / 2, min(y1_, y2_), max(y1_, y2_), (x1_, y1_, x2_, y2_)))
            for along, segs_ in lines.items():
                L_, O_ = (W, H)[along], (H, W)[along]
                segs_.sort()
                clusters: list[list] = []
                for sg in segs_:
                    if clusters and sg[0] - clusters[-1][-1][0] < 30:
                        clusters[-1].append(sg)
                    else:
                        clusters.append([sg])
                for cl in clusters:
                    pos = np.mean([c[0] for c in cl])
                    cover = np.zeros(L_ + 1, bool)
                    for _, a_, b_, _ in cl:
                        cover[max(0, int(a_)):int(b_) + 1] = True
                    longest = max(b_ - a_ for _, a_, b_, _ in cl)
                    edge = pos < 0.15 * O_ or pos > 0.85 * O_
                    if (longest > 0.55 * L_ or (edge and cover.sum() > 0.55 * L_)) and lonely(cl, along):
                        for *_, (x1_, y1_, x2_, y2_) in cl:
                            cv2.line(frame, (x1_, y1_), (x2_, y2_), 1, 13)
                        if along == 0 and pos < 0.12 * H:
                            top = int(min(c[0] for c in cl)) if top is None else min(top, int(min(c[0] for c in cl)))
            ink[frame > 0] = 0
            if top is not None:
                # 머리글("Dr. A. Schmidts Diatom.-Atlas")과 쪽 번호는 위쪽 긴 가로선 위에 있다
                ink[:top, :] = 0
        if d["frame"]:
            d = {**d, "labels": widen_labels(ink, d["labels"])}
            d["words"] = d["words"] + [x[:4] for x in d["labels"]]
        for x0, y0, x1, y1 in d["words"]:
            ink[max(0, int(y0 * s) - 3):int(y1 * s) + 3, max(0, int(x0 * s) - 3):int(x1 * s) + 3] = 0
        # 번호: (글자, 가운데 x, 윗변, 아랫변, 왼변, 오른변) — 픽셀
        labs = [(w, (x0 + x1) / 2 * s, y0 * s, y1 * s, x0 * s, x1 * s) for x0, y0, x1, y1, w in d["labels"]]
        # `below+mixed` — 그 권의 주된 방향에서 먼저 찾고, 없으면 가장 가까운 번호.
        # Schmidt 는 한 권 안에서도 쪽마다 번호를 놓는 자리가 달라 하나로는 안 된다
        # (band3: 앞쪽은 그림 위·옆, 빽빽한 뒤쪽은 그림 밑)
        side, _, fallback = d["side"].partition("+")
        M = MARGIN_PT * u

        def toward(x, y, w_, h_, t, side=side):
            """번호 t 가 덩어리의 `side` 쪽에 있으면 그 거리, 아니면 None.

            한국 도감은 늘 아래다(번호가 그림 바로 밑). Schmidt 는 권마다 다르다 —
            Band4 는 아래, Band1 은 왼쪽 위, Band2 는 옆이나 위(시제품)."""
            _, lx, ly0, ly1, lx0, lx1 = t
            ly = (ly0 + ly1) / 2
            near = 30 * u
            if side == "below":
                return ly0 - (y + h_) if ly0 >= y + h_ - near and x - M <= lx <= x + w_ + M else None
            if side == "above":
                return y - ly1 if ly1 <= y + near and x - M <= lx <= x + w_ + M else None
            if side == "left":
                return x - lx1 if lx1 <= x + near and y - M <= ly <= y + h_ + M else None
            if side == "right":
                return lx0 - (x + w_) if lx0 >= x + w_ - near and y - M <= ly <= y + h_ + M else None
            g = np.hypot(max(x - lx1, 0, lx0 - x - w_), max(y - ly1, 0, ly0 - y - h_))
            return g if g <= 3 * M else None                # mixed — 상자 사이 거리

        def claims(x, y, w_, h_):
            if d["frame"]:                                 # Schmidt — 상자 안에 든 번호를 센다
                return sum(1 for t in labs if x <= t[1] <= x + w_ and y <= (t[2] + t[3]) / 2 <= y + h_)
            if side == "below":
                return sum(1 for t in labs if x <= t[1] <= x + w_ and y <= t[2] <= y + h_ + 30 * u)
            return sum(1 for t in labs if (x <= t[1] <= x + w_ and y <= (t[2] + t[3]) / 2 <= y + h_)
                       or (toward(x, y, w_, h_, t) is not None and toward(x, y, w_, h_, t) <= 30 * u))

        def segment(g0):
            # 덩어리 — 번호가 둘 이상 걸린 덩어리는 팽창을 줄여 다시 가른다 (15 → 7 → 3 → 1)
            # 덩어리마다 쪽 전체를 훑지 않는다 — 통계는 연결 성분이 이미 낸다. Schmidt 쪽은
            # 무늬 점까지 덩어리가 수천 개라 `lab == i` 를 돌리면 한 쪽에 몇 분이 걸렸다
            lab = np.zeros(ink.shape, np.int32)
            stats = [np.zeros(5, np.int64)]
            nxt = 1
            todo = [(np.ones(ink.shape, bool), g0)]
            while todo:
                region, g = todo.pop()
                sub = (ink.astype(bool) & region).astype(np.uint8)
                blob = cv2.dilate(sub, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (g, g))) if g > 1 else sub
                blob &= region.astype(np.uint8)
                n_, lab_, st_, _ = cv2.connectedComponentsWithStats(blob, 8)
                to = np.zeros(n_, np.int32)
                for i in range(1, n_):
                    x, y, w_, h_, a = st_[i]
                    if g > 1 and a >= MIN_AREA and claims(x, y, w_, h_) >= 2:
                        todo.append((lab_ == i, g // 2 if g > 3 else 1))
                        continue
                    to[i] = nxt
                    stats.append(st_[i].astype(np.int64))
                    nxt += 1
                new_ = to[lab_]
                lab[new_ > 0] = new_[new_ > 0]
            # 오려내기 — 사람이 사각형으로 떼어 낸 잉크는 새 덩어리
            carved, touched = {}, set()
            for f in fixes:
                if len(f) != 5:
                    continue
                X0, Y0, X1, Y1 = (int(v * s) for v in f[:4])
                m = np.zeros(ink.shape, bool)
                m[Y0:Y1, X0:X1] = True
                m &= lab > 0
                if not m.any():
                    raise SystemExit(f"{p} 오려내기 {f} 에 잉크가 없다")
                touched |= set(np.unique(lab[m]).tolist())
                lab[m] = nxt
                stats.append(np.zeros(5, np.int64))
                touched.add(nxt)
                carved[nxt] = f[4]
                nxt += 1
            st = np.array(stats, np.int64)
            for i in touched:                                  # 오려내기가 깎은 덩어리만 다시 잰다
                ys, xs = np.nonzero(lab == i)
                st[i] = [xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1, len(xs)] \
                    if len(xs) else 0

            def near_blob(i, t):
                """번호 둘레 40px 안에 그 덩어리의 잉크가 실제로 있는가 (Schmidt).
                상자 안에 있다는 것만으로는 속 빈 덩어리(테두리·큰 고리)가 모든 번호를 먹는다"""
                cx, cy = int(t[1]), int((t[2] + t[3]) / 2)
                r = lab[max(0, cy - 40):cy + 40, max(0, cx - 40):cx + 40]
                return bool((r == i).any())

            def match_pass():
                """Schmidt — 번호와 덩어리를 **하나씩** 짝짓는다.

                쪽마다(같은 권 안에서도) 번호가 그림의 위·아래·옆으로 갈려, 방향 규칙은
                한 줄씩 밀려 붙거나(band3/9) 한 번호가 그림 둘을 받는다. 모든 (번호, 덩어리)
                짝을 상자 사이 거리로 늘어놓고 가까운 것부터 둘 다 비어 있을 때만 짝짓는다.
                짝 못 받은 덩어리(그림의 조각·부분 그림)는 가장 가까운 번호에 붙는다.
                """
                dropped: list[int] = []
                blobs = []
                for i in range(1, nxt):
                    x, y, w_, h_, a = st[i]
                    if a < MIN_AREA or i in carved:
                        continue
                    if (x < 0.03 * W or x + w_ > 0.97 * W) and w_ < 0.03 * W:
                        continue
                    if w_ > 0.5 * W and h_ > 0.5 * H and a < 0.05 * w_ * h_:
                        dropped.append(i)                      # 손으로 그린 판 테두리
                        continue
                    blobs.append(i)

                # 거리는 번호 상자에서 **그 덩어리의 잉크 픽셀까지**다. 상자 사이 거리로 재면
                # 마름모 그림의 빈 모서리에 찍힌 번호가 아래 그림을 더 가깝게 본다(band3/9)
                R = int(3 * M) + 1
                isblob = np.zeros(nxt + 1, bool)
                isblob[blobs] = True
                pairs = []
                for t in labs:
                    X0, Y0 = max(0, int(t[4]) - R), max(0, int(t[2]) - R)
                    win = lab[Y0:int(t[3]) + R, X0:int(t[5]) + R]
                    ys, xs = np.nonzero(isblob[win])
                    if not len(xs):
                        continue
                    dx = np.maximum(np.maximum(t[4] - (xs + X0), (xs + X0) - t[5]), 0)
                    dy = np.maximum(np.maximum(t[2] - (ys + Y0), (ys + Y0) - t[3]), 0)
                    ids = win[ys, xs]
                    best = np.full(nxt + 1, np.inf)
                    np.minimum.at(best, ids, np.hypot(dx, dy))
                    pairs += [(float(best[i]), int(i), t[0]) for i in np.flatnonzero(np.isfinite(best))]
                pairs.sort()
                near: dict[int, tuple[float, str]] = {}
                for c, i, w in pairs:
                    near.setdefault(i, (c, w))
                def greedy(pairs):
                    groups: dict[str, list[int]] = {}
                    taken: set[int] = set()
                    for c, i, w in pairs:
                        if i in taken or w in groups:
                            continue
                        groups[w] = [i]
                        taken.add(i)
                    return groups, taken
                groups, taken = greedy(pairs)
                # 두 번째 — 이 쪽의 배치를 배운다. 첫 짝에서 번호가 그림 상자의 어디쯤
                # (상자 기준 상대 좌표)에 놓이는지 중앙값을 내고, 그 기대 자리와 번호 사이
                # 거리로 다시 짝짓는다. 잉크 거리만으로는 그림 밑의 번호가 옆 그림과도 가까워
                # 짝이 한 칸씩 밀렸다(band3/99 의 Eunotia)
                lab_of = {t[0]: t for t in labs}
                rel = [((lab_of[w][1] - st[g[0]][0]) / max(st[g[0]][2], 1),
                        ((lab_of[w][2] + lab_of[w][3]) / 2 - st[g[0]][1]) / max(st[g[0]][3], 1))
                       for w, g in groups.items()]
                if len(rel) >= 4:
                    ru, rv = np.median([r[0] for r in rel]), np.median([r[1] for r in rel])
                    ink_d = {(i, w): c for c, i, w in pairs}
                    pairs2 = []
                    for (i, w), c in ink_d.items():
                        x, y, w_, h_ = st[i][:4]
                        t = lab_of[w]
                        ax, ay = x + ru * w_, y + rv * h_
                        a_d = float(np.hypot(t[1] - ax, (t[2] + t[3]) / 2 - ay))
                        pairs2.append((0.0 if c == 0 else min(a_d, 4 * M) + c, i, w))
                    pairs2.sort()
                    groups, taken = greedy(pairs2)
                orphan = []
                for i in blobs:
                    if i in taken:
                        continue
                    if i in near:
                        groups.setdefault(near[i][1], []).append(i)
                    else:
                        orphan.append(i)
                # 큰 판은 번호가 그림에서 멀다(Eunotia·Chaetoceros) — 짝 못 받은 번호와
                # 주인 없는 덩어리끼리 400px 안에서 한 번 더 짝짓는다(상자 사이 거리)
                rest = sorted(
                    (float(np.hypot(max(st[i][0] - t[5], 0, t[4] - st[i][0] - st[i][2]),
                                    max(st[i][1] - t[3], 0, t[2] - st[i][1] - st[i][3]))), i, t[0])
                    for i in orphan for t in labs if t[0] not in groups)
                for c, i, w in rest:
                    if c > 400:
                        break
                    if i in orphan and w not in groups:
                        groups[w] = [i]
                        orphan.remove(i)
                return groups, orphan, dropped

            def first_pass(side, fallback):
                groups: dict[str, list[int]] = {}
                orphan: list[int] = []
                dropped: list[int] = []
                for i in range(1, nxt):
                    x, y, w_, h_, a = st[i]
                    if a < MIN_AREA or i in carved:
                        continue
                    if (x < 0.03 * W or x + w_ > 0.97 * W) and w_ < 0.03 * W:
                        continue                               # 스캔 테두리
                    if d["frame"] and w_ > 0.5 * W and h_ > 0.5 * H and a < 0.05 * w_ * h_:
                        dropped.append(i)                      # 손으로 그린 판 테두리 — 쪽을 덮는 빈 덩어리
                        continue
                    inside = [(abs(t[2] - (y + h_)) + 0.5 * abs(t[1] - (x + w_ / 2)), t[0]) for t in labs
                              if x <= t[1] <= x + w_ and y <= t[2] <= y + h_
                              and (not d["frame"] or near_blob(i, t))]
                    cand = inside or [(g, t[0]) for t in labs if (g := toward(x, y, w_, h_, t, side)) is not None] \
                        or (fallback and [(g, t[0]) for t in labs
                                          if (g := toward(x, y, w_, h_, t, fallback)) is not None])
                    if cand:
                        groups.setdefault(min(cand)[1], []).append(i)
                    else:
                        orphan.append(i)
                return groups, orphan, dropped

            if d["frame"]:
                groups, orphan, dropped = match_pass()
            else:
                groups, orphan, dropped = first_pass(side, fallback)
            for i, w in carved.items():
                groups.setdefault(w, []).append(i)
            # 점 짚기 — 버린 덩어리는 따로 모은다. 상자가 번호 글자까지 넓어지면
            # 버린 그림이 다시 들어올 수 있어 크롭에서 지워야 한다(p209 의 544)
            for f in fixes:
                if len(f) != 3:
                    continue
                X, Y = int(f[0] * s), int(f[1] * s)
                i = int(lab[Y, X])
                if not i:
                    near = lab[max(0, Y - 40):Y + 40, max(0, X - 40):X + 40]
                    ids = near[near > 0]
                    if not len(ids):
                        raise SystemExit(f"{p} 점 {f} 둘레에 덩어리가 없다")
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
            for w, lx, ly, *_ in labs:
                if w in groups or not orphan:
                    continue

                def gap(i):
                    x, y, w_, h_ = st[i][:4]
                    return np.hypot(max(x - lx, 0, lx - x - w_), max(y - ly, 0, ly - y - h_))
                b = min(orphan, key=gap)
                if gap(b) <= 40 * u:
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
            return lab, st, nxt, carved, groups, orphan, dropped, bbox

        if d["frame"]:
            # Schmidt 는 두 팽창(31 · 15)으로 다 해 보고 **빈 번호가 적은** 것을 쓴다(같으면
            # 주인 없는 덩어리가 적은 것). 흐린 점묘 원반은 15 로는 조각나 한 조각만 제 번호를
            # 받고 나머지가 이웃 번호로 갔다 — 잘림과 섞임이 같은 뿌리였다(band2/109).
            # 빽빽한 판(band4/155)은 31 이면 이웃과 붙어 빈 번호가 생긴다
            names_ = {t[0] for t in labs}
            runs = [segment(g) for g in (SC_GROW, GROW)]
            lab, st, nxt, carved, groups, orphan, dropped, bbox = min(
                runs, key=lambda r: (len(names_ - set(r[4])), len(r[5])))
        else:
            lab, st, nxt, carved, groups, orphan, dropped, bbox = segment(GROW)

        sheet = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        rng = np.random.default_rng(int(re.sub(r"\D", "", p)))
        made = []
        names = d["names"]
        for w, ids in groups.items():
            x0, y0, x1, y1 = bbox(ids)
            t = next((t for t in labs if t[0] == w), None)
            if t and side == "below":                     # 번호도 크롭에 담는다
                _, lx, _, ly1, *_ = t
                x0, x1, y1 = min(x0, lx - 40), max(x1, lx + 40), max(y1, ly1 + 4)
            elif t:
                x0, y0, x1, y1 = min(x0, t[4] - 4), min(y0, t[2] - 4), max(x1, t[5] + 4), max(y1, t[3] + 4)
            x0, y0 = max(0, int(x0) - PAD), max(0, int(y0) - PAD)
            x1, y1 = min(W, int(x1) + PAD), min(H, int(y1) + PAD, int((d["cap_top"] - 3) * s))
            ours = names is None or w in names
            c = tuple(int(v) for v in rng.integers(0, 190, 3)) if ours else (150, 150, 150)
            cv2.rectangle(sheet, (x0, y0), (x1, y1), c, 6)
            cv2.putText(sheet, w, (x0 + 8, y0 + 64), cv2.FONT_HERSHEY_SIMPLEX, 2.2, c, 6)
            if not ours:
                continue                                   # 도감 밖 항목(159–166 등)
            crop = im[y0:y1, x0:x1].copy()
            theirs = [j for ww, g in groups.items() if ww != w for j in g] + dropped
            crop[np.isin(lab[y0:y1, x0:x1], theirs)] = 255
            if names is None:
                # Schmidt 는 거꾸로 — 내 덩어리·내 번호·작은 점 말고는 다 지운다. 잉크에서
                # 지운 것(머리글·테두리·남의 번호)은 덩어리가 아니라 "남의 것" 으로 안 잡히고,
                # 흐린 남의 그림 조각은 주인 없는 덩어리로 남아 상자 안에 들어온다
                lc = lab[y0:y1, x0:x1]
                big = np.flatnonzero(st[:, 4] >= MIN_AREA)
                off = np.isin(lc, np.setdiff1d(big, ids)) | ((lc == 0) & (crop < THR))
                if t:
                    off[max(0, int(t[2]) - 6 - y0):max(0, int(t[3]) + 6 - y0),
                        max(0, int(t[4]) - 6 - x0):max(0, int(t[5]) + 6 - x0)] = False
                crop[off] = 255
            for a0, b0, a1, b1, ww in d["labels"]:
                if ww != w:
                    crop[max(0, int(b0 * s) - 6 - y0):max(0, int(b1 * s) + 6 - y0),
                         max(0, int(a0 * s) - 6 - x0):max(0, int(a1 * s) + 6 - x0)] = 255
            cv2.imwrite(str(work / "crops" / f"{d['tag']}_{fsafe(w)}.png"), crop)
            made.append(w)
        for i in orphan:
            x, y, w_, h_, _ = st[i]
            cv2.rectangle(sheet, (int(x), int(y)), (int(x + w_), int(y + h_)), (0, 0, 255), 10)
        cv2.imwrite(str(work / "sheets" / f"{d['tag']}.jpg"),
                    cv2.resize(sheet, (W * SHEET_H // H, SHEET_H)))
        got = {w for w in (t[0] for t in labs) if names is None or w in names} | set(made)
        want = d["want"]
        r = dict(made=sorted(made), empty=sorted(got - set(made)), orphans=len(orphan),
                 not_in_index=sorted(got - want) if names is not None else [],
                 index_only=sorted(want - got))
        report[p] = r
        flag = r["empty"] or r["orphans"] or r["not_in_index"] or r["index_only"]
        bad += bool(r["empty"])
        print(f"{p} 크롭 {len(made):2d}" + (f"  빈 {r['empty']}" if r["empty"] else "")
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


def figure_tag(nums: list[str]) -> str:
    """그림 번호들 → 파일 이름 조각. 이어지면 `1-8`, 아니면 `21_24`."""
    if all(n.isdigit() for n in nums) and len(nums) > 1 and \
            [int(n) for n in nums] == list(range(int(nums[0]), int(nums[-1]) + 1)):
        return f"{nums[0]}-{nums[-1]}"
    return "_".join(fsafe(n) for n in nums)


def sc_fig_fixes() -> dict[tuple[str, str], tuple[str, str]]:
    """(쪽, 색인의 그림 표기) → (실제 그림 표기, 근거). 색인 OCR 이 그림 번호를 틀린 자리."""
    import tomllib
    if not SC_FIXES.exists():
        return {}
    d = tomllib.loads(SC_FIXES.read_text(encoding="utf-8"))
    return {(page, f["index"]): (f["real"], f.get("note", ""))
            for page, v in d.items() for f in v.get("figures", [])}


def cmd_publish_schmidt(work: Path, apply: bool) -> int:
    """색인 자리 하나(학명 · 쪽 · 그림 범위)마다 그림을 이어 붙인 한 장을 낸다.

    Schmidt 의 자리는 그림 하나가 아니라 범위다(`1—8` · `21, 22`). 뷰어의 자리는
    `crop_image` 하나라, 범위의 그림을 **원래 배율 그대로** 번호순으로 늘어놓는다.
    그림 사이를 잇는 한 상자(합집합)는 안 쓴다 — 떨어진 번호면 남의 그림이 다 들어온다.
    **범위의 그림이 하나라도 없으면 안 만든다**(색인 OCR 이 `29—32` 를 `29—82` 로
    읽은 자리가 그렇다 — `schmidt_crop_fixes.toml` 의 `figures` 로 고친다).
    """
    from PIL import Image
    import tomllib
    fixes = sc_fig_fixes()
    # 눈검사에서 끝내 틀린 자리 — 크롭을 안 붙인다(틀리게 붙이는 것보다 낫다)
    skips = {page: set(v.get("skip", [])) for page, v in
             (tomllib.loads(SC_FIXES.read_text(encoding="utf-8")) if SC_FIXES.exists() else {}).items()}
    skipped: set[str] = set()
    d = json.loads(SCHMIDT_JSON.read_text(encoding="utf-8"))
    crops = work / "crops"
    have = {f.stem for f in crops.glob("band*_p*_*.png")}
    pages = {f.stem for f in (work / "labels").glob("band*_*.json")}
    plan, short = {}, []
    for e in d["entries"]:
        for p in e["placements"]:
            if not (p["figures"] and p["pdf_plate_page"]):
                continue
            band, page = p["volume"].lower(), p["pdf_plate_page"]
            if f"{band}_{page}" not in pages:
                continue
            key = f"{band}/{page}"
            figs_ = fixes.get((key, p["figures"]), (p["figures"],))[0]
            nums = figure_numbers(figs_)
            stems = [f"{band}_p{page:04d}_{fsafe(n)}" for n in nums]
            miss = [n for n, s_ in zip(nums, stems) if s_ not in have]
            if not nums or miss:
                short.append((key, e["name"], p["figures"], miss))
                continue
            tag = f"b{band[-1]}p{page}_fig{figure_tag(nums)}"
            if figure_tag(nums) in skips.get(key, ()):
                skipped.add(tag)
                continue
            plan.setdefault(tag, (stems, []))[1].append(e["name"])
    # 그림이 다 있어도 틀릴 수 있다 — `23, 24` 를 OCR 이 `28, 24` 로 읽으면 남의 그림
    # 28 을 붙인다. 번호가 거꾸로 가거나, 한 그림을 두 학명이 부르면 사람이 본다
    owner: dict[tuple[str, str], set[str]] = {}
    for tag, (stems, ns) in plan.items():
        for s_ in stems:
            owner.setdefault(s_, set()).update(ns)
    look = sorted({tag for tag, (stems, ns) in plan.items()
                   if any(not a.isdigit() or not b.isdigit() or int(a) >= int(b)
                          for a, b in zip((x.rsplit("_", 1)[1] for x in stems),
                                          (x.rsplit("_", 1)[1] for x in stems[1:])))
                   or any(len(owner[s_]) > 1 for s_ in stems)})
    (work / "look.json").write_text(json.dumps(
        {tag: plan[tag][1] for tag in look}, ensure_ascii=False, indent=1))
    print(f"자리 크롭 {len(plan)}장 (학명 {sum(len(v[1]) for v in plan.values())}) · 못 만든 자리 {len(short)}"
          f" · 뺀 자리(skip) {len(skipped)}"
          f" · 사람이 볼 것 {len(look)} ({work / 'look.json'})")
    for key, name, f, miss in short[:40]:
        print(f"  {key} {name} [{f}] 없는 그림 {miss[:8]}{' …' if len(miss) > 8 else ''}")
    out = work / "placements"
    out.mkdir(exist_ok=True)
    GAP, WRAP = 30, 2400
    for tag, (stems, _) in plan.items():
        ims = [Image.open(crops / f"{s_}.png") for s_ in stems]
        rows, row, w = [], [], 0
        for im in ims:                                     # 폭 WRAP 에서 줄을 바꾼다
            if row and w + GAP + im.width > max(WRAP, im.width):
                rows.append(row)
                row, w = [], 0
            row.append(im)
            w += (GAP if w else 0) + im.width
        rows.append(row)
        W_ = max(sum(i.width for i in r) + GAP * (len(r) - 1) for r in rows)
        H_ = sum(max(i.height for i in r) for r in rows) + GAP * (len(rows) - 1)
        sheet = Image.new("L", (W_, H_), 255)
        y = 0
        for r in rows:
            x = 0
            for i in r:
                sheet.paste(i.convert("L"), (x, y))
                x += i.width + GAP
            y += max(i.height for i in r) + GAP
        sheet.save(out / f"{tag}.png")
    names = {}
    for tag, (_, ns) in plan.items():
        for n in ns:
            names[(tag, n)] = PLATE_DIR / f"plate_schmidt_{tag}_{slug(n)}.png"
    old = {p.name for p in PLATE_DIR.glob("plate_schmidt_*.png")}
    new = {v.name for v in names.values()}
    print(f"→ {PLATE_DIR}  (새로 {len(new - old)} · 바뀜 {len(new & old)} · 남는 옛것 {len(old - new)})")
    if not apply:
        print("(--apply 를 주면 쓴다)")
        return 0
    import shutil
    for (tag, _), dest in names.items():
        shutil.copyfile(out / f"{tag}.png", dest)
    print("썼다")
    return 0


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
    ap.add_argument("--book", choices=["korean", "schmidt"], default="korean")
    a = ap.parse_args()
    if a.step == "labels":
        return cmd_labels(a.work)
    if a.step == "ocr":
        return cmd_ocr(a.work)
    if a.step == "cut":
        return cmd_cut(a.work, a.only.split(",") if a.only else None, a.book)
    if a.book == "schmidt":
        return cmd_publish_schmidt(a.work, a.apply)
    return cmd_publish(a.work, a.apply)


if __name__ == "__main__":
    raise SystemExit(main())
