"""후보에 엔진이 낸 클래스를 담는 칸을 더한다 (P29 6절 4 · 246).

**더하기만이다** — `db_default=""` 라 이 칸을 모르는 옛 파이프라인 이미지(`v0.5.3`)의
INSERT 가 그대로 돈다. 기존 후보는 전부 빈 값이고, 빈 값은 `judge.classify` 가 지금까지의
형태 규칙으로 판정하는 갈래다 — 저장된 판정이 하나도 안 바뀐다(`check_db` 1번).

되돌리면 칸이 걷힌다. 4차 검출이 이미 들어온 뒤라면 그 클래스가 함께 사라지고, 다시
걸렀을 때(`refilter`) 형태 규칙으로 판정이 바뀐다 — 되돌리기 전에 볼 것.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0052_runbatch_frozen_viewpoint_batch"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidate",
            name="engine_cls",
            field=models.CharField(blank=True, db_default="", default="", max_length=32),
        ),
    ]
