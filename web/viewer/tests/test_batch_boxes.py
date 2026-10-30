"""검토 화면 탭 줄의 묶음 상자 (051 → 2026-10-30).

051 은 묶음을 **엔진 단위로 접었다**(라디오 "YOLO · SAM"). 그래서 `yolo-3차`·
`yolo-4차` 가 한 칸에 들어가 차수가 안 보였고, 3차 정답 시야에서 4차를 열려면
`?batch=` 를 손으로 쳐야 했다. 이 시야의 **주 묶음**이 무엇인지도 어디에도 안
적혔다(사용자).

여기서 지키는 것.

1. **묶음마다 상자 하나** — 같은 엔진의 차수가 접히지 않는다
2. **주 묶음이 맨 앞이고 맨 주소로 간다** — "주 묶음" 이 적힌다
3. **주 묶음에 이 시야의 검출이 없어도 상자가 있다**(개체 0)
4. **얼린 묶음은 그렇게 적힌다**
5. 나머지는 `?batch=` 읽기 전용으로 가고, 거기서는 그 상자가 지금 보는 것이다
"""
import re

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data
from ..models import RunBatch, Viewpoint


class BatchBoxesTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=3)
        cls.vp, cls.bare_vp = cls.w.viewpoints
        # 같은 엔진(YOLO)의 차수 둘 — 접히면 안 된다
        cls.y3 = fx.add_other_engine(cls.vp, label="yolo-3차")
        cls.y4 = fx.add_other_engine(cls.vp, label="yolo-4차", n_candidates=1)
        cls.url = reverse("group", args=["rs23", cls.vp.idx])

    def setUp(self):
        self.c = Client()

    def boxes(self, html):
        """상자마다 (클래스, href, 글자) — 렌더한 그대로 읽는다."""
        found = re.findall(
            r'<a class="bbox([^"]*)"\s+href="([^"]*)"[^>]*>(.*?)</a>', html, re.S)
        return [(cls.split(), href.replace("&amp;", "&"),
                 re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip())
                for cls, href, body in found]

    def test_묶음마다_상자_하나이고_차수가_안_접힌다(self):
        r = self.c.get(self.url)
        self.assertEqual(r.status_code, 200)
        bx = self.boxes(r.content.decode())
        names = [t for _, _, t in bx]
        self.assertEqual(len(bx), 3, names)
        self.assertTrue(any("yolo-3차" in t for t in names), names)
        self.assertTrue(any("yolo-4차" in t for t in names), names)

    def test_주_묶음이_맨_앞이고_맨_주소로_간다(self):
        bx = self.boxes(self.c.get(self.url).content.decode())
        cls, href, text = bx[0]
        self.assertIn("sam2-시험", text)
        self.assertIn("주 묶음", text)
        self.assertIn("prim", cls)
        self.assertIn("now", cls, "맨 주소에서 주 묶음이 지금 보는 것이 아니다")
        self.assertEqual(href, self.url)
        self.assertNotIn("읽기 전용", text)
        # 나머지는 주 묶음 표시가 없고 읽기 전용으로 간다
        for cls, href, text in bx[1:]:
            self.assertNotIn("주 묶음", text)
            self.assertIn("읽기 전용", text)
            self.assertIn("?batch=", href)

    def test_개수는_그_묶음이_낸_것이다(self):
        bx = self.boxes(self.c.get(self.url).content.decode())
        texts = [t for _, _, t in bx]
        self.assertTrue(any(re.search(r"yolo-3차 2\b", t) for t in texts), texts)
        self.assertTrue(any(re.search(r"yolo-4차 1\b", t) for t in texts), texts)

    def test_읽기_전용_갈래에서는_그_상자가_지금_보는_것이다(self):
        r = self.c.get(f"{self.url}?batch={self.y4.pk}")
        self.assertEqual(r.status_code, 200)
        bx = self.boxes(r.content.decode())
        now = [t for c, _, t in bx if "now" in c]
        self.assertEqual(len(now), 1)
        self.assertIn("yolo-4차", now[0])
        # 주 묶음 상자는 그대로 맨 앞이고 맨 주소로 돌아간다
        self.assertIn("주 묶음", bx[0][2])
        self.assertEqual(bx[0][1], self.url)

    def test_주_묶음에_검출이_없어도_상자가_있다(self):
        """4차를 기다리는 칸 — 맨 주소가 빈 화면을 여는데 무엇이 비었는지 적혀야 한다."""
        y5 = RunBatch.objects.create(kind="detect", label="yolo-5차")
        Viewpoint.objects.filter(pk=self.vp.pk).update(batch=y5)
        bx = self.boxes(self.c.get(self.url).content.decode())
        cls, href, text = bx[0]
        self.assertIn("yolo-5차", text)
        self.assertIn("주 묶음", text)
        self.assertIn(" 0", text)
        self.assertEqual(href, self.url)
        # 옛 주 묶음(sam2-시험)은 이제 읽기 전용 상자다
        sam = [t for _, h, t in bx if "sam2-시험" in t]
        self.assertEqual(len(sam), 1)
        self.assertIn("읽기 전용", sam[0])

    def test_얼린_묶음은_얼림으로_적힌다(self):
        RunBatch.objects.filter(label="yolo-3차").update(frozen=True)
        bx = self.boxes(self.c.get(self.url).content.decode())
        y3 = next(t for _, _, t in bx if "yolo-3차" in t)
        self.assertIn("얼림", y3)
        self.assertNotIn("읽기 전용", y3)

    def test_다른_시야의_검출은_세지_않는다(self):
        """상자는 **이 시야**에 검출이 있는 묶음만이다."""
        bs = data.batches_for_viewpoint("rs23", self.bare_vp.idx)
        self.assertEqual([b["label"] for b in bs], ["sam2-시험"])
