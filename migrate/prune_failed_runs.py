#!/usr/bin/env python3
"""저장 도중에 죽은 실행이 남긴 검출 찌꺼기를 지운다 (198).

    deploy/host/dbsync.sh prune_failed_runs.py
    deploy/host/dbrun.sh  prune_failed_runs.py                    # 세어만 본다
    deploy/host/dbrun.sh  prune_failed_runs.py --apply
    deploy/host/dbrun.sh  prune_failed_runs.py --error "no such column" --since 2026-09-15

## 왜 생기나

`segment_diatoms.save_detection` 은 트랜잭션이 둘이다 — 첫 번째가 `Detection`
과 `Candidate` 를 쓰고 잠금을 놓은 뒤, 두 번째가 `is_current` 를 옮기고
교정을 다시 맺는다(rebind). **두 번째에서 죽으면 첫 번째는 이미 커밋돼 있다.**
그 실행은 `failed` 로 닫히지만 검출 행은 `is_current=False` 인 채로 남고,
폴러가 1분마다 같은 슬라이드를 다시 돌리므로 **같은 이미지에 실패 하나마다
행이 하나씩 쌓인다.** 09-15 에 파이프라인 이미지(`v0.5.2`)가 DB 스키마(`0036`
이후)를 몰라 그렇게 됐다 — 이틀 사이 실행 4,212개 · 후보 90만 행 · 530 MB.

`ops/prune_detections.py` 는 이 자리에 안 맞는다. 그것은 이미지마다 **하나를
남기는** 규칙이라 실패가 남긴 것 중 가장 새것을 "화면이 그릴 것" 으로 남긴다.
여기서는 **실패한 실행이 남긴 것은 전부 찌꺼기**다 — 성공한 실행이 아직 없는
이미지라도 남길 것이 없다.

## 무엇을 지우나

`status='failed'` 이고 `error` 에 주어진 문자열이 든 `Run` 과, 그 실행이 남긴
`Detection`(→ `Candidate` 는 CASCADE). 지우기 전에 셋을 확인한다 —
어느 것 하나라도 걸리면 **아무것도 안 지우고 멈춘다**:

- 지울 검출 중 `is_current=True` 가 없다 (있으면 실패가 아니라 화면이 보는 것)
- 지울 검출의 후보를 가리키는 `ObjectReview` 가 없다 (`SET_NULL` 이라 지워지진
  않지만, 그 교정은 orphan 이 된다 — 사람이 봐야 한다)
- 지울 검출을 `superseded_by` 로 가리키는 **다른** 검출이 없다

`Detection.run` 은 `SET_NULL` 이라 `Run` 을 지워도 검출은 안 따라온다 — 검출을
먼저 짚어 지우고 실행을 지운다. `--apply` 전에 `backup_db.py` 를 돌릴 것.
"""
import argparse
import os
import sys
from pathlib import Path

import django

# /srv/DiaRUGA/scripts 에 복사해 컨테이너 안에서 돌 때 Django 코드가 어디
# 있는지는 DIARUGA_APP 이 알려 준다 (check_db.py 와 같은 규약).
APP = Path(os.environ.get("DIARUGA_APP")
          or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(APP / "web"))
sys.path.append(str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diarugaweb.settings")
django.setup()

from django.db import transaction                                   # noqa: E402
from viewer.models import Candidate, Detection, ObjectReview, Run   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--error", default="no such column: viewer_objectreview.note",
                    help="Run.error 에 이 문자열이 든 실패만 (기본: 198 의 그 오류)")
    ap.add_argument("--since", default="2026-09-15",
                    help="이 날짜(KST 자정 · YYYY-MM-DD) 이후에 시작한 실행만")
    ap.add_argument("--apply", action="store_true", help="실제로 지운다")
    args = ap.parse_args()

    runs = (Run.objects.filter(status="failed", error__contains=args.error,
                               started_at__date__gte=args.since)
            .order_by("pk"))
    run_ids = list(runs.values_list("pk", flat=True))
    dets = Detection.objects.filter(run_id__in=run_ids)
    det_ids = list(dets.values_list("pk", flat=True))
    n_cand = Candidate.objects.filter(detection_id__in=det_ids).count()
    images = dets.values_list("image__path", flat=True).distinct()

    print(f"실패한 실행 {len(run_ids)}개 · 검출 {len(det_ids)}개 · 후보 {n_cand:,}개")
    print(f"  실행 번호 {run_ids[0] if run_ids else '-'} ~ {run_ids[-1] if run_ids else '-'}")
    for p in images:
        print(f"  {p}")
    if not run_ids:
        return 0

    bad = 0
    n = dets.filter(is_current=True).count()
    if n:
        print(f"!! is_current 인 검출이 {n}개 있다 — 실패가 남긴 것이 아니다")
        bad += 1
    n = ObjectReview.objects.filter(candidate__detection_id__in=det_ids).count()
    if n:
        print(f"!! 이 검출의 후보에 교정 {n}건이 붙어 있다 — 지우면 orphan 이 된다")
        bad += 1
    n = (Detection.objects.filter(superseded_by_id__in=det_ids)
         .exclude(pk__in=det_ids).count())
    if n:
        print(f"!! 다른 검출 {n}개가 이것을 superseded_by 로 가리킨다")
        bad += 1
    if bad:
        print("아무것도 안 지운다.")
        return 1

    if not args.apply:
        print("(세어만 봤다 — 지우려면 --apply)")
        return 0

    with transaction.atomic():
        # CASCADE 로 후보가 따라간다. 한 번에 짚으면 SQLite 의 변수 상한(999 →
        # 32,766)에 걸릴 수 있어 검출 번호를 나눠 지운다.
        for i in range(0, len(det_ids), 500):
            Detection.objects.filter(pk__in=det_ids[i:i + 500]).delete()
        runs.delete()
    print(f"지웠다 — 실행 {len(run_ids)}개 · 검출 {len(det_ids)}개 · 후보 {n_cand:,}개")
    print("파일 크기는 VACUUM 을 해야 준다 (WAL 이라 폴러가 멈춘 사이에).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
