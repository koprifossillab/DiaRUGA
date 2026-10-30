"""남극 지역의 해역(`Site.region`)을 채운다 (사용자 2026-10-30).

첫 화면의 표·카드·지도 나무가 해역 → 지역 → 지점으로 묶인다(`data.by_sea`).
해역은 새 칸이 아니라 원래 그 뜻의 `Site.region` 이다 — 그런데 로스해의 넷과
엘리펀트섬이 비어 있어 한 머리에 못 모였다.

| 지역 | 해역 |
|---|---|
| RS14 · RS19 · RS21 · RS23 | 로스해 |
| GC03 (Elephant Island) | 남극반도 |

AM22 는 이미 `아문젠해` 다.

**빈 칸만 채운다** — 사람이 넣은 값은 안 덮는다(CLAUDE.md "자동값이 사람이 채운
것을 덮으면 안 된다"). 남극(`area=ant`)의 그 코드만 본다. 지역이 없는 DB(시험 ·
새로 만든 것)에서는 아무것도 안 한다.

**번호는 0054 다** — 같은 날 어드민의 v0.39.0 이 `0053_candidate_engine_cls` 를
먼저 냈다. 처음 0053 으로 짠 것을 그 뒤로 옮겼다(두 마이그레이션은 서로 다른
테이블만 만진다).

## 되돌리기

이 마이그레이션이 넣은 값 그대로인 행만 비운다. 그 사이 사람이 다른 값으로
고쳤으면 그것은 남는다 — 같은 값으로 고친 것까지는 가를 수 없다.
"""
from django.db import migrations

SEAS = {
    "RS14": "로스해", "RS19": "로스해", "RS21": "로스해", "RS23": "로스해",
    "GC03": "남극반도",
}


def fill(apps, schema_editor):
    Site = apps.get_model("viewer", "Site")
    for code, sea in SEAS.items():
        Site.objects.filter(area="ant", code=code, region="").update(region=sea)


def unfill(apps, schema_editor):
    Site = apps.get_model("viewer", "Site")
    for code, sea in SEAS.items():
        Site.objects.filter(area="ant", code=code, region=sea).update(region="")


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0053_candidate_engine_cls"),
    ]

    operations = [
        migrations.RunPython(fill, unfill),
    ]
