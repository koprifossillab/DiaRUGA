#!/usr/bin/env python3
"""5차 꾸러미 ① — 합성본 → 프레임 warp 를 다시 계산한다 (P33 3절 · 8절 ①).

    python tools/v5_warps.py warps   --out /data3/DiaRUGA/datasets/v5-work/warps.json
    python tools/v5_warps.py overlay --warps …/warps.json --out …/overlay --vp 260731_rs23-gc03_369cm_vp012 …

**`focus_stack` 이 버린 warp 를 같은 규칙으로 다시 낸다** — 같은 기준 판(사진의 `Laplacian` 분산이
가장 큰 판) · 같은 블러(σ 3) · 같은 ECC 인자(`MOTION_EUCLIDEAN` · 60회 · 1e-5 · 가우스 5). ECC 는
결정적이라 합성 때와 같은 warp 가 나온다(P26). 합성본의 점 p 는 프레임 k 에서 `W_k · [p, 1]` 이다
(`focus_stack` 이 `WARP_INVERSE_MAP` 으로 그 판을 기준에 맞췄으므로).

**어느 시야인가** — 4.1차 꾸러미(`yolo-v4.1-seg`)의 이미지 이름 `<slug>_vp<idx>` 를 분할 디렉토리에서
읽는다. **프레임 구성은 3차 정답 사본(DB)에서** — 꾸러미가 그 사본에서 나왔으니 시야 번호가 같은 판이다.
사본은 `mode=ro&immutable=1` 로 연다(파일이 안 바뀌어 sha256 이 그대로다 · CLAUDE.md "YOLO 회차마다").

**대조하고 어긋나면 뺀다**(까닭을 적는다) — DB 에 시야가 없다 · 합성본이 없다(한 장짜리 — 더할 판이
없다) · 프레임 파일이 없다 · 다시 고른 기준 판이 합성 때 남긴 `Stack.ref_frame_id` 와 다르다. ECC 가
실패한 판은 그 판만 뺀다.

Django 를 안 쓴다 — 호스트 venv 로 돈다(`photos/` 를 읽을 수 있는 계정이어야 한다).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

DATA = Path("/data3/DiaRUGA")
ANSWER = DATA / "backup/answer/DiaRUGA_20261028_151451_yolo3-final-inspected.db"
V41 = Path("/nfs/temp-share/DiaRUGA/datasets/yolo-v4.1-seg")
SPLITS = ("train", "val", "val_slide")

# `pipeline/focus_stack.py` 의 `align_to_reference` 와 같은 값 — 바꾸면 합성 때의 warp 와 어긋난다
BLUR = 3
ECC_CRIT = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5)
ECC_GAUSS = 5


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def connect(db: Path):
    return sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)


def dataset_viewpoints(root: Path) -> list[tuple[str, str, int]]:
    """(분할, slug, idx). 이름은 `<slug>_vp<idx>.jpg`."""
    out = []
    for split in SPLITS:
        for p in sorted((root / "images" / split).glob("*.jpg")):
            slug, _, idx = p.stem.rpartition("_vp")
            out.append((split, slug, int(idx)))
    return out


def plan(db: Path, vps) -> tuple[list[dict], list[dict]]:
    """시야마다 프레임 목록을 DB 에서 읽는다. (돌릴 것, 뺀 것)."""
    c = connect(db)
    todo, skipped = [], []
    for split, slug, idx in vps:
        name = f"{slug}_vp{idx:03d}"
        row = c.execute("""select v.id from viewer_viewpoint v join viewer_slide s on s.id=v.slide_id
                           where s.slug=? and v.idx=?""", (slug, idx)).fetchone()
        if row is None:
            skipped.append({"name": name, "split": split, "why": "DB 에 시야가 없다"}); continue
        vid = row[0]
        st = c.execute("""select focused_path, ref_frame_id, resize_scale, align_failed
                          from viewer_stack where viewpoint_id=?""", (vid,)).fetchone()
        if st is None:
            skipped.append({"name": name, "split": split, "why": "합성본이 없다 — 한 장짜리라 더할 판이 없다"})
            continue
        frames = c.execute("""select id, name, path, seq from viewer_frame where viewpoint_id=?
                              order by seq, id""", (vid,)).fetchall()
        missing = [f[2] for f in frames if not (DATA / f[2]).exists()]
        if missing:
            skipped.append({"name": name, "split": split, "why": f"프레임 파일이 없다 {len(missing)}장",
                            "missing": missing}); continue
        if st[2] != 1.0:
            skipped.append({"name": name, "split": split, "why": f"합성 배율이 {st[2]} 다"}); continue
        todo.append({"name": name, "split": split, "viewpoint_id": vid, "stack": st[0],
                     "ref_frame_id": st[1], "align_failed_at_stack": st[3],
                     "frames": [{"id": f[0], "name": f[1], "path": f[2], "seq": f[3]} for f in frames]})
    return todo, skipped


def motion(W: np.ndarray, w: int, h: int) -> dict:
    """합성본 좌표에서 본 움직임 — 가운데 이동 · 귀퉁이 최대 이동 · 회전."""
    pts = np.array([[w / 2, h / 2], [0, 0], [w, 0], [0, h], [w, h]], np.float64)
    moved = pts @ W[:, :2].T + W[:, 2]
    d = np.hypot(*(moved - pts).T)
    return {"center_px": round(float(d[0]), 2), "corner_max_px": round(float(d[1:].max()), 2),
            "rot_deg": round(math.degrees(math.atan2(W[1, 0], W[0, 0])), 4)}


def warp_one(job: dict) -> dict:
    t0 = time.time()
    grays = []
    for f in job["frames"]:
        im = cv2.imread(str(DATA / f["path"]), cv2.IMREAD_COLOR)
        if im is None:
            return {**job, "error": f"못 읽는다: {f['path']}"}
        grays.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    h, w = grays[0].shape
    ref_i = int(np.argmax([cv2.Laplacian(g, cv2.CV_32F).var() for g in grays]))
    a = cv2.GaussianBlur(grays[ref_i], (0, 0), BLUR)
    out = []
    for i, (f, g) in enumerate(zip(job["frames"], grays)):
        rec = {**f, "is_ref": i == ref_i}
        if i == ref_i:
            W, ok = np.eye(2, 3, dtype=np.float32), True
        else:
            W = np.eye(2, 3, dtype=np.float32)
            try:
                cv2.findTransformECC(a, cv2.GaussianBlur(g, (0, 0), BLUR), W, cv2.MOTION_EUCLIDEAN,
                                     ECC_CRIT, None, ECC_GAUSS)
                ok = True
            except cv2.error:
                ok = False
        rec["ok"] = ok
        if ok:
            rec["warp"] = [round(float(x), 6) for x in W.ravel()]
            rec.update(motion(W.astype(np.float64), w, h))
        out.append(rec)
    ref_id = job["frames"][ref_i]["id"]
    return {**job, "frames": out, "size": [w, h], "ref_ok": ref_id == job["ref_frame_id"],
            "ref_frame_id_recomputed": ref_id, "sec": round(time.time() - t0, 1)}


def cmd_warps(a) -> int:
    vps = dataset_viewpoints(Path(a.v41))
    todo, skipped = plan(Path(a.db), vps)
    if a.limit:
        todo = todo[: a.limit]
    print(f"꾸러미 시야 {len(vps)} · 돌릴 것 {len(todo)} · 뺀 것 {len(skipped)}", file=sys.stderr)
    done = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, r in enumerate(ex.map(warp_one, todo), 1):
            done.append(r)
            if i % 20 == 0:
                print(f"  {i}/{len(todo)}", file=sys.stderr)
    # 기준 판이 합성 때와 다르면 warp 가 합성본 좌표계가 아니다 — 그 시야는 뺀다
    keep = []
    for r in done:
        if r.get("error"):
            skipped.append({"name": r["name"], "split": r["split"], "why": r["error"]})
        elif not r["ref_ok"]:
            skipped.append({"name": r["name"], "split": r["split"],
                            "why": "다시 고른 기준 판이 합성 때의 기준 판과 다르다",
                            "ref_frame_id": r["ref_frame_id"],
                            "recomputed": r["ref_frame_id_recomputed"]})
        else:
            keep.append(r)
    res = {"made_at": time.strftime("%Y-%m-%d %H:%M:%S"), "answer_db": str(a.db),
           "answer_db_sha256": sha256(Path(a.db)), "v41": str(a.v41),
           "rule": {"blur_sigma": BLUR, "ecc": "MOTION_EUCLIDEAN 60 1e-5 gauss 5",
                    "map": "stack p → frame W·[p,1]"},
           "viewpoints": keep, "skipped": skipped}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    summarize(res)
    return 0


def summarize(res: dict) -> None:
    fr = [f for v in res["viewpoints"] for f in v["frames"] if not f["is_ref"]]
    ok = [f for f in fr if f["ok"]]
    print(f"\n시야 {len(res['viewpoints'])} · 기준 아닌 판 {len(fr)} · ECC 실패 {len(fr) - len(ok)}")
    for k in ("center_px", "corner_max_px", "rot_deg"):
        x = np.abs([f[k] for f in ok])
        print(f"  {k:<14} 가운데 {np.median(x):.3f} · 90% {np.percentile(x, 90):.3f} · 최대 {x.max():.3f}")
    why = {}
    for s in res["skipped"]:
        key = s["why"].split(" — ")[0]
        why[key] = why.get(key, 0) + 1
    print("뺀 시야:", why or "없다")


def cmd_overlay(a) -> int:
    """합성본의 검출 폴리곤(3차 검토 대상 묶음의 통과분)을 프레임으로 옮겨 그린다 — 눈으로 맞는지 본다.

    왼쪽: 합성본 위의 폴리곤 · 오른쪽: 프레임 원본 위에 W 로 옮긴 폴리곤(초록) 과 옮기지 않은 것(빨강).
    """
    res = json.loads(Path(a.warps).read_text(encoding="utf-8"))
    by = {v["name"]: v for v in res["viewpoints"]}
    c = connect(Path(res["answer_db"]))
    bid = c.execute("select id from viewer_runbatch where for_review").fetchone()[0]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    names = a.vp or [v["name"] for v in sorted(
        res["viewpoints"], key=lambda v: -max((f.get("corner_max_px", 0) for f in v["frames"]), default=0))[: a.top]]
    for name in names:
        v = by[name]
        polys = [json.loads(p) for (p,) in c.execute(
            """select c.polygon from viewer_candidate c join viewer_detection d on d.id=c.detection_id
               join viewer_run r on r.id=d.run_id join viewer_image i on i.id=d.image_id
               where d.viewpoint_id=? and d.is_current and r.batch_id=? and i.kind='stack' and c.passed""",
            (v["viewpoint_id"], bid))]
        polys = [np.array(p, np.float64).reshape(-1, 2) for p in polys if p]
        stack = cv2.imread(str(DATA / v["stack"]))
        for f in v["frames"]:
            if f["is_ref"] or not f["ok"]:
                continue
            W = np.array(f["warp"], np.float64).reshape(2, 3)
            fr = cv2.imread(str(DATA / f["path"]))
            L, R = stack.copy(), fr.copy()
            for p in polys:
                q = p @ W[:, :2].T + W[:, 2]
                cv2.polylines(L, [p.astype(np.int32)], True, (0, 255, 0), 3)
                cv2.polylines(R, [p.astype(np.int32)], True, (0, 0, 255), 2)
                cv2.polylines(R, [q.astype(np.int32)], True, (0, 255, 0), 3)
            pic = np.hstack([L, R])
            cv2.putText(pic, f"{name} {f['name']} corner {f['corner_max_px']}px rot {f['rot_deg']}deg",
                        (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 255, 0), 4)
            pic = cv2.resize(pic, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(out / f"{name}_{f['name']}.jpg"), pic, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"{name}: 폴리곤 {len(polys)} · 판 {sum(1 for f in v['frames'] if not f['is_ref'] and f['ok'])}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("warps")
    w.add_argument("--db", default=str(ANSWER))
    w.add_argument("--v41", default=str(V41))
    w.add_argument("--out", required=True)
    w.add_argument("--jobs", type=int, default=8)
    w.add_argument("--limit", type=int, default=0)
    o = sub.add_parser("overlay")
    o.add_argument("--warps", required=True)
    o.add_argument("--out", required=True)
    o.add_argument("--vp", nargs="*")
    o.add_argument("--top", type=int, default=6, help="--vp 가 없으면 귀퉁이 이동이 큰 시야부터")
    a = ap.parse_args()
    return cmd_warps(a) if a.cmd == "warps" else cmd_overlay(a)


if __name__ == "__main__":
    sys.exit(main())
