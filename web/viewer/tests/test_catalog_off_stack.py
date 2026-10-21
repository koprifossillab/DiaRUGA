"""카탈로그의 「합성본에 없음」 거르개 (226 · 사용자 2026-10-21).

YOLO 4차는 합성본으로 배운다(P29). 프레임에만 있는 개체는 합성본 라벨에서
빠지고, 그 자리가 **배경으로 학습된다** — "흐리거나 달라 보여도 그 자리에 개체는
있다"(P30 2.1)와 반대되는 정답이다. 검토자가 합성본에서 훑어 채우도록 그 카드를
모은다.

**밟기 쉬운 자리가 둘이다.**

- **합성본이 없는 시야**(한 장짜리)의 개체를 걸면 고칠 수 없는 것을 고치라고 한다
- **파편을 감추면** 수의 절반이 사라진다(10-21 · 280 중 143) — 칩의 수와 카드 수가
  어긋나면 사람은 자료가 없다고 읽는다

후보는 픽스처 표의 차례로 돈다 — 0 round · 1 round_frag.
"""
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from ..models import RunBatch


class OffStackFilterTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_candidates=2)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        frames = fx.add_frame_detections(cls.w.vp, n_candidates=2)
        cls.frame_img = frames[0][1]
        k = cls.w.keys()
        cls.on_stack, cls.frag_off = k[0], k[1]
        fx.add_review(cls.w.vp, k[0])                         # 합성본
        fx.add_review(cls.w.vp, k[1], image=cls.frame_img)    # 프레임에만 · 파편
        # 합성본이 없는 시야 — 물을 것이 없다
        cls.s = fx.make_world(slug="single", site_code="RS99", n_candidates=1,
                              with_stack=False)
        fx.add_review(cls.s.vp, cls.s.keys()[0])

    def rows(self, slug, q=""):
        url = reverse("catalog", args=[slug]) + q
        return self.client.get(url).context["rows"]

    def test_프레임에만_있는_개체만_걸린다(self):
        got = {(r["key"], r["image_id"]) for r in self.rows("rs23", "?cls=off_stack")}
        self.assertEqual(got, {(self.frag_off, self.frame_img.pk)})

    def test_파편도_감추지_않는다(self):
        rows = self.rows("rs23", "?cls=off_stack")
        self.assertEqual([r["cls"] for r in rows], ["round_frag"])

    def test_칩의_수는_파편을_센다(self):
        html = self.client.get(
            reverse("catalog", args=["rs23"])).content.decode()
        self.assertIn('합성본에 없음 <span class="dim">1</span>', html)

    def test_합성본이_없는_시야는_안_걸린다(self):
        self.assertEqual(self.rows("single", "?cls=off_stack"), [])
        self.assertTrue(self.rows("single"), "카드 자체는 있어야 한다")

    def test_파편_보기_칸을_안_낸다(self):
        """골랐을 때 파편을 다 내므로 켜고 끌 수 있는 것처럼 보이면 안 된다."""
        html = self.client.get(reverse("catalog", args=["rs23"])
                               + "?cls=off_stack").content.decode()
        self.assertNotIn('class="fragtoggle"', html)
