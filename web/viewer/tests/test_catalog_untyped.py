"""카탈로그의 「유형 미지정」 거르개 넷 (225 · 사용자 2026-10-21).

유형 칸이 비면 화면이 엔진의 추측을 대신 그려 **"비었다" 가 안 보인다.** YOLO
4차 자료를 만들기 전에 사람이 훑도록 넷으로 가른다 — 엔진 봉상 · 엔진 원형 ·
엔진값 없음 · 손그림. **사람이 고른 유형은 엔진값과 같아도 넷 어디에도 안
든다** — 그것까지 들면 이미 한 일을 다시 하게 된다.

후보는 픽스처 표의 차례로 돈다 — 0 round · 1 round_frag · 2 rod · 3 rod_frag ·
4 eucampia.
"""
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data
from ..models import Candidate, RunBatch

DRAWN = "m1a2b3c4d"


class UntypedFilterTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_candidates=5)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        cls.k = cls.w.keys()
        # 4번은 엔진이 유형을 못 낸 후보다
        Candidate.objects.filter(mask_key=cls.k[4]).update(cls="")
        for vp in cls.w.viewpoints:
            fx.review_done(vp)
        # 3번은 사람이 봉상으로 골랐다 — 엔진값과 무관하게 넷에서 빠져야 한다
        fx.add_review(cls.w.vp, cls.k[3], label="rod")
        det = cls.w.detection()
        fx.new_review(
            viewpoint=cls.w.vp, image=det.image, batch=None,
            mask_key=DRAWN, source="manual", bind_method="manual",
            geom={"bbox": [400, 300, 60, 60],
                  "polygon": [400, 300, 460, 300, 460, 360, 400, 360]})
        data.invalidate_classes()

    def keys(self, f):
        url = reverse("catalog", args=["rs23"]) + f"?cls={f}"
        return {r["key"] for r in self.client.get(url).context["rows"]}

    def test_엔진_봉상(self):
        self.assertEqual(self.keys("untyped_rod"), {self.k[2]})

    def test_엔진_원형(self):
        self.assertEqual(self.keys("untyped_round"), {self.k[0]})

    def test_엔진값_없음(self):
        self.assertEqual(self.keys("untyped_none"), {self.k[4]})

    def test_손그림(self):
        self.assertEqual(self.keys("untyped_drawn"), {DRAWN})

    def test_사람이_고른_유형은_안_든다(self):
        for f in ("untyped_rod", "untyped_round", "untyped_none",
                  "untyped_drawn"):
            with self.subTest(f=f):
                self.assertNotIn(self.k[3], self.keys(f))

    def test_칩에_수가_적힌다(self):
        html = self.client.get(
            reverse("catalog", args=["rs23"])).content.decode()
        for label in ("엔진 봉상", "엔진 원형", "엔진값 없음", "손그림"):
            with self.subTest(label=label):
                self.assertIn(f"유형 미지정 · {label} <span class=\"dim\">1</span>",
                              html)
