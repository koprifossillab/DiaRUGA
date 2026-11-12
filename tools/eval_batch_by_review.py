"""검토가 끝난 슬라이드로 검출 묶음의 정확도를 센다 (256).

사람이 검토 완료를 누른 시야만 본다. 그 시야에서 —

- 묶음이 통과시킨 후보 중 **안 지운 것 = 맞음**, **지운 것 = 오검출**
- 사람이 **새로 그린 것**(`source="manual"`)과 **되살린 탈락 후보 = 놓침**
- 유형은 사람이 안 건드렸으면 동의로 센다(사용자 2026-11-12)

**운영 DB 를 열지 않는다** (132) — `/data3/DiaRUGA/backup/` 의 사본을 준다.
Django 를 안 쓰고 sqlite3 로 읽기 전용(`immutable=1`)으로 연다 — `export_review.py`
와 같은 자리다. 검토 직후라면 다음 시간별 백업(매시 20분)을 기다렸다 센다.

    python tools/eval_batch_by_review.py <백업.db> [--slide 20] [--batch 9]

기본값은 RS14-GC04 6cm(`slide 20`) · `yolo-4.1차`(`batch 9`) 다. 놓친 그림과
후보의 대응은 bbox IoU 로 맞춘다(0.5 이상 / 0.2 이상 부분 겹침).
"""
import argparse, sqlite3, collections, json, statistics as st
ap = argparse.ArgumentParser()
ap.add_argument("db"); ap.add_argument("--slide", type=int, default=20)
ap.add_argument("--batch", type=int, default=9)
A = ap.parse_args(); DB, SLIDE, BATCH = A.db, A.slide, A.batch
c = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True); c.row_factory = sqlite3.Row
q = lambda s, *a: c.execute(s, a).fetchall()
allv = q("select id,idx from viewer_viewpoint where slide_id=? order by idx", SLIDE)
vps = q("""select v.id,v.idx from viewer_viewpoint v join viewer_viewpointreview r on r.viewpoint_id=v.id
           where v.slide_id=? and r.batch_id=? and r.done order by v.idx""", SLIDE, BATCH)
counted = {r['key']: r['counted'] for r in q("select key,counted from viewer_classdef")}
print(f"DB {DB}\n시야 {len(allv)}개 중 검토 완료 {len(vps)}개 · 미완 idx",
      sorted(set(r['idx'] for r in allv) - set(r['idx'] for r in vps)))
def iou(a, b):
    iw = min(a[0]+a[2], b[0]+b[2]) - max(a[0], b[0]); ih = min(a[1]+a[3], b[1]+b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0: return 0
    i = iw*ih; return i/(a[2]*a[3]+b[2]*b[3]-i)
T = collections.Counter(); cm = collections.Counter(); missk = collections.Counter()
fin_tp = collections.Counter(); fin_miss = collections.Counter(); fpc = collections.Counter(); passc = collections.Counter()
conf_tp, conf_fp, small = [], [], 0
for v in vps:
    um = q("""select d.um_per_pixel from viewer_detection d join viewer_run r on r.id=d.run_id
              where d.viewpoint_id=? and r.batch_id=? and d.is_current""", v['id'], BATCH)[0][0]
    cands = q("""select ca.* from viewer_candidate ca join viewer_detection d on d.id=ca.detection_id
                 join viewer_run r on r.id=d.run_id where d.viewpoint_id=? and r.batch_id=? and d.is_current""", v['id'], BATCH)
    revs = q("""select o.*,do.label from viewer_objectreview o left join viewer_diatomobject do on do.id=o.diatom_object_id
                where o.viewpoint_id=? and (o.batch_id=? or o.batch_id is null)""", v['id'], BATCH)
    byc = {r['candidate_id']: r for r in revs if r['candidate_id']}
    t = collections.Counter()
    for ca in cands:
        r = byc.get(ca['id'])
        if ca['passed']:
            passc[ca['engine_cls']] += 1
            if r is None: t['통과인데 판정 없음'] += 1; continue
            if r['removed']: t['FP'] += 1; fpc[ca['engine_cls']] += 1; conf_fp.append(ca['predicted_iou'])
            else:
                t['TP'] += 1; conf_tp.append(ca['predicted_iou'])
                fin = r['label'] or ca['cls']; fin_tp[fin] += 1; cm[(ca['engine_cls'], fin)] += 1
        elif r is not None and r['accepted'] and not r['removed']:
            t['되살림'] += 1; fin_miss[r['label'] or ca['cls'] or '?'] += 1
    for m in revs:
        if m['source'] != 'manual' or m['removed']: continue
        bb = json.loads(m['geom'])['bbox']; best = ('', 0)
        for ca in cands:
            r = byc.get(ca['id']); i = iou(bb, (ca['bbox_x'], ca['bbox_y'], ca['bbox_w'], ca['bbox_h']))
            kind = ('지운 통과 후보' if (r is not None and r['removed']) else '남긴 통과 후보') if ca['passed'] else '탈락:' + ca['reject']
            if i > best[1]: best = (kind, i)
        missk[best[0] if best[1] >= 0.5 else ('부분 겹침' if best[1] >= 0.2 else '후보 없음')] += 1
        t['그림'] += 1; fin_miss[m['label'] or '?'] += 1
        if max(bb[2], bb[3]) * um < 10: small += 1
    print(f"  g{v['idx']:<3}", dict(t)); T.update(t)
TP, FP, M, R = T['TP'], T['FP'], T['그림'], T['되살림']
print("합계", dict(T))
print(f"정밀도 {TP}/{TP+FP} = {TP/(TP+FP):.3f} · 재현율 {TP}/{TP+M+R} = {TP/(TP+M+R):.3f}")
truth = fin_tp + fin_miss
print(f"사람이 인정한 개체 {sum(truth.values())} · 세는 유형(완형) {sum(n for k,n in truth.items() if counted.get(k))}")
print("유형별  정답수 · 잡음 · 재현율 | (YOLO 클래스 기준) 통과 · 오검출")
for k in sorted(truth):
    print(f"  {k:15} {truth[k]:4} {fin_tp[k]:4} {fin_tp[k]/truth[k]:.2f}")
for k in sorted(passc): print(f"  yolo:{k:12} 통과 {passc[k]:4} 오검출 {fpc[k]:4} 정밀도 {1-fpc[k]/passc[k]:.2f}")
w = lambda ks: (sum(fin_tp[k] for k in ks), sum(truth[k] for k in ks))
a, b = w([k for k in truth if counted.get(k)]); print(f"완형 재현율 {a}/{b} = {a/b:.3f}")
a, b = w([k for k in truth if not counted.get(k)]); print(f"파편 재현율 {a}/{b} = {a/b:.3f}")
print("놓친 그림의 가장 가까운 후보:", dict(missk), f"· 긴 변 10µm 미만 {small}")
agree = sum(n for (e, f), n in cm.items() if e == f)
print(f"유형 일치 {agree}/{TP} = {agree/TP:.3f}; 어긋남:", {f"{e}→{f}": n for (e, f), n in sorted(cm.items(), key=lambda x: -x[1]) if e != f})
print(f"신뢰도 중앙값 맞음 {st.median(conf_tp):.3f} · 오검출 {st.median(conf_fp):.3f}")
for th in (0.01, 0.05, 0.1, 0.2, 0.3):
    x = sum(p >= th for p in conf_tp); y = sum(p >= th for p in conf_fp)
    print(f"  conf≥{th}: 정밀도 {x/(x+y):.3f} 재현율 {x/(TP+M+R):.3f}")
