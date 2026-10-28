"""손그림 개체의 빈 유형을 카드에 보이던 값으로 채운다 (일회성 · 2026-10-28).

손그림은 엔진값이 없어 `DiatomObject.label` 이 비면 유형이 없다. 그런데 다른
판(엔진 후보)과 묶여 있으면 `fold_object_cls` 가 그 판들의 엔진 추측을 끌어와
카드에 그린다 — 화면에는 유형이 있는데 "유형 미지정 · 손그림" 칩에 걸린다.
사용자가 최종 검수에서 그 값을 보고 넘겼으므로 그대로 사람의 지정으로 적는다.

    dbrun.sh fill_folded_cls.py --slide 260731_rs23-gc03_369cm            # 보기만
    dbrun.sh fill_folded_cls.py --slide 260731_rs23-gc03_369cm --apply

**칩과 같은 줄을 고른다** — `catalog_rows` 에서 사람 지정이 없고(`cls_user`)
손그림이고(`source=manual`) 접힌 값(`cls_folded`)이 있는 카드. 엔진값도 접힌
값도 없는 손그림은 건드리지 않는다(채울 근거가 없다).
"""
import argparse
import os
import sys
from pathlib import Path

import django

# `ops/check_db.py` 의 머리와 같다 — 컨테이너에서는 DIARUGA_APP 이 /app 이다.
APP = Path(os.environ.get("DIARUGA_APP")
          or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(APP / "web"))
sys.path.append(str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diarugaweb.settings")
django.setup()

from django.db import transaction                                  # noqa: E402

from viewer import data                                            # noqa: E402
from viewer.models import DiatomObject                             # noqa: E402


def targets(slug):
    out = {}
    for r in data.catalog_rows(slug):
        if r.get("cls_user") or r.get("source") != "manual":
            continue
        if not (r.get("cls_folded") and r.get("cls")):
            continue
        out[r["obj_id"]] = (r["cls"], r.get("catalog_no") or "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slide", required=True, action="append")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    for slug in a.slide:
        want = targets(slug)
        print(f"{slug}: {len(want)}")
        for oid, (cls, no) in sorted(want.items()):
            print(f"  obj {oid:>6}  {no:<16} → {cls}")
        if not a.apply or not want:
            continue
        with transaction.atomic():
            n = 0
            for dobj in DiatomObject.objects.filter(pk__in=want):
                if dobj.label:            # 그 사이 사람이 고른 것은 안 덮는다
                    continue
                dobj.label = want[dobj.pk][0]
                data.check_grade_pose(dobj.label, dobj.grade, dobj.pose)
                dobj.save(update_fields=["label", "updated_at"])
                n += 1
        print(f"  적었다: {n}")
        left = targets(slug)
        print(f"  남은 것: {len(left)}")


if __name__ == "__main__":
    main()
