#!/usr/bin/env python3
"""5차 꾸러미 `yolo-v5-seg` 를 굽는다 — 합성본의 정답을 프레임으로 옮긴다 (P33 · 250 · 8절 ③).

    python tools/make_v5.py --out /data3/DiaRUGA/datasets/yolo-v5-seg [--limit N] [--jobs 10]

**무엇이 들어가나**

| 디렉토리 | 판 | 라벨 |
|---|---|---|
| `train` | 4.1차 train 의 합성본(한 장짜리는 그 한 장) **+ 그 시야의 프레임 전부** | 합성본은 4.1차 그대로, 프레임은 옮기고 거른 것 |
| `val` | 4.1차 val 의 합성본 — **두 번 보완한 1,723** | 4.1차 val(1,348) + 242 8.5 표시의 실제 375 |
| `val_frames` | val 시야의 프레임 | val(1,723)을 옮기고 거른 것 — 7절 1~3 을 재는 자리 |
| `val_slide` · `val_slide_frames` | 같은 짝 — 816cm | 4.1차 그대로 · 옮기고 거른 것 |

학습(`data.yaml`)의 val 은 **합성본 val** 이다 — 4.1차와 같은 자로 재야 7절 4(합성본이 나빠지지 않았나)가 성립한다.

**옮기기** — 합성본의 점 p 는 프레임에서 `W·[p,1]`(250 · `v5_warps.py`). 프레임 밖으로 나간 부분은 사각형으로
잘라 낸다(Sutherland–Hodgman). 남은 넓이가 50 화소 미만이면 그 판에는 그 개체가 없다.

**거르기** — (개체, 프레임) 선명도는 **옮긴 마스크의 경계 띠 ±6 px** 의 `Laplacian` 분산이고, 그 개체가 들어간
프레임들 가운데 가장 선명한 판 대비 **0.3 미만이면 뺀다**(사용자 10-30 · 250). 처음엔 0.5 였는데 표본을 보니
0.4~0.5 도 형태가 또렷했다 — 이 꾸러미는 흐린 판에서도 잡게 하려는 것이라 윤곽만 남은 것만 뺀다.
**빼는 개체는 라벨에서만 빼고 사진에는 남긴다**(사용자 10-30) — "이만큼 흐리면 잡지 않는다" 는 판단을 내린
자리라 배경으로 배우는 것이 그 판단을 가르치는 길이다. 지우면 모델이 그런 개체를 한 번도 안 봐 추론 때 무엇을
할지 정해지지 않고, 칠한 덩어리라는 실제에 없는 무늬가 생긴다. 띠가 너무 작아 못 재면(30 화소 미만) 남긴다(그 수를 적는다).

**"모르겠음"** — 4.1차 train 의 23 자리는 합성본에서 이미 지워져 있다. 프레임에서도 옮겨 지운다(242 표시 md) —
규조각인지 판단을 못 한 자리라 라벨로도 배경으로도 가르칠 수 없다. **배경색(그 판의 가운데값 색)으로 칠하고
폴리곤보다 6 px 넓힌다** — 흐린 판에서는 윤곽이 바깥으로 번져, 폴리곤만 칠하면 진한 테두리가 남았다.
**남는 정답 폴리곤과 겹치는 화소는 지우지 않는다.**
val 의 아님·모르겠음은 지우지 않는다 — 오답으로 남긴다(242 8.6).

손대지 않은 프레임은 원본 JPEG 바이트를 그대로 복사한다. 지운 판만 다시 인코딩한다(품질 95).

`MANIFEST.json` — 원본 꾸러미 · warp · 표시 md · 정답 사본의 sha256, 판마다 warp, 개체마다 상대 선명도와 뺀 까닭.
`SHA256SUMS` — 이미지 + 라벨.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA = Path("/data3/DiaRUGA")
V41 = Path("/nfs/temp-share/DiaRUGA/datasets/yolo-v4.1-seg")
WARPS = DATA / "datasets/v5-work/warps.json"
MD_TRAIN = REPO / "devlog/assets/20261028_242_yolo41_train_fp_review.md"
MD_VAL = REPO / "devlog/assets/20261028_242_yolo41_val_new_review.md"
CLASSES = ["round", "round_frag", "rod", "rod_frag", "chaetoceros", "eucampia", "other"]
BAND = 6
THRESH = 0.3
ERASE_GROW = 6          # 지우는 자리를 이만큼 넓힌다 — 프레임에서는 윤곽이 폴리곤 밖으로 번진다
MIN_AREA = 50
FRAME_SPLIT = {"train": "train", "val": "val_frames", "val_slide": "val_slide_frames"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def md_rows(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.open(encoding="utf-8") if line.startswith('{"img"')]


def pts(s: str) -> np.ndarray:
    return np.array([[float(v) for v in xy.split(",")] for xy in s.split()], np.float64)


def read_labels(p: Path, w: int, h: int) -> list[tuple[int, np.ndarray]]:
    out = []
    for line in p.read_text().splitlines():
        v = line.split()
        if len(v) < 7:
            continue
        xy = np.array(v[1:], np.float64).reshape(-1, 2) * [w, h]
        out.append((int(v[0]), xy))
    return out


def fmt(c: int, P: np.ndarray, w: int, h: int) -> str:
    q = P / [w, h]
    return f"{c} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in q)


def clip_rect(P: np.ndarray, w: int, h: int) -> np.ndarray:
    """Sutherland–Hodgman — 다각형을 [0,w]×[0,h] 로 자른다."""
    def clip(poly, inside, cross):
        out = []
        for i in range(len(poly)):
            a, b = poly[i - 1], poly[i]
            if inside(b):
                if not inside(a):
                    out.append(cross(a, b))
                out.append(b)
            elif inside(a):
                out.append(cross(a, b))
        return out

    def at_x(x0):
        return lambda a, b: np.array([x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0])])

    def at_y(y0):
        return lambda a, b: np.array([a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0])

    poly = list(P)
    for inside, cross in ((lambda p: p[0] >= 0, at_x(0)), (lambda p: p[0] <= w, at_x(w)),
                          (lambda p: p[1] >= 0, at_y(0)), (lambda p: p[1] <= h, at_y(h))):
        if not poly:
            break
        poly = clip(poly, inside, cross)
    return np.array(poly, np.float64).reshape(-1, 2)


def area(P: np.ndarray) -> float:
    if len(P) < 3:
        return 0.0
    x, y = P[:, 0], P[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def mask_of(P: np.ndarray, w: int, h: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(P).astype(np.int32)], 1)
    return m


def band_var(lap: np.ndarray, m: np.ndarray, kb) -> float:
    ring = (cv2.dilate(m, kb) - cv2.erode(m, kb)).astype(bool)
    v = lap[ring]
    return float(v.var()) if v.size >= 30 else float("nan")


def build_vp(job: dict) -> dict:
    """한 시야: 합성본을 옮겨 놓고, 프레임마다 라벨을 옮기고 거르고 지운다."""
    out_root = Path(job["out"])
    split, stem, w, h = job["split"], job["stem"], job["w"], job["h"]
    rec = {"stem": stem, "split": split, "stack": {}, "frames": []}

    # 합성본(한 장짜리는 그 한 장) — 4.1차 사진 그대로, 라벨은 4.1차(+ val 보완)
    src_img = V41 / "images" / split / f"{stem}.jpg"
    shutil.copyfile(src_img, out_root / "images" / split / f"{stem}.jpg")
    objs = job["objs"]
    (out_root / "labels" / split / f"{stem}.txt").write_text(
        "".join(fmt(c, P, w, h) + "\n" for c, P in objs))
    rec["stack"] = {"n_objects": len(objs), "added_val": job["n_added"]}

    v = job.get("warp")
    if v is None:                       # 한 장짜리 — 더할 판이 없다
        return rec
    kb = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * BAND + 1, 2 * BAND + 1))
    fsplit = FRAME_SPLIT[split]
    frames = [f for f in v["frames"] if f["ok"]]
    # 1) 옮기고 잘라 선명도를 잰다 — 판마다 (개체 → (폴리곤, 선명도))
    per = []
    for f in frames:
        W = np.array(f["warp"], np.float64).reshape(2, 3)
        g = cv2.imread(str(DATA / f["path"]), cv2.IMREAD_GRAYSCALE)
        lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
        rows = []
        for c, P in objs:
            Q = clip_rect(P @ W[:, :2].T + W[:, 2], w, h)
            if area(Q) < MIN_AREA:
                rows.append(None)
                continue
            rows.append((Q, band_var(lap, mask_of(Q, w, h), kb)))
        unsure = [clip_rect(U @ W[:, :2].T + W[:, 2], w, h) for U in job["unsure"]]
        per.append((f, rows, [U for U in unsure if area(U) >= MIN_AREA]))
    # 2) 개체마다 가장 선명한 판 대비 상대값
    best = []
    for k in range(len(objs)):
        vals = [r[k][1] for _, r, _ in per if r[k] is not None and np.isfinite(r[k][1])]
        best.append(max(vals) if vals else None)
    # 3) 판마다 쓴다
    for f, rows, unsure in per:
        keep, drop, info = [], [], []
        for k, ((c, _), r) in enumerate(zip(objs, rows)):
            if r is None:
                info.append({"k": k, "why": "프레임 밖"})
                continue
            Q, s = r
            if not np.isfinite(s) or not best[k]:
                keep.append((c, Q))
                info.append({"k": k, "rel": None, "why": "못 잼 — 남김"})
                continue
            rel = s / best[k]
            if rel < THRESH:
                drop.append(Q)
                info.append({"k": k, "rel": round(rel, 3), "why": "흐림"})
            else:
                keep.append((c, Q))
                info.append({"k": k, "rel": round(rel, 3)})
        name = f"{stem}_s{f['seq']}_{f['name']}"
        dst = out_root / "images" / fsplit / f"{name}.jpg"
        erase = unsure                      # 흐려서 뺀 것은 사진에 남긴다
        if erase:
            im = cv2.imread(str(DATA / f["path"]), cv2.IMREAD_COLOR)
            bg = np.median(im.reshape(-1, 3), axis=0).astype(np.uint8)
            em = np.zeros((h, w), np.uint8)
            for Q in erase:
                cv2.fillPoly(em, [np.round(Q).astype(np.int32)], 1)
            em = cv2.dilate(em, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * ERASE_GROW + 1, 2 * ERASE_GROW + 1)))
            for _, Q in keep:                        # 남는 정답은 지우지 않는다
                cv2.fillPoly(em, [np.round(Q).astype(np.int32)], 0)
            im[em.astype(bool)] = bg
            cv2.imwrite(str(dst), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            shutil.copyfile(DATA / f["path"], dst)
        (out_root / "labels" / fsplit / f"{name}.txt").write_text(
            "".join(fmt(c, Q, w, h) + "\n" for c, Q in keep))
        rec["frames"].append({"image": f"{fsplit}/{name}.jpg", "source": f["path"], "seq": f["seq"],
                              "is_ref": f["is_ref"], "warp": f["warp"], "kept": len(keep),
                              "dropped_blur": len(drop), "erased_unsure": len(unsure),
                              "objects": info})
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} 가 비어 있지 않다 — 지우고 다시 굽는다(덧쓰지 않는다)")
    for d in ("images", "labels"):
        for s in ("train", "val", "val_slide", *FRAME_SPLIT.values()):
            (out / d / s).mkdir(parents=True, exist_ok=True)

    warps = json.loads(WARPS.read_text(encoding="utf-8"))
    by_warp = {v["name"]: v for v in warps["viewpoints"]}
    v41_manifest = json.loads((V41 / "MANIFEST.json").read_text(encoding="utf-8"))

    unsure = {}
    for r in md_rows(MD_TRAIN):
        for f in r["fp"]:
            if f["mark"] == "unsure":
                unsure.setdefault(r["img"], []).append(pts(f["pts"]))
    added = {}
    for r in md_rows(MD_VAL):
        for f in r["fp"]:
            if f["mark"] == "real":
                added.setdefault(r["img"], []).append((CLASSES.index(f["final"]), pts(f["pts"])))

    jobs = []
    for split in ("train", "val", "val_slide"):
        for p in sorted((V41 / "images" / split).glob("*.jpg")):
            stem = p.stem
            im = cv2.imread(str(p), cv2.IMREAD_REDUCED_GRAYSCALE_8)
            w, h = 2752, 2208
            if stem in by_warp:
                w, h = by_warp[stem]["size"]
            else:
                full = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                h, w = full.shape
            del im
            objs = read_labels(V41 / "labels" / split / f"{stem}.txt", w, h)
            add = added.get(stem, []) if split == "val" else []
            jobs.append({"out": str(out), "split": split, "stem": stem, "w": w, "h": h,
                         "objs": objs + add, "n_added": len(add),
                         "unsure": unsure.get(stem, []) if split == "train" else [],
                         "warp": by_warp.get(stem)})
    if a.limit:
        jobs = [j for j in jobs if j["warp"]][: a.limit]
    t0 = time.time()
    recs = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, r in enumerate(ex.map(build_vp, jobs), 1):
            recs.append(r)
            if i % 40 == 0:
                print(f"  {i}/{len(jobs)} · {time.time() - t0:.0f}s", file=sys.stderr)

    # 집계
    counts = {}
    for r in recs:
        s = counts.setdefault(r["split"], Counter())
        s["viewpoints"] += 1
        s["stack_objects"] += r["stack"]["n_objects"]
        s["added_val"] += r["stack"]["added_val"]
        s["frames"] += len(r["frames"])
        for f in r["frames"]:
            s["frame_objects"] += f["kept"]
            s["frame_dropped_blur"] += f["dropped_blur"]
            s["frame_erased_unsure"] += f["erased_unsure"]
            s["frame_outside"] += sum(o["why"] == "프레임 밖" for o in f["objects"] if "why" in o)
            s["frame_unmeasured"] += sum(o.get("why") == "못 잼 — 남김" for o in f["objects"])
    counts = {k: dict(v) for k, v in counts.items()}

    (out / "data.yaml").write_text(
        "# 2026-10-30 · yolo-v4.1-seg + 프레임 (P33 · 250) · tools/make_v5.py\n"
        "# val 은 합성본(두 번 보완한 1,723) — 4.1차와 같은 자. 프레임 val 은 images/val_frames 로 따로 잰다\n"
        "path: .\ntrain: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    for name, img in (("data_val_frames.yaml", "val_frames"), ("data_val_slide.yaml", "val_slide"),
                      ("data_val_slide_frames.yaml", "val_slide_frames")):
        (out / name).write_text(f"path: .\ntrain: images/train\nval: images/{img}\nnames:\n"
                                + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))

    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "plan": "devlog/20261030_P33_frames-from-stack-labels.md · 250",
        "base": "yolo-v4.1-seg", "base_sha256sums": sha256(V41 / "SHA256SUMS"),
        "base_manifest_created_at": v41_manifest["created_at"],
        "answer_db": warps["answer_db"], "answer_db_sha256": warps["answer_db_sha256"],
        "warps": str(WARPS), "warps_sha256": sha256(WARPS),
        "unsure_src": {"md": str(MD_TRAIN.relative_to(REPO)), "sha256": sha256(MD_TRAIN),
                       "n": sum(len(v) for v in unsure.values())},
        "val_added_src": {"md": str(MD_VAL.relative_to(REPO)), "sha256": sha256(MD_VAL),
                          "n": sum(len(v) for v in added.values())},
        "rule": {"sharpness": f"Laplacian var · mask boundary band ±{BAND}px",
                 "relative_to": "same object's sharpest frame", "threshold": THRESH,
                 "drop": "blurred: label removed, pixels kept · unsure: pixels (grown by ERASE_GROW px) filled with frame median colour except kept GT",
                 "erase_grow_px": ERASE_GROW,
                 "min_area_px": MIN_AREA, "clip": "Sutherland–Hodgman to frame rect",
                 "untouched_frames": "original JPEG bytes"},
        "classes": CLASSES, "counts": counts, "viewpoints": recs,
        "limit": a.limit or None,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "SHA256SUMS", "w") as fh:
        for p in sorted(out.rglob("*")):
            if p.is_file() and p.parts[len(out.parts)] in ("images", "labels"):
                fh.write(f"{sha256(p)}  {p.relative_to(out)}\n")
    print(json.dumps(counts, ensure_ascii=False, indent=1))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
