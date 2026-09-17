"""산출 비교 화면 (202).

**여기서 잡는 것은 목록과 다른 수를 내는 것이다.** 비교 표의 분류 칸은 목록
표의 분류 열과 같은 SQL 을 지나므로 같아야 하는데, 그 사실을 사람이
기억하는 대신 시험이 대조한다 — 종명 축을 SQL 에 더하면서 `GROUP BY` 가
바뀌었고, 거기서 분류 수가 갈라지면 예외 없이 그냥 틀린다.
"""
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data


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
        # b 의 rod 는 종명이 없다 — "종명 없음" 줄은 남는 것이 있을 때만 선다.
        # a 는 rod 하나가 전부 종명이 있으니 없고, b 는 종명이 없으니 그쪽 열에 1.
        self.assertEqual(ctx["n_species"], 1)
        self.assertEqual(_row(ctx, "round")["species"], [])

    def test_종명_없는_나머지_줄(self):
        # 후보 여덟 = 분류 일곱을 한 바퀴 돌고 round 가 한 번 더 → round 둘.
        c = fx.make_world(slug="c", depth_cm=300.0, sample_code="300cm",
                          n_candidates=8)
        fx.add_review(c.vp, c.keys()[0], species="Eucampia antarctica")
        ctx = data.compare_slides(["c"])
        rnd = _row(ctx, "round")
        self.assertEqual(rnd["cells"][0]["n"], 2)
        # 종명 줄 하나와 "종명 없음" 나머지 줄 — 둘을 더하면 분류 수와 같다.
        self.assertEqual([(s["name"], s["cells"][0]["n"]) for s in rnd["species"]],
                         [("Eucampia antarctica", 1), ("", 1)])
        # 종명이 하나도 없는 분류에는 나머지 줄도 안 선다.
        self.assertEqual(_row(ctx, "rod")["species"], [])

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
