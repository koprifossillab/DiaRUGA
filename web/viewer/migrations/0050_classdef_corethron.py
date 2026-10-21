"""분류에 Corethron 을 더한다 (227 · 사용자 2026-10-21).

지금까지의 시료에서는 대단히 드문데 **앞으로 많이 나올 것**이라 미리 걸어 둔다
(사용자). 속이고 센다. 묶음에는 안 든다. YOLO 4차에서는 「기타」 클래스로 가
화면에 미분류로 뜬다(P29) — 라벨이 Corethron 으로 쌓이니 모이면 뗀다.

| 칸 | 값 | 왜 |
|---|---|---|
| short | `COR` | 다른 속(`CRS`·`RHZ`·`DAC`)과 같은 모양 |
| badge | `cor` | `base.html` 의 `.badge.cor` 와 짝 |
| color | `225,90,240` (#e15af0 · 자홍) | 쓰이는 색 사이 가장 넓은 빈자리 — 원통상 보라 266° 와 Eucampia 분홍 327° 사이 약 292°. 청록(~178°)은 화면의 강조색(하늘 197°)과 18° 라 접었다 |
| hotkey | 비움 | **사용자가 일부러 비웠다** — 앞으로 단축키 없는 분류가 많아진다. 우클릭 메뉴·카탈로그 셀렉트로 지정한다 |
| counted · is_taxon | 참 · 참 | |

`base.html` 의 CSS 여덟 자리도 함께 간다(`0037` 머리말). 되돌리기는 지우지 않고 끈다.
"""
from django.db import migrations

ROW = {
    "key": "corethron", "label": "Corethron", "short": "COR",
    "badge": "cor", "color": "225,90,240", "hotkey": "",
    "is_taxon": True, "counted": True, "sort_order": 9, "active": True,
}


def add(apps, schema_editor):
    apps.get_model("viewer", "ClassDef").objects.update_or_create(
        key=ROW["key"], defaults=ROW)


def remove(apps, schema_editor):
    apps.get_model("viewer", "ClassDef").objects.filter(
        key=ROW["key"]).update(active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0049_classdef_cylinder"),
    ]

    operations = [migrations.RunPython(add, remove)]
