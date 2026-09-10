#!/usr/bin/env python3
"""묶었는데 유형을 안 고른 개체에 **엔진이 합성본에서 말한 유형**을 채운다.

    python fill_object_label_from_engine.py                 # 재 보기만 (안 쓴다)
    python fill_object_label_from_engine.py --apply
    python fill_object_label_from_engine.py --apply --include-unlinked

**사용자 지시 2026-09-10.** *"내가 손을 대어, 묶어서 현재 개체로 등록이 되어
있는 것 중에, 내가 유형 결정을 하지 않아 미분류로 되어 있는 것은 오류다.
합성본을 기준으로 일괄적으로 엔진이 판정했던 유형으로 맞춘다."*

## 왜 이것이 맞는가 — 검토가 엔진값을 바탕으로 이뤄졌다

**사용자가 엔진의 판정을 놓고 검토했고, 틀린 것만 고쳤다.** 그래서 유형이
비어 있다는 것은 *"안 봤다"* 가 아니라 **"엔진값에 동의했다"** 는 뜻이다.
비워 두면 뷰어는 엔진값을 보여주지만 `DiatomObject.label` 은 비어 있어,
**화면에 보이는 것과 저장된 것이 어긋난다** — 그 어긋남이 학습 자료로
나갈 때 그 개체를 통째로 빠뜨리거나 무분류로 만든다.

> **적어 두는 반대 근거.** 사람이 **이미 유형을 매긴** 개체 693개에 이 절차를
> 그대로 적용해 보면 엔진값이 사람 유형과 **6.3%** 만 맞는다 (`round_frag` 를
> 엔진은 `round` 라 하고, `chaetoceros` 를 `rod` 라 한다). 엔진은 유형을 둘밖에
> 모르기 때문이다 — `pipeline/judge.py` 의 `classify()` 가 내는 것은
> `round`·`rod`·`None` 뿐이고 **파편도 속도 판정하지 않는다.**
>
> **그 6.3% 는 골라진 표본이라 여기 오류율이 아니다** — 사람이 손댄 것은
> 바로 엔진이 틀렸던 것들이다. 그래도 이 숫자를 남기는 이유는, 나중에 이
> 값을 학습 자료로 쓸 때 **채운 것과 사람이 고른 것이 같은 무게가 아님**을
> 알아야 하기 때문이다.

## 출처를 코멘트에 남긴다

**`DiatomObject.label` 에는 "사람이 정했다" 를 나타내는 칸이 없다**
(`Candidate.cls_user` 에 해당하는 것이 개체에는 없다). 그래서 채운 뒤에는
사람 지정과 이 일괄값을 칸으로 못 가른다 — `note` 에 표시를 남겨 두는 것이
지금 가진 유일한 자리다 (사용자 선택 2026-09-10).

    <이미 있던 글>
    [엔진값 일괄 2026-09-10]

**이미 있는 글을 지우지 않는다.** 코멘트는 사람이 적은 재생성 불가 자료다
(`merge_into_object` 가 묶을 때 잇는 것과 같은 이유). 표시가 이미 있으면
다시 붙이지 않는다 — 두 번 돌려도 같다.

## 무엇을 고르나

- 묶음: `--batch` (기본은 **검토 대상 묶음**)
- `label` 이 비어 있다
- **산 판이 있다** — 모든 판이 오검출이면 유형이 붙을 자리가 아니다
- **멤버가 둘 이상**(사람이 묶은 것). `--include-unlinked` 로 멤버 하나짜리까지
- **산 합성본 멤버**가 있고, 그 멤버의 후보에 엔진값이 있다

값이 없어 못 채우는 것은 **건너뛰고 이유를 센다** — 사람이 그린 마스크
(후보가 없다) · 합성본 판이 없는 시야 · 엔진값이 빈 후보.

## 되돌리기

`--apply` 전에 **`backup_db.py` 를 돌린다.** 되돌릴 때는 그 사본에서 이
개체들의 `label`·`note` 를 되쓰거나, 코멘트 표시로 골라 `label` 을 비운다.
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

import django

# 이 스크립트는 저장소 밖(/srv/DiaRUGA/scripts)에 복사해 두고 컨테이너 안에서
# 돌린다. Django 코드가 어디 있는지는 DIARUGA_APP 이 알려 준다 — 이미지 안의
# /app 이고, 뷰어 컨테이너가 쓰는 바로 그 코드다. 저장소에서 그냥 돌리면
# 한 단계 위가 뿌리다(스크립트가 migrate/ 안에 있다).
APP = Path(os.environ.get("DIARUGA_APP")
           or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(APP / "web"))
sys.path.append(str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diarugaweb.settings")
django.setup()

from django.db import transaction                                   # noqa: E402
from django.db.models import Count, Q                                # noqa: E402

from viewer.models import (ClassDef, DiatomObject, ObjectReview,     # noqa: E402
                           RunBatch)

MARK = "[엔진값 일괄 %s]"


def _guess_cls(elongation):
    """되살린 개체의 표시용 분류. **`web/viewer/data.py._guess_cls` 와 같아야 한다.**

    규칙이 둘이 되면 화면이 보여준 값과 여기가 채우는 값이 갈린다 — 그러면
    "화면에 보이는 것을 저장한다" 는 이 스크립트의 전제가 깨진다.
    """
    if elongation is None:
        return None
    if elongation < 1.4:
        return "round"
    return "rod" if 2.0 <= elongation <= 20.0 else None


def engine_cls(row: ObjectReview):
    """그 판정이 딛고 선 후보에 엔진이 붙인 유형. 없으면 `(값, 이유)` 의 이유.

    통과분은 `Candidate.cls` 를 그대로 쓰고, **되살린 것**(`accepted`)은
    후보가 판정을 통과하지 못해 `cls` 가 비어 있으므로 `_guess_cls` 로 짐작한다
    — 화면(`data.detection_for`)이 하는 것과 같은 갈래다.
    """
    c = row.candidate
    if c is None:
        return None, "사람이 그린 마스크 (후보가 없다)"
    if c.cls:
        return c.cls, None
    if row.accepted:
        g = _guess_cls(c.elongation)
        return (g, None) if g else (None, "되살렸으나 길이비로 짐작이 안 된다")
    return None, "후보에 엔진값이 없다"


def pick(obj: DiatomObject):
    """그 개체의 **산 합성본 멤버**. 없으면 `None`.

    `(개체, 이미지)` 유일 제약이 있어 합성본 멤버는 개체마다 많아야 하나다
    (실측으로도 208개 전부 하나였다).
    """
    for row in obj.members.all():
        if row.removed:
            continue
        if row.image and row.image.kind == "stack":
            return row
    return None


def main():
    ap = argparse.ArgumentParser(
        description="묶었는데 유형이 빈 개체에 엔진값을 채운다")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다")
    ap.add_argument("--batch", default="",
                    help="묶음 이름. 기본은 검토 대상 묶음")
    ap.add_argument("--include-unlinked", action="store_true",
                    help="멤버가 하나뿐인 개체까지 (기본은 묶인 것만)")
    ap.add_argument("--date", default="2026-09-10",
                    help="코멘트에 남길 날짜")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="개체를 하나씩 보여준다")
    args = ap.parse_args()

    if args.batch:
        batch = RunBatch.objects.filter(label=args.batch).first()
        if batch is None:
            raise SystemExit(f"그런 묶음이 없다: {args.batch}")
    else:
        batch = RunBatch.objects.filter(for_review=True).first()
        if batch is None:
            raise SystemExit("검토 대상 묶음이 정해져 있지 않다 — --batch 로 고를 것")
    print(f"묶음: {batch.label} (id={batch.pk})")

    known = set(ClassDef.objects.filter(active=True)
                .values_list("key", flat=True))

    qs = (DiatomObject.objects
          .filter(batch=batch)
          .filter(Q(label="") | Q(label__isnull=True))
          .annotate(n_mem=Count("members"),
                    n_live=Count("members", filter=Q(members__removed=False)))
          .filter(n_live__gt=0)
          .prefetch_related("members__image", "members__candidate"))
    if not args.include_unlinked:
        qs = qs.filter(n_mem__gte=2)

    plan, skip = [], Counter()
    for obj in qs:
        row = pick(obj)
        if row is None:
            skip["합성본 판이 없다"] += 1
            continue
        cls, why = engine_cls(row)
        if cls is None:
            skip[why] += 1
            continue
        if cls not in known:
            # **모르는 값을 넣지 않는다.** `ClassDef` 에 없는 키는 화면에서
            # 색도 단축키도 없이 조용히 다르게 굴러간다 (038·040).
            skip[f"ClassDef 에 없는 값: {cls}"] += 1
            continue
        plan.append((obj, cls))

    print(f"\n고른 개체 {qs.count()} · 채울 수 있는 것 {len(plan)}")
    print("\n채울 유형:")
    for k, v in Counter(c for _, c in plan).most_common():
        print(f"   {k:14s} {v:5d}")
    if skip:
        print("\n건너뛴 것:")
        for k, v in skip.most_common():
            print(f"   {k:34s} {v:5d}")

    if args.verbose:
        print("\n개체별:")
        for obj, cls in plan[:80]:
            print(f"   obj#{obj.pk:6d} 시야{obj.viewpoint_id:5d} "
                  f"멤버{obj.members.count():2d} → {cls}")
        if len(plan) > 80:
            print(f"   … 그리고 {len(plan) - 80}개 더")

    if not args.apply:
        print("\n--apply 를 주지 않아 아무것도 안 썼다")
        return

    mark = MARK % args.date
    n = 0
    with transaction.atomic():
        for obj, cls in plan:
            note = (obj.note or "").strip()
            if mark not in note:
                note = f"{note}\n{mark}".strip() if note else mark
            DiatomObject.objects.filter(pk=obj.pk).update(label=cls, note=note)
            n += 1
    print(f"\n{n}개의 유형을 채웠다. 코멘트에 {mark} 를 남겼다")
    print("check_db.py 를 돌려 볼 것")


if __name__ == "__main__":
    main()
