#!/usr/bin/env python3
"""5차 꾸러미 ② — (개체, 프레임) 선명도를 두 방식으로 재 비교한다 (P33 4절 · 8절 ②).

    python tools/v5_sharpness.py --warps /data3/DiaRUGA/datasets/v5-work/warps.json \\
        --out /data3/DiaRUGA/datasets/v5-work/sharpness.json [--vp N] [--band 6]

**선명도는 프레임마다, 옮긴 그 마스크 자리에서 잰다**(사용자 10-30) — 원본 해상도 `Laplacian` 의 분산.

- **안쪽** — 폴리곤 안(경계에서 2 px 들인 것)
- **띠** — 경계 안팎 `--band` px. 흐려지면 윤곽이 바깥으로 번지므로 경계 부근의 대비가 선명도를 잘
  말한다는 생각이다. 속이 밋밋한 큰 원형은 안쪽만 재면 선명해도 낮게 나올 수 있다(P26 의 쌍봉)

**어느 쪽이 초점 위치와 맞는가** — 합성본의 깊이 맵(`depth_npz` · 화소마다 가장 선명했던 판의 번호를
소수로)에서 개체 자리의 가운데값을 반올림한 판을 **합성이 고른 초점 판**으로 놓고, 방식마다 가장 선명하게
잰 판이 그것과 같은 비율을 센다(±1 판도 함께). 깊이 맵도 국소 선명도에서 나온 것이라 완전히 따로 선
기준은 아니지만, **라벨을 옮길 판을 고르는 일이 곧 합성이 그 개체를 어느 판에서 가져왔는가와 맞아야
한다**는 점에서 맞는 자다.

**폴리곤** — 4.1차 꾸러미의 라벨은 이 계정이 못 읽어서(NAS 의 파일이 600) 3차 정답 사본의 검토 대상
묶음 통과분을 쓴다. 방식을 고르는 데에는 이것으로 충분하다 — 꾸러미를 구울 때는 꾸러미 라벨을 쓴다.

상대 선명도(그 개체의 가장 선명한 판 대비)의 분포를 문턱 후보마다 몇 개가 빠지는지로 낸다.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

DATA = Path("/data3/DiaRUGA")
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)


def connect(db):
    return sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)


def lapvar(lap: np.ndarray, m: np.ndarray) -> float:
    v = lap[m]
    return float(v.var()) if v.size >= 30 else float("nan")


def one(job) -> list[dict]:
    v, polys, band = job
    h_w = v["size"]
    z = np.load(DATA / v["depth_npz"])["depth"] if v.get("depth_npz") else None
    frames = [f for f in v["frames"] if f["ok"]]
    laps = {}
    for f in frames:
        g = cv2.imread(str(DATA / f["path"]), cv2.IMREAD_GRAYSCALE)
        laps[f["id"]] = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    seq_of = {f["id"]: i for i, f in enumerate(v["frames"])}     # 깊이 맵의 판 번호 = seq 차례
    kin = np.ones((5, 5), np.uint8)
    kb = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
    out = []
    for oid, p in polys:
        P = np.array(p, np.float64).reshape(-1, 2)
        focus = None
        if z is not None:
            m0 = np.zeros(z.shape, np.uint8)
            cv2.fillPoly(m0, [P.astype(np.int32)], 1)
            d = z[m0.astype(bool)]
            d = d[np.isfinite(d)]
            if d.size >= 30:
                focus = int(round(float(np.median(d))))
        rows = []
        for f in frames:
            W = np.array(f["warp"], np.float64).reshape(2, 3)
            Q = (P @ W[:, :2].T + W[:, 2]).astype(np.int32)
            m = np.zeros((h_w[1], h_w[0]), np.uint8)
            cv2.fillPoly(m, [Q], 1)
            if m.sum() < 50:                       # 프레임 밖으로 나갔다
                continue
            inner = cv2.erode(m, kin, iterations=1).astype(bool)
            ring = (cv2.dilate(m, kb) - cv2.erode(m, kb)).astype(bool)
            rows.append({"seq": seq_of[f["id"]], "inside": lapvar(laps[f["id"]], inner),
                         "band": lapvar(laps[f["id"]], ring)})
        if len(rows) >= 2:
            out.append({"vp": v["name"], "split": v["split"], "obj": oid, "focus": focus,
                        "n_frames": len(v["frames"]), "frames": rows,
                        "area_px": int(cv2.contourArea(P.astype(np.float32)))})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warps", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--vp", type=int, default=40, help="몇 시야를 볼까(프레임이 많은 것부터 고르게)")
    ap.add_argument("--band", type=int, default=6)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    res = json.loads(Path(a.warps).read_text(encoding="utf-8"))
    c = connect(res["answer_db"])
    bid = c.execute("select id from viewer_runbatch where for_review").fetchone()[0]
    vps = [v for v in res["viewpoints"] if sum(f["ok"] for f in v["frames"]) >= 3]
    # 슬라이드가 고르게 들어가게 — 슬라이드마다 차례로 하나씩
    by = {}
    for v in vps:
        by.setdefault(v["name"].rpartition("_vp")[0], []).append(v)
    pick = []
    while len(pick) < a.vp and any(by.values()):
        for k in list(by):
            if by[k] and len(pick) < a.vp:
                pick.append(by[k].pop(0))
    jobs = []
    for v in pick:
        v["depth_npz"] = c.execute("select depth_npz_path from viewer_stack where viewpoint_id=?",
                                   (v["viewpoint_id"],)).fetchone()[0]
        polys = [(cid, json.loads(p)) for cid, p in c.execute(
            """select c.id, c.polygon from viewer_candidate c join viewer_detection d on d.id=c.detection_id
               join viewer_run r on r.id=d.run_id join viewer_image i on i.id=d.image_id
               where d.viewpoint_id=? and d.is_current and r.batch_id=? and i.kind='stack' and c.passed""",
            (v["viewpoint_id"], bid)) if p and p != "[]"]
        jobs.append((v, polys, a.band))
    rows = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for r in ex.map(one, jobs):
            rows += r
    Path(a.out).write_text(json.dumps({"band_px": a.band, "objects": rows}, ensure_ascii=False),
                           encoding="utf-8")
    report(rows, a.band)
    return 0


def report(rows, band) -> None:
    print(f"시야 {len({r['vp'] for r in rows})} · 개체 {len(rows)} · (개체, 판) "
          f"{sum(len(r['frames']) for r in rows)} · 띠 ±{band} px")
    for k in ("inside", "band"):
        ok = [r for r in rows if r["focus"] is not None
              and all(np.isfinite(f[k]) for f in r["frames"])]
        hit = sum(max(r["frames"], key=lambda f: f[k])["seq"] == r["focus"] for r in ok)
        near = sum(abs(max(r["frames"], key=lambda f: f[k])["seq"] - r["focus"]) <= 1 for r in ok)
        rel = np.array([f[k] / max(g[k] for g in r["frames"]) for r in ok for f in r["frames"]])
        mins = np.array([min(f[k] for f in r["frames"]) / max(f[k] for f in r["frames"]) for r in ok])
        print(f"\n[{k}] 초점 판이 맞다 {hit}/{len(ok)} ({hit / len(ok):.0%}) · ±1 판 {near / len(ok):.0%}")
        print(f"  개체 안 최소 상대값 — 가운데 {np.median(mins):.2f} · 하위 5% {np.percentile(mins, 5):.2f}")
        cells = " · ".join(f"<{t}: {np.mean(rel < t):.1%}" for t in THRESHOLDS)
        print(f"  (개체, 판) 상대값이 문턱 아래 — {cells}")
        # 크기별 — 큰 개체에서 안쪽이 약하다는 짐작을 본다
        big = [r for r in ok if r["area_px"] >= np.median([x["area_px"] for x in ok])]
        hb = sum(max(r["frames"], key=lambda f: f[k])["seq"] == r["focus"] for r in big)
        print(f"  큰 개체 절반만 — 초점 판이 맞다 {hb}/{len(big)} ({hb / max(len(big), 1):.0%})")


if __name__ == "__main__":
    sys.exit(main())
