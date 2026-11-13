"""지점마다 산출 그래프의 기본 종 목록 (P34 5단계 · 259).

**칸을 더하기만 한다.** 다만 SQLite 에서는 `ALTER TABLE ADD COLUMN` 한 줄이 아니다 —
JSON 칸에 `JSON_VALID` 검사 제약이 붙어 Django 가 **`viewer_locality` 를 새로 만들고
행을 옮긴다**(`sqlmigrate` 로 확인). 지점은 수십 행이라 순간이고, 사본에서 돌려
지점 수 · 지점마다의 시료 수 · 코어 자료(`CoreSeries`) 소속이 그대로인 것을 봤다
(259). 걷는 칸이 없어 다른 테이블의 FK 가 그대로 산다.

`db_default` 가 있어 이 칸을 모르는 옛 파이프라인 이미지의 INSERT 도 받는다 —
**파이프라인 이미지는 안 굽는다.** 되돌리면 칸을 걷는다(사람이 저장한 목록이
사라진다 — 그래프 화면에서 다시 고르면 된다).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0055_classdef_corethron_frag'),
    ]

    operations = [
        migrations.AddField(
            model_name='locality',
            name='tally_taxa',
            field=models.JSONField(blank=True, db_default=[], default=list),
        ),
    ]
