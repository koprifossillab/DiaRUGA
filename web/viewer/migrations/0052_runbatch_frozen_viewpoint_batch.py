"""시야의 주 묶음 칸과 얼린 묶음 표시를 더한다 (P31 · P32 · 사용자 2026-10-28).

**더하기만이다** — 두 칸 다 비거나(`Viewpoint.batch` null) 거짓(`db_default`)으로
들어가서, 이 칸을 모르는 옛 파이프라인 이미지의 INSERT 가 그대로 돈다. 파이프라인
이미지를 굽지 않는다(CLAUDE.md "스키마를 조이는 마이그레이션").

## 채우는 것 — 따라가면 안 되는 시야만

칸이 비면 주 묶음은 따라간다(`data.primary_batch_id`). 채우는 것은 그러면 안 되는
시야뿐이다:

| 시야 | 주 묶음 | 까닭 |
|---|---|---|
| `yolo-3차` 에서 검토 완료 | `yolo-3차` | 3차 정답(P31 ③). 검토 대상을 4차로 옮겨도 남는다 |
| 한국(`Site.area=kr`) · 관찰 이름표 `Smear` | `sam2-전수` | SAM 으로만 본다(08-26 · P29 4절). 한국 BP 두 슬라이드에는 예전에 잘못 들어간 `yolo-3차` 검출이 있어(`batch_scope.py` 머리말) 따라가게 두면 그것이 열린다 |

그리고 **`yolo-3차` 를 얼린다**(P32 ②) — 10-28 15:14 에 최종 검수가 끝났다.

**묶음을 이름으로 찾는다.** 이 마이그레이션은 한 번 도는 자료 결정이라 운영의
이름을 그대로 쓴다. 이름이 없는 DB(시험 · 새로 만든 것)에서는 아무것도 안 한다.

## 되돌리기

칸을 걷으면 채운 값도 함께 사라진다 — 따로 할 일이 없다. 옛 판으로 돌아가면
전역 검토 대상 하나로 보던 때로 돌아간다(얼림도 없다).
"""
import django.db.models.deletion
from django.db import migrations, models

ANSWER = "yolo-3차"
SAM = "sam2-전수"


def fill(apps, schema_editor):
    RunBatch = apps.get_model("viewer", "RunBatch")
    Viewpoint = apps.get_model("viewer", "Viewpoint")

    answer = RunBatch.objects.filter(label=ANSWER).first()
    if answer is not None:
        Viewpoint.objects.filter(
            reviews__batch=answer, reviews__done=True
        ).update(batch=answer)
        RunBatch.objects.filter(pk=answer.pk).update(frozen=True)

    sam = RunBatch.objects.filter(label=SAM).first()
    if sam is not None:
        # 정답으로 채운 시야는 건드리지 않는다 — 10-28 에는 겹치는 것이 없지만
        # 겹치면 정답 쪽이 이긴다
        loose = Viewpoint.objects.filter(batch__isnull=True)
        loose.filter(slide__sample__locality__site__area="kr").update(batch=sam)
        loose.filter(slide__obs_label="Smear").update(batch=sam)


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0051_classdef_eucampia_frag"),
    ]

    operations = [
        migrations.AddField(
            model_name="runbatch",
            name="frozen",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="viewpoint",
            name="batch",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_viewpoints", to="viewer.runbatch"),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
