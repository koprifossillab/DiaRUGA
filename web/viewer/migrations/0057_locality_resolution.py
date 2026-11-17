"""지점마다 산출 해상도 — 저해상도(200) · 고해상도(400) (P36).

**칸을 더하기만 한다.** `db_default` 가 있어 이 칸을 모르는 옛 파이프라인 이미지의
INSERT 도 받는다 — **파이프라인 이미지는 안 굽는다.** 옛 행은 전부 저해상도가 된다
(사용자 11-17: 기본은 저해상도). RS14-GC04 를 고해상도로 바꾸는 것은 배포 뒤 정보
편집 화면에서 한다 — 지점 코드를 마이그레이션에 박으면 테스트 사본·새 설치에서
뜻이 없다. 되돌리면 칸을 걷는다(고른 값이 사라진다 — 다시 고르면 된다).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0056_locality_tally_taxa'),
    ]

    operations = [
        migrations.AddField(
            model_name='locality',
            name='resolution',
            field=models.CharField(choices=[('low', '저해상도'), ('high', '고해상도')],
                                   db_default='low', default='low', max_length=8),
        ),
    ]
