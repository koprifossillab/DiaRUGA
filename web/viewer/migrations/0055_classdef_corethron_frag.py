"""분류에 Corethron 파편을 더한다 (252 · 사용자 2026-11-09).

0051 의 Eucampia 파편과 같은 이유다 — 속으로 알아본 것의 파편을 원형·봉상
파편에 섞어 붙이면 나중에 가를 수 없다. **갈라 둔 것은 언제든 합칠 수 있다.**

| 칸 | 값 | 왜 |
|---|---|---|
| short | `Cor파편` | `Euc파편` 과 같은 모양 |
| badge | `corf` | `eucf`·`rndf`·`cylf` 와 같은 모양 |
| color | `237,156,246` (#ed9cf6) | Corethron 자홍을 흰색 쪽으로 40% (0015·0049·0051 의 파편 색과 같은 셈) |
| hotkey | 비움 | Corethron 이 일부러 비워 둔 것(0050)을 따른다. 우클릭 메뉴·카탈로그 셀렉트로 지정한다 |
| counted | 거짓 | 파편은 세지 않는다 |
| is_taxon | 참 | 속으로 알아본 것이다. 메뉴에서 Corethron 바로 뒤에 놓인다 |
| sort_order | 9 | Corethron 과 같다 — 차례가 `(sort_order, key)` 라 `corethron` 바로 뒤에 온다 |

**YOLO 는 Corethron 과 같이 「기타」 로 간다** — `export_yolo.py` 의 대응표에
없으면 `other` 다. 고칠 것이 없다.

`base.html` 의 CSS 여덟 자리도 함께 간다(`0037` 머리말). 되돌리기는 지우지 않고 끈다.
"""
from django.db import migrations

ROW = {
    "key": "corethron_frag", "label": "Corethron 파편", "short": "Cor파편",
    "badge": "corf", "color": "237,156,246", "hotkey": "",
    "is_taxon": True, "counted": False, "sort_order": 9, "active": True,
}


def add(apps, schema_editor):
    apps.get_model("viewer", "ClassDef").objects.update_or_create(
        key=ROW["key"], defaults=ROW)


def remove(apps, schema_editor):
    apps.get_model("viewer", "ClassDef").objects.filter(
        key=ROW["key"]).update(active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0054_site_region_seas"),
    ]

    operations = [migrations.RunPython(add, remove)]
