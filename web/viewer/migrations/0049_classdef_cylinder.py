"""원통상 묶음을 세우고 Dactyliosolen·원통상 파편을 더한다 (224 · 사용자 2026-10-21).

**Dactyliosolen 은 원형도 봉상도 아니다.** 도감을 보고 Rhizosolenia 와 같은
원통상으로 묶기로 했다 — 둘은 가르는 분류로 두고, 묶음(`ClassGroup`)이 화면에서
합쳐 센다. 파편은 드물지만 원통상 파편으로 따로 둔다(세지 않는다).

| 칸 | Dactyliosolen | 원통상 파편 |
|---|---|---|
| short | `DAC` (`RHZ`·`CRS` 와 같은 모양) | `원통파편` (여덟 칸 시험이 비운 것을 잡는다) |
| badge | `dac` | `cylf` (`rndf`·`rodf` 와 같은 모양) |
| color | Rhizosolenia 와 같은 연보라 (사용자) | 연보라를 흰색 쪽으로 40% (0015 의 파편 색과 같은 셈) |
| hotkey | `t` — 순환이 Rhizosolenia → Dactyliosolen → 원통상 파편 | |
| counted | 참 | 거짓 |
| is_taxon | 참 | 거짓 |

**`base.html` 의 CSS 여덟 자리도 함께 간다** (`0037` 머리말).

**이미 원형으로 적어 둔 Dactyliosolen 을 옮긴다** (사용자 2026-10-21). `0037` 은
"기계가 옮기지 않는다" 였는데 그때와 다르다 — 그때는 봉상 중 어느 것이
Rhizosolenia 인지를 기계가 정해야 했고, 이번에는 **사람이 종명으로 이미 적어
둔 것**이다(10-21 사본으로 19개, 전부 `round`). 판단은 사람의 것이고 칸만
옮긴다. 같은 마이그레이션에 넣은 것은 **분류만 생기고 자료는 원형에 남는 틈이
없게** 하려는 것이다.
"""
from django.db import migrations

GROUP = {"key": "cylinder", "label": "원통상", "short": "원통", "sort_order": 0}

ROWS = [
    {"key": "dactyliosolen", "label": "Dactyliosolen", "short": "DAC",
     "badge": "dac", "color": "185,130,255", "hotkey": "t",
     "is_taxon": True, "counted": True, "sort_order": 7, "active": True},
    {"key": "cylinder_frag", "label": "원통상 파편", "short": "원통파편",
     "badge": "cylf", "color": "213,180,255", "hotkey": "t",
     "is_taxon": False, "counted": False, "sort_order": 8, "active": True},
]
MEMBERS = ("rhizosolenia", "dactyliosolen", "cylinder_frag")


def add(apps, schema_editor):
    ClassDef = apps.get_model("viewer", "ClassDef")
    ClassGroup = apps.get_model("viewer", "ClassGroup")
    DiatomObject = apps.get_model("viewer", "DiatomObject")

    g, _ = ClassGroup.objects.update_or_create(key=GROUP["key"], defaults=GROUP)
    for row in ROWS:
        ClassDef.objects.update_or_create(key=row["key"], defaults=row)
    ClassDef.objects.filter(key__in=MEMBERS).update(group=g)

    # `update()` 라 `updated_at` 이 안 바뀐다 — 사람이 마지막으로 만진 시각이
    # 이 이전으로 남는다
    DiatomObject.objects.filter(
        label="round", species__istartswith="Dactyliosolen"
    ).update(label="dactyliosolen")


def remove(apps, schema_editor):
    """되돌리면 분류를 끄고(`0014`·`0037` 과 같다) 옮긴 개체를 원형으로 돌린다.

    **배포 뒤 사람이 Dactyliosolen 으로 붙인 것도 함께 돌아간다** — 종명이
    Dactyliosolen 이 아니면 원형이 아닐 수 있어 그것은 그대로 둔다(분류가 꺼져도
    붙은 교정은 읽힌다).
    """
    ClassDef = apps.get_model("viewer", "ClassDef")
    DiatomObject = apps.get_model("viewer", "DiatomObject")
    DiatomObject.objects.filter(
        label="dactyliosolen", species__istartswith="Dactyliosolen"
    ).update(label="round")
    ClassDef.objects.filter(key__in=[r["key"] for r in ROWS]).update(active=False)
    ClassDef.objects.filter(key__in=MEMBERS).update(group=None)


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0048_classgroup"),
    ]

    operations = [migrations.RunPython(add, remove)]
