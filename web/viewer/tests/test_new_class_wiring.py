"""분류를 더할 때 **빠지기 쉬운 자리**들 (`ClassDef` 머리말 · 038·040).

배지 CSS 는 `test_classdef_css.py` 가 본다. 여기서 보는 것은 **분류 목록을 손으로
적어 둔 자리**다 — 표에 행을 넣어도 그런 자리는 안 따라오고, **예외도 경고도 없이
그 분류만 조용히 다르게 굴러간다.**

실제로 그렇게 되어 있었다: 개수 줄이 다섯을 박아 두어서
(`rod`·`round`·`rod_frag`·`round_frag`·`eucampia`) **Chaetoceros 는 표에 든 뒤로도
개수 줄에 한 번도 안 나왔다.** `v0.10.x` 부터 `v0.13.0` 까지 그랬다.
"""
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data
from ..models import ClassDef


class CountLineTest(DiaRUGATestCase):
    """개수 줄이 **표에 든 분류를 다 센다.**"""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=1, n_candidates=3)

    def test_표의_분류를_손으로_적지_않는다(self):
        """표에만 있는 분류를 세어도 개수 줄에 낀다 — 코드를 안 고쳐도.

        묶음(224)에 든 세는 분류는 묶음 토막의 괄호 안에 든다 — 그것까지
        펴서 **하나도 안 빠졌는지** 본다.
        """
        counts = {k: 3 for k in data.CLASSES}
        line = " ".join(data._count_parts(counts))
        for k in data.CLASSES:
            self.assertRegex(line, rf"(^|[ (·]){k} 3", f"{k} 가 개수 줄에 없다")

    def test_새로_넣은_속도_센다(self):
        """`Rhizosolenia` — 0037 로 들어온 분류다. 원통상 묶음 안에 든다."""
        self.assertIn("rhizosolenia", data.CLASSES)
        parts = data._count_parts({"rhizosolenia": 2, "rod": 1})
        self.assertIn("cylinder 2 (rhizosolenia 2)", parts)

    def test_안_센_분류는_안_적는다(self):
        """0 이거나 없는 것은 줄에 안 낀다 — 빈 이름이 늘어서면 못 읽는다."""
        parts = data._count_parts({"rod": 0, "round": 4})
        self.assertEqual(parts, ["round 4"])


class RhizosoleniaRowTest(DiaRUGATestCase):
    """마이그레이션 `0037` 이 넣은 행이 **여덟 칸을 다 채웠는가.**

    하나라도 비면 그 분류만 다르게 구른다 — `check_db` 의 "4. 분류" 가 운영에서
    보는 것을 여기서는 마이그레이션이 낸 행에 대고 본다. **픽스처가 아니라
    마이그레이션이 만든 행이다**(시험 DB 는 마이그레이션으로 선다).
    """

    def test_여덟_칸이_다_차_있다(self):
        row = ClassDef.objects.get(key="rhizosolenia")
        self.assertEqual(row.label, "Rhizosolenia")
        self.assertTrue(row.short, "약칭이 비면 목록 표의 열이 넓어진다")
        self.assertTrue(row.badge, "배지가 비면 배지 CSS 를 못 찾는다")
        self.assertTrue(row.color, "색이 비면 마스크가 투명해진다")
        self.assertTrue(row.hotkey, "단축키가 비면 그 분류만 메뉴로만 지정된다")
        self.assertTrue(row.counted)
        self.assertTrue(row.is_taxon, "속으로 알아본 것이라 메뉴에서 줄이 갈린다")
        self.assertTrue(row.active)
    def test_픽스처_표와_같은_값이다(self):
        """**옮겨 적은 표와 마이그레이션이 어긋나면 안 된다.**

        `factories.CLASSES` 는 운영 표를 옮겨 적은 것이고(`test_classdef_css`
        가 그것을 본다), 운영에 이 행을 넣는 것은 마이그레이션이다. 둘이
        갈라지면 **시험은 한쪽만 보고 통과한다** — CSS 시험이 픽스처 색을
        보는 동안 운영에는 다른 색이 앉는다.
        """
        row = ClassDef.objects.get(key="rhizosolenia")
        mirror = next(c for c in fx.CLASSES if c[0] == "rhizosolenia")
        key, label, short, badge, color, hot, counted, taxon = mirror
        self.assertEqual(
            (row.label, row.short, row.badge, row.color, row.hotkey,
             row.counted, row.is_taxon),
            (label, short, badge, color, hot, counted, taxon))


class HotkeyTest(DiaRUGATestCase):
    """단축키가 **운영 표 모양에서** 겹치지 않는가.

    마이그레이션만 도는 DB 에는 `round`·`rod`·`eucampia` 가 없다 — 그것들은
    초기 반입으로 들어왔지 마이그레이션이 넣은 것이 아니다. 그래서 겹침은
    **운영을 옮겨 적은 픽스처 표**에 대고 봐야 성립한다.
    """

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()

    def test_속끼리는_키를_안_나눈다(self):
        """본체·파편은 한 키를 나눠 갖지만(순환) **속끼리는 안 그런다.**

        `Eucampia` 와 같은 키를 주면 한 번 더 눌러야 닿는데, 그 순환은 원래
        *온전한 것과 깨진 것*을 가르려고 둔 것이다(039·0016).

        **같은 묶음 안의 속은 예외다** (224 · 사용자 2026-10-21) — 원통상의
        Rhizosolenia·Dactyliosolen 은 `t` 를 나눠 갖는다. 순환이 가르는 것이
        "같은 형태 안의 갈래" 로 넓어졌다.
        """
        taxa = ClassDef.objects.filter(active=True, is_taxon=True)
        seen = {}
        for t in taxa:
            if not t.hotkey:
                continue
            owner = t.group_id or t.key
            seen.setdefault(t.hotkey, set()).add(owner)
        bad = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertEqual(bad, {}, f"묶음이 다른 속끼리 겹친다: {bad}")

    def test_예약된_키를_안_쓴다(self):
        """`d` 는 그리기다 (`_detection.html`). 스페이스·화살표도 이미 쓰인다.

        **여기서 봐야 성립한다** — 마이그레이션만 도는 DB 에서 보면 표에 둘밖에
        없어서, 다른 분류가 예약키를 집어도 안 걸린다.
        """
        used = {c.hotkey for c in ClassDef.objects.filter(active=True)}
        self.assertNotIn("d", used)
        self.assertNotIn(" ", used)

    def test_본체와_파편만_키를_나눈다(self):
        """한 키에 둘 이상이 걸렸다면 **같은 형태의 본체·파편**이어야 한다."""
        rings = {}
        for c in ClassDef.objects.filter(active=True).exclude(hotkey=""):
            rings.setdefault(c.hotkey, []).append(c.key)
        for hot, keys in rings.items():
            if len(keys) < 2:
                continue
            # 같은 묶음(224)이면 한 형태다 — 원통상의 속 둘과 그 파편
            groups = {c.group_id for c in ClassDef.objects.filter(key__in=keys)}
            if len(groups) == 1 and None not in groups:
                continue
            stems = {k.removesuffix("_frag") for k in keys}
            self.assertEqual(len(stems), 1,
                             f"`{hot}` 에 서로 다른 형태가 걸렸다: {keys}")


class ClassMenuTest(DiaRUGATestCase):
    """새 분류가 **화면에 실제로 놓이는가.**"""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=1, n_candidates=3)

    def test_카탈로그_유형_셀렉트에_뜬다(self):
        html = self.client.get(
            reverse("catalog", args=["rs23"])).content.decode()
        self.assertIn("Rhizosolenia", html)

    def test_검토_화면에_단축키가_실린다(self):
        """`HOTKEYS` 를 화면이 표에서 만든다 — 목록을 템플릿에 적지 않는다."""
        html = self.client.get(
            reverse("group", args=["rs23", self.w.vp.idx])).content.decode()
        self.assertIn("rhizosolenia", html)
