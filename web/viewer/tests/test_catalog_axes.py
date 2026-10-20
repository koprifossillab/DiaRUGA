"""카탈로그 카드의 장축·단축 (222).

장축·단축은 동정키다. 카드는 개체 하나이고 개체는 판 여럿에 걸쳐 있어서,
**어느 판의 길이를 적느냐**가 이 기능의 전부다 — 개체가 가장 크게 잡힌 판에서
잰다. 대표(그림)의 줄을 그대로 쓰면 합성본에서 좁게 잡힌 윤곽의 길이가 적힌다.
"""
from django.test import Client
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data
from ..models import Detection, Image, ObjectReview, RunBatch


def rect(x, y, w, h):
    return [x, y, x + w, y, x + w, y + h, x, y + h]


class CatalogAxesTest(DiaRUGATestCase):

    def setUp(self):
        super().setUp()
        fx.make_classes()
        self.w = fx.make_world(slug="rs23", n_frames=3, n_candidates=2)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        self.frame_img = fx.add_frame_detections(self.w.vp)[0][1]
        self.stack_img = Image.objects.get(viewpoint=self.w.vp, kind="stack")
        self.key = self.w.keys()[0]
        self.a = fx.add_review(self.w.vp, self.key, image=self.stack_img)
        self.b = fx.add_review(self.w.vp, self.key, image=self.frame_img)
        Detection.objects.filter(viewpoint=self.w.vp).update(um_per_pixel=0.5)

    def set_poly(self, row, poly):
        ObjectReview.objects.filter(pk=row.pk).update(
            geom={"bbox": [poly[0], poly[1], poly[2] - poly[0], poly[5] - poly[1]],
                  "polygon": poly})

    def card(self):
        hit = [r for r in data.catalog_rows("rs23") if r["key"] == self.key]
        self.assertEqual(len(hit), 1)
        return hit[0]

    def test_가장_크게_잡힌_판에서_잰다(self):
        """대표는 합성본(작게 잡힘), 프레임이 더 크다 → 프레임의 길이."""
        self.set_poly(self.a, rect(10, 10, 40, 20))     # 합성본 — 작다
        self.set_poly(self.b, rect(10, 10, 80, 40))     # 프레임 — 크다
        fx.link_reviews([self.a, self.b], rep=0)
        ax = self.card()["axes"]
        self.assertIsNotNone(ax, "장축·단축이 안 나왔다")
        # 직사각형의 모멘트 타원 지름 = 변 × 2/√3. 0.5 µm/px
        self.assertAlmostEqual(ax["major"], 80 * 2 / 3 ** 0.5 * 0.5, places=1)
        self.assertAlmostEqual(ax["minor"], 40 * 2 / 3 ** 0.5 * 0.5, places=1)
        self.assertFalse(ax["here"], "그림과 다른 판에서 쟀는데 그 말을 안 한다")

    def test_대표가_가장_크면_기준을_안_적는다(self):
        self.set_poly(self.a, rect(10, 10, 80, 40))
        self.set_poly(self.b, rect(10, 10, 40, 20))
        fx.link_reviews([self.a, self.b], rep=0)
        ax = self.card()["axes"]
        self.assertTrue(ax["here"])

    def test_배율을_모르면_비운다(self):
        """µm 을 지어내지 않는다."""
        Detection.objects.filter(viewpoint=self.w.vp).update(um_per_pixel=None)
        self.set_poly(self.a, rect(10, 10, 80, 40))
        fx.link_reviews([self.a, self.b], rep=0)
        self.assertIsNone(self.card()["axes"])

    def test_카드에_등급과_코멘트_사이에_놓인다(self):
        self.set_poly(self.a, rect(10, 10, 80, 40))
        fx.link_reviews([self.a, self.b], rep=0)
        html = Client().get(reverse("catalog", args=["rs23"])).content.decode()
        i_gp = html.index('class="row gp"')
        i_ax = html.index('class="row axes"')
        i_note = html.index('<textarea class="note"')
        self.assertLess(i_gp, i_ax)
        self.assertLess(i_ax, i_note)
        self.assertIn("장축 <b>46.2</b>", html)
