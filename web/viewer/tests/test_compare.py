"""산출 비교 화면 (202 · 204).

**여기서 잡는 것은 목록과 다른 수를 내는 것이다.** 비교 표의 분류 칸은 목록
표의 분류 열과 같은 SQL 을 지나므로 같아야 하는데, 그 사실을 사람이
기억하는 대신 시험이 대조한다 — 종명 축을 SQL 에 더하면서 `GROUP BY` 가
바뀌었고, 거기서 분류 수가 갈라지면 예외 없이 그냥 틀린다.

204 에서 더한 것 — 열 머리의 시야당 개체·파편 비율, 코어 자료의 참조값
(잰 점 · 내삽 · 범위 밖 · 없음). 내삽은 **양옆 점의 선형**이고 범위 밖은
지어내지 않는다 — 그 갈래 넷이 다 다른 답이라 하나씩 되살려 본다.
"""
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data
from ..models import CorePoint, CoreSeries


def _row(ctx, key):
    return next(r for r in ctx["rows"] + ctx["extra_rows"] if r["key"] == key)


class CompareRowsTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 후보 넷 = round · round_frag · rod · rod_frag (CLASSES 차례).
        cls.a = fx.make_world(slug="a", depth_cm=71.0, n_candidates=4)
        cls.b = fx.make_world(slug="b", depth_cm=231.0, sample_code="231cm",
                              n_candidates=2)
        # a: 첫 개체(round)를 지우고, rod 에 종명을 적는다.
        keys = cls.a.keys()
        fx.add_review(cls.a.vp, keys[0], removed=True)
        fx.add_review(cls.a.vp, keys[2], species="Fragilariopsis kerguelensis")

    def test_분류_수가_목록과_같다(self):
        ctx = data.compare_slides(["a", "b"])
        lst = {r["slug"]: r for r in data.datasets()}
        for i, c in enumerate(ctx["cols"]):
            want = {x["key"]: x["n"] for x in lst[c["slug"]]["counted"]}
            for r in ctx["rows"]:
                self.assertEqual(r["cells"][i]["n"], want[r["key"]],
                                 f"{c['slug']} {r['key']}")
            self.assertEqual(c["n_counted"], lst[c["slug"]]["n_counted"])
            self.assertEqual(c["n_detected"], lst[c["slug"]]["n_detected"])

    def test_지운_것은_빠지고_비율은_세는_분류의_합이_분모다(self):
        ctx = data.compare_slides(["a", "b"])
        a = ctx["cols"][0]
        self.assertEqual(a["slug"], "a")
        self.assertEqual(a["n_counted"], 1)          # round 지움 → rod 하나
        self.assertEqual(a["n_detected"], 3)         # 조각 둘은 개체 전부에는 든다
        rod = _row(ctx, "rod")
        self.assertEqual(rod["cells"][0], {"n": 1, "pct": 100.0})
        self.assertEqual(_row(ctx, "round")["cells"][0], {"n": 0, "pct": 0.0})
        # 파편은 비율이 없다 — 분모에 안 드는 것을 비율로 적으면 100 이 안 맞는다.
        self.assertFalse(_row(ctx, "rod_frag")["counted"])
        self.assertIsNone(_row(ctx, "rod_frag")["cells"][0]["pct"])

    def test_종명이_분류_아래_한_줄로_선다(self):
        ctx = data.compare_slides(["a", "b"])
        rod = _row(ctx, "rod")
        names = [s["name"] for s in rod["species"]]
        self.assertEqual(names, ["Fragilariopsis kerguelensis"])
        self.assertEqual(rod["species"][0]["cells"][0]["n"], 1)
        self.assertEqual(rod["species"][0]["cells"][1]["n"], 0)
        # b 의 rod 는 종명이 없지만 「종명 없음」 줄은 안 선다 (204).
        self.assertEqual(ctx["n_species"], 1)
        self.assertEqual(_row(ctx, "round")["species"], [])

    def test_종명_없는_나머지_줄은_안_낸다(self):
        """204 — 「종명 없음」 줄을 걷었다. 분류 수에서 종명 줄을 빼면 그 수다."""
        # 후보 여덟 = 분류 일곱을 한 바퀴 돌고 round 가 한 번 더 → round 둘.
        c = fx.make_world(slug="c", depth_cm=300.0, sample_code="300cm",
                          n_candidates=8)
        fx.add_review(c.vp, c.keys()[0], species="Eucampia antarctica")
        ctx = data.compare_slides(["c"])
        rnd = _row(ctx, "round")
        self.assertEqual(rnd["cells"][0]["n"], 2)
        self.assertEqual([(s["name"], s["cells"][0]["n"]) for s in rnd["species"]],
                         [("Eucampia antarctica", 1)])
        self.assertEqual(_row(ctx, "rod")["species"], [])
        # 분류의 색이 줄에 실린다 — 막대가 그 색으로 그려진다.
        self.assertEqual(rnd["color"], "60,220,120")

    def test_시야당_개체와_파편_비율(self):
        """열 머리의 수 둘 (204). 시야당은 세는 분류 ÷ 검출이 돈 시야, 파편
        비율은 파편 ÷ 남는 개체 전부 — 분모가 서로 다르다."""
        ctx = data.compare_slides(["a", "b"])
        a, b = ctx["cols"]
        # a: round 지움 → rod 하나 남고 조각 둘. 시야 하나.
        self.assertEqual((a["n_counted"], a["n_frag"], a["n_detected"]), (1, 2, 3))
        self.assertEqual(a["per_view"], 1.0)
        self.assertEqual(a["frag_pct"], 66.7)
        # b: round · round_frag 하나씩.
        self.assertEqual(b["per_view"], 1.0)
        self.assertEqual(b["frag_pct"], 50.0)
        self.assertNotIn("reviewed_groups", a)

    def test_열은_고른_차례가_아니라_깊이_차례다(self):
        ctx = data.compare_slides(["b", "a"])
        self.assertEqual([c["slug"] for c in ctx["cols"]], ["a", "b"])
        self.assertEqual([c["depth_cm"] for c in ctx["cols"]], [71.0, 231.0])

    def test_모르는_slug_는_거르고_알린다(self):
        ctx = data.compare_slides(["a", "zzz", "a"])
        self.assertEqual([c["slug"] for c in ctx["cols"]], ["a"])
        self.assertEqual(ctx["unknown"], ["zzz"])

    def test_아무것도_없으면_빈_표(self):
        ctx = data.compare_slides([])
        self.assertEqual(ctx["cols"], [])
        self.assertEqual(ctx["rows"], [])


class ComparePageTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.a = fx.make_world(slug="a", depth_cm=71.0, n_candidates=3)
        cls.b = fx.make_world(slug="b", depth_cm=231.0, sample_code="231cm",
                              n_candidates=2)
        fx.add_review(cls.a.vp, cls.a.keys()[0],
                      species="Fragilariopsis kerguelensis")

    def test_화면이_열리고_고른_것이_표에_선다(self):
        r = self.client.get(reverse("compare"), {"s": ["a", "b"]})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Fragilariopsis kerguelensis", html)
        self.assertIn("231 cm", html)
        # 고른 것은 체크된 채로 다시 뜬다 — 하나 더하고 다시 비교할 수 있게.
        self.assertIn('value="a" checked', html)
        self.assertIn('value="b" checked', html)
        self.assertEqual(html.count("value=\"a\""), 1)

    def test_고른_것이_없어도_열린다(self):
        r = self.client.get(reverse("compare"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("둘 이상 고르세요", html)
        self.assertNotIn("<table", html)

    def test_모르는_slug_는_404_가_아니다(self):
        r = self.client.get(reverse("compare"), {"s": ["a", "nope"]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("nope", r.content.decode())


class CoreValueAtTest(DiaRUGATestCase):
    """`core_value_at` — 갈래 넷."""

    PTS = [(0, 10.0), (200, 20.0), (400, 50.0)]

    def test_잰_점이_있으면_그_값(self):
        self.assertEqual(data.core_value_at(self.PTS, 200),
                         {"state": "exact", "value": 20.0, "at_cm": 20.0})

    def test_사이는_선형_내삽(self):
        r = data.core_value_at(self.PTS, 300)
        self.assertEqual(r["state"], "interp")
        self.assertAlmostEqual(r["value"], 35.0)
        self.assertEqual((r["lo_cm"], r["hi_cm"]), (20.0, 40.0))
        # 한쪽으로 치우친 자리는 그쪽 값에 가깝다 — 평균이 아니다.
        self.assertAlmostEqual(data.core_value_at(self.PTS, 250)["value"], 27.5)

    def test_범위_밖은_지어내지_않는다(self):
        for mm in (500, 401):
            r = data.core_value_at(self.PTS, mm)
            self.assertEqual(r["state"], "outside")
            self.assertIsNone(r["value"])
            self.assertEqual((r["lo_cm"], r["hi_cm"]), (0.0, 40.0))
        # 0 은 첫 점이라 exact 다 — 범위 밖이 아니다.
        self.assertEqual(data.core_value_at(self.PTS, 0)["state"], "exact")

    def test_점이_없으면_none(self):
        self.assertEqual(data.core_value_at([], 100)["state"], "none")


class CompareCoreRefTest(DiaRUGATestCase):
    """비교 표에 코어 자료의 참조값이 열마다 얹힌다 (204)."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 같은 코어(RS23-GC03)의 71 cm · 231 cm 와 다른 코어(WAP13-GC47)의 하나.
        cls.a = fx.make_world(slug="a", depth_cm=71.0, n_candidates=2)
        cls.b = fx.make_world(slug="b", depth_cm=231.0, sample_code="231cm",
                              n_candidates=2)
        cls.c = fx.make_world(slug="c", site_code="WAP13", loc_code="GC47",
                              sample_code="450cm", depth_cm=450.0, n_candidates=2)
        cls.o = fx.make_world(slug="o", area="kr", kind="outcrop",
                              site_code="BP", loc_code="BP09",
                              sample_code="0901", n_candidates=2)
        cs = CoreSeries.objects.create(locality=cls.a.locality, key="opal",
                                       label="Opal", unit="%")
        CorePoint.objects.bulk_create(
            [CorePoint(series=cs, depth_mm=mm, value=v)
             for mm, v in ((600, 40.0), (710, 44.0), (800, 50.0), (2000, 30.0))])

    def test_잰_값_내삽_범위_밖_없음이_열마다_갈린다(self):
        ctx = data.compare_slides(["a", "b", "c", "o"])
        self.assertEqual([r["key"] for r in ctx["ref_rows"]], ["opal"])
        row = ctx["ref_rows"][0]
        self.assertEqual((row["label"], row["unit"]), ("Opal", "%"))
        # 열은 목록의 차례다 — 지역 코드순이라 BP 의 노두가 맨 앞이다.
        self.assertEqual([c["slug"] for c in ctx["cols"]], ["o", "a", "b", "c"])
        o, a, b, c = row["cells"]
        self.assertEqual((a["state"], a["value"]), ("exact", 44.0))
        self.assertEqual(b["state"], "outside")
        self.assertEqual(c["state"], "none")            # 코어 자료가 없는 지점
        self.assertEqual(o["state"], "none")            # 노두 — 깊이 축이 없다
        # 막대는 열 중 가장 큰 값이 100.
        self.assertEqual(a["w"], 100.0)
        self.assertEqual(b["w"], 0)

    def test_내삽한_값(self):
        # 71 cm 의 점을 걷으면 60 과 80 사이 — 44 가 아니라 45.5 가 된다.
        CorePoint.objects.filter(depth_mm=710).delete()
        ctx = data.compare_slides(["a"])
        x = ctx["ref_rows"][0]["cells"][0]
        self.assertEqual(x["state"], "interp")
        self.assertAlmostEqual(x["value"], 45.5)
        self.assertEqual((x["lo_cm"], x["hi_cm"]), (60.0, 80.0))

    def test_화면에_데이터_없음과_내삽_표시가_뜬다(self):
        CorePoint.objects.filter(depth_mm=710).delete()
        r = self.client.get(reverse("compare"), {"s": ["a", "b", "c"]})
        html = r.content.decode()
        self.assertIn("≈</span>45.5", html)
        self.assertIn("범위 밖", html)
        self.assertIn("데이터 없음", html)
        # 「비교 대상」 거르기의 열쇠가 표의 줄과 같은 꼴로 있다.
        self.assertIn('data-cls="round"', html)
        self.assertIn('class="cmp-filter"', html)
