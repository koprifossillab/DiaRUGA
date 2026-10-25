"""분류에 Eucampia 파편을 더한다 (237 · 사용자 2026-10-25).

지금까지 Eucampia 의 파편은 원형 파편으로 붙여 왔다. 그러면 원형 파편 하나에
생김새가 다른 둘이 섞인다 — P29 가 개체/파편 두 클래스를 버린 근거("파편의
기준이 계열마다 갈린다")가 여기에도 그대로 걸린다. **섞인 것은 나중에 가르기
어렵고, 갈라 둔 것은 언제든 합칠 수 있다.** 그래서 라벨부터 가른다.

| 칸 | 값 | 왜 |
|---|---|---|
| short | `Euc파편` | `원통파편` 과 같은 모양 |
| badge | `eucf` | `rndf`·`rodf`·`cylf` 와 같은 모양 |
| color | `255,168,216` (#ffa8d8) | Eucampia 분홍을 흰색 쪽으로 40% (0015·0049 의 파편 색과 같은 셈) |
| hotkey | `e` | **순환에 넣는다**(사용자) — Eucampia → Eucampia 파편 → Eucampia … |
| counted | 거짓 | 파편은 세지 않는다 |
| is_taxon | 참 | 속으로 알아본 것이다. 메뉴에서도 Eucampia 바로 뒤에 놓인다 |
| sort_order | 4 | Eucampia 와 같다 — 차례가 `(sort_order, key)` 라 `eucampia` 바로 뒤에 온다. 뒤 분류의 번호를 안 밀어도 된다 |

**이미 원형 파편으로 붙인 것은 옮기지 않는다.** 0049 의 Dactyliosolen 과 달리
사람이 Eucampia 라고 적어 둔 자리가 없다 — 어느 원형 파편이 Eucampia 의 것인지는
사람이 다시 봐야 안다.

**YOLO 4차에서는 원형 파편 클래스로 보낸다**(P29 3절). 수가 모이면 뗀다.

`base.html` 의 CSS 여덟 자리도 함께 간다(`0037` 머리말). 되돌리기는 지우지 않고 끈다.
"""
from django.db import migrations

ROW = {
    "key": "eucampia_frag", "label": "Eucampia 파편", "short": "Euc파편",
    "badge": "eucf", "color": "255,168,216", "hotkey": "e",
    "is_taxon": True, "counted": False, "sort_order": 4, "active": True,
}


def add(apps, schema_editor):
    apps.get_model("viewer", "ClassDef").objects.update_or_create(
        key=ROW["key"], defaults=ROW)


def remove(apps, schema_editor):
    apps.get_model("viewer", "ClassDef").objects.filter(
        key=ROW["key"]).update(active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0050_classdef_corethron"),
    ]

    operations = [migrations.RunPython(add, remove)]
