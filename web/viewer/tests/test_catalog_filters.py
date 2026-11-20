"""카탈로그의 **거르개 줄** (255).

한 줄에 칩 스물일곱이 나란히 있던 것을 유형·파편·동정·정제용으로 갈랐다.
여기서 보는 것은 그 가름이 **조용히 다른 것을 내는 자리**다 —

- 유형과 동정 상태가 **함께 걸리는가** (`cls` + `st`). 예전에는 한 칸을 나눠 써서
  하나를 누르면 다른 것이 풀렸다
- **옛 주소**(`?cls=unnamed`)가 그대로 도는가 — 적어 둔 링크가 "전체" 를 내면
  사람은 거르개가 걸린 줄 안다
- **칩의 수가 눌렀을 때 놓일 카드의 수인가.** 수와 카드가 다른 식에서 나오면
  "12" 를 눌렀는데 9장이 놓인다
- 이 슬라이드에 없는 유형의 칩을 안 놓는가, 골라 둔 것은 0 이어도 놓는가
"""
from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from ..models import RunBatch
from .. import data
from ..views import catalog_len


class CatalogFilterRowTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=4)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        for _vp in cls.w.viewpoints:
            fx.review_done(_vp)
        rows = data.catalog_rows("rs23")
        assert len(rows) >= 3, "카드가 모자라 시험이 헛돈다"
        # 첫 카드를 봉상으로 지정하고 코멘트를 단다 — 유형과 상태가 둘 다 걸리는 것
        cls.rod = rows[0]
        fx.new_review(viewpoint_id=cls.w.viewpoints[rows[0]["group_id"]].pk,
                      image_id=rows[0]["image_id"], batch_id=rows[0]["batch_id"],
                      mask_key=rows[0]["key"], bind_method="exact",
                      label="rod", note="가장자리가 넘쳤다")

    def setUp(self):
        self.url = reverse("catalog", args=["rs23"])

    def ctx(self, **q):
        r = Client().get(self.url, q)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.context, r.content.decode()

    def nos(self, ctx):
        return [r["catalog_no"] for r in ctx["rows"]]

    def test_유형과_동정_상태가_함께_걸린다(self):
        both, _ = self.ctx(cls="rod", st="noted")
        self.assertEqual(self.nos(both), [self.rod["catalog_no"]])
        # 한 축만 건 것보다 넓지 않다 — 둘 중 하나가 무시되면 여기서 잡힌다
        rods, _ = self.ctx(cls="rod")
        self.assertTrue(all(r["cls"] == "rod" for r in rods["rows"]))
        none, _ = self.ctx(cls="round", st="noted")
        self.assertEqual(self.nos(none), [],
                         "유형이 다른데 코멘트만 보고 냈다 — cls 가 무시됐다")

    def test_옛_주소가_그대로_돈다(self):
        """동정 상태 셋은 `cls` 에 있다가 `st` 로 옮겼다."""
        old, _ = self.ctx(cls="noted")
        new, _ = self.ctx(st="noted")
        self.assertEqual(self.nos(old), self.nos(new))
        self.assertEqual(self.nos(old), [self.rod["catalog_no"]])
        self.assertEqual((old["cls"], old["st"]), ("", "noted"))

    def test_칩의_수가_놓이는_카드의_수다(self):
        ctx, _ = self.ctx()
        chips = ctx["f_whole"] + ctx["f_frags"] + ctx["f_cleanup"]
        self.assertTrue(chips, "칩이 하나도 없다")
        for c in chips:
            with self.subTest(chip=c["key"]):
                got, _ = self.ctx(cls=c["key"])
                self.assertEqual(got["total"], c["n"])
        for c in ctx["f_status"]:
            with self.subTest(status=c["key"]):
                got, _ = self.ctx(st=c["key"])
                self.assertEqual(got["total"], c["n"])
        self.assertEqual(ctx["total"], ctx["f_all"]["n"])

    def test_수는_다른_축을_건_채로_센다(self):
        ctx, _ = self.ctx(st="noted")
        by = {c["key"]: c["n"] for c in ctx["f_whole"]}
        self.assertEqual(by, {"rod": 1},
                         "코멘트 있는 것은 봉상 하나뿐인데 다른 유형이 놓였다")

    def test_없는_유형은_칩을_안_놓는다(self):
        ctx, html = self.ctx()
        keys = {c["key"] for c in ctx["f_whole"] + ctx["f_frags"]}
        have = {r["cls"] for r in data.catalog_rows("rs23")}
        self.assertNotIn("corethron", have, "픽스처에 Corethron 이 있어 시험이 헛돈다")
        self.assertNotIn("corethron", keys)
        self.assertTrue(keys <= have | {"group:cylinder"}, keys - have)

    def test_골라_둔_것은_0_이어도_놓는다(self):
        """안 놓으면 풀 자리가 없다."""
        ctx, _ = self.ctx(cls="corethron")
        chip = [c for c in ctx["f_whole"] if c["key"] == "corethron"]
        self.assertEqual(len(chip), 1)
        self.assertTrue(chip[0]["on"])
        self.assertEqual(chip[0]["n"], 0)
        # 다시 누르면 풀린다
        self.assertNotIn("cls=", chip[0]["href"])

    def test_정제용은_접혀_있다가_고르면_펴진다(self):
        _, html = self.ctx()
        self.assertIn('<details class="fmore">', html)
        _, html = self.ctx(cls="untyped_rod")
        self.assertIn('<details class="fmore" open>', html)

    def test_쪽을_넘겨도_동정_상태가_따라간다(self):
        ctx, _ = self.ctx(st="unnamed", frag="1")
        for c in ctx["f_whole"] + ctx["f_frags"]:
            self.assertIn("st=unnamed", c["href"])
            self.assertIn("frag=1", c["href"])


class CatalogSizeSortTest(DiaRUGATestCase):
    """장축 길이로 정렬하고 범위로 거른다 (265).

    여기서 보는 것은 **카드에 적힌 길이와 놓인 차례·걸린 범위가 같은 값에서
    나오는가**, 그리고 차례·범위가 **쪽과 칩을 넘어 따라가는가**다.
    """

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=4)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        for _vp in cls.w.viewpoints:
            fx.review_done(_vp)
        rows = data.catalog_rows("rs23")
        cls.lens = [catalog_len(r) for r in rows]
        assert None not in cls.lens, "길이 없는 카드가 섞여 시험이 헛돈다"
        assert len(set(cls.lens)) >= 3, f"길이가 안 갈려 시험이 헛돈다: {cls.lens}"
        assert cls.lens != sorted(cls.lens) and \
            cls.lens != sorted(cls.lens, reverse=True), \
            "번호 차례가 이미 길이 차례라 정렬을 안 해도 통과한다"

    def setUp(self):
        self.url = reverse("catalog", args=["rs23"])

    def ctx(self, **q):
        # 픽스처의 절반이 파편이다 — 펴 놓고 본다(기본은 감춘다)
        q.setdefault("frag", "1")
        r = Client().get(self.url, q)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.context, r.content.decode()

    def got(self, ctx):
        return [catalog_len(r) for r in ctx["rows"]]

    def test_장축_긴_것부터_짧은_것부터(self):
        ctx, _ = self.ctx(sort="len")
        self.assertEqual(self.got(ctx), sorted(self.lens, reverse=True))
        ctx, _ = self.ctx(sort="len_asc")
        self.assertEqual(self.got(ctx), sorted(self.lens))

    def test_모르는_정렬은_번호_차례다(self):
        base, _ = self.ctx()
        odd, _ = self.ctx(sort="nope")
        self.assertEqual(self.got(odd), self.got(base))
        self.assertEqual(odd["sort"], "")

    def test_범위_안의_카드만_놓인다(self):
        s = sorted(set(self.lens))
        lo, hi = s[1], s[-2]
        ctx, _ = self.ctx(lmin=lo, lmax=hi)
        want = [v for v in self.lens if lo <= v <= hi]
        self.assertEqual(sorted(self.got(ctx)), sorted(want))
        self.assertLess(len(want), len(self.lens), "아무것도 안 걸러져 시험이 헛돈다")
        self.assertEqual(ctx["size"]["n_out"], len(self.lens) - len(want))
        # 한쪽만 걸 수 있다
        ctx, _ = self.ctx(lmin=hi)
        self.assertEqual(sorted(self.got(ctx)),
                         sorted(v for v in self.lens if v >= hi))

    def test_칩의_수가_범위를_건_채로_센다(self):
        s = sorted(set(self.lens))
        ctx, _ = self.ctx(lmax=s[0])
        self.assertEqual(ctx["f_all"]["n"], ctx["total"])
        self.assertEqual(ctx["total"], self.lens.count(s[0]))

    def test_눈금의_양_끝은_거르기_전의_것이다(self):
        s = sorted(set(self.lens))
        base, _ = self.ctx()
        ctx, _ = self.ctx(lmin=s[-1])
        self.assertEqual((ctx["size"]["lo"], ctx["size"]["hi"]),
                         (base["size"]["lo"], base["size"]["hi"]))
        self.assertLessEqual(base["size"]["lo"], s[0])
        self.assertGreaterEqual(base["size"]["hi"], s[-1])

    def test_차례와_범위가_칩과_검색을_따라간다(self):
        ctx, html = self.ctx(sort="len", lmin="1", frag="1")
        for c in ctx["f_whole"] + ctx["f_status"]:
            self.assertIn("sort=len", c["href"])
            self.assertIn("lmin=1", c["href"])
        self.assertIn('name="sort" value="len"', html)
        self.assertIn('name="lmin" value="1"', html)
        # 모두 풀기는 범위를 풀고 차례는 둔다
        self.assertTrue(ctx["f_any"])
        self.assertNotIn("lmin", ctx["f_clear"])
        self.assertIn("sort=len", ctx["f_clear"])

    def test_쪽을_넘겨도_차례와_범위가_남는다(self):
        from unittest import mock
        with mock.patch("viewer.views.CATALOG_PER_PAGE", 2):
            ctx, _ = self.ctx(sort="len_asc", lmin="1", frag="1")
            self.assertIn("sort=len_asc", ctx["next_url"])
            self.assertIn("lmin=1", ctx["next_url"])
            nxt = Client().get(self.url + ctx["next_url"]).context
            self.assertIn("frag=1", ctx["next_url"])
        self.assertEqual(self.got(ctx) + self.got(nxt),
                         sorted(self.lens)[:4])

    def test_엉뚱한_값은_안_건_것으로_읽는다(self):
        ctx, _ = self.ctx(lmin="abc", lmax="-3")
        self.assertFalse(ctx["size"]["on"])
        self.assertEqual(len(ctx["rows"]), len(self.lens))
        # 거꾸로 주면 바꿔 읽는다
        s = sorted(set(self.lens))
        ctx, _ = self.ctx(lmin=s[-1], lmax=s[0])
        self.assertEqual(len(ctx["rows"]), len(self.lens))
