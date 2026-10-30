"""시야 목록 머리의 통계 상자 · 거르기 줄 · 표지 (2026-10-30 · 사용자).

지키는 것.

1. **표지의 개수는 둘이다** — 개체(세는 분류만 · 파편·미분류를 뺀다)와 전체(검토
   후 남은 것). 하나만 있으면 목록 표의 "검출" 칸과 표지가 어긋나 보인다
2. **표지에 프레임 이름·"합성됨" 을 안 단다** — 찾기 칸이 이름을 대신 찾는다
3. **칩에 붙는 수는 서버가 센다** — 표지의 `data-*` 와 같은 기준이어야 거른 뒤의
   수와 칩의 수가 맞는다

걸러지는 것(JS)은 `browser/test_dataset_filter.py` 가 본다.
"""
import re

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data


class DatasetPageTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 후보 셋 = round · round_frag · rod — 세는 것은 둘(파편을 뺀다)
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=3)
        fx.review_done(cls.w.viewpoints[0])

    def html(self):
        return Client().get(reverse("dataset", args=["rs23"])).content.decode()

    def tiles(self, html):
        return re.findall(r'<a class="tile".*?</a>', html, re.S)

    def test_표지가_개체와_전체를_함께_센다(self):
        g = data.dataset_detail("rs23")["groups"][0]
        self.assertEqual((g["n_counted"], g["n_detected"]), (2, 3))
        self.assertIn("개체 2 · 전체 3", self.tiles(self.html())[0])

    def test_표지에_프레임_이름과_합성됨을_안_단다(self):
        vp = self.w.viewpoints[0]
        name = vp.sharpest_frame.name
        tile = self.tiles(self.html())[0]
        body = re.sub(r'<a class="tile"[^>]*>', "", tile)   # data-q 는 찾기용이다
        body = re.sub(r"<img[^>]*>", "", body)   # 합성본 파일 이름이 주소에 든다
        self.assertNotIn(name, body)
        self.assertNotIn("합성됨", body)
        self.assertIn(name, re.search(r'data-q="([^"]*)"', tile).group(1),
                      "찾기 칸이 프레임 이름으로 못 찾는다")

    def test_칩의_수가_표지와_맞는다(self):
        f = data.dataset_detail("rs23")["facets"]
        self.assertEqual(f["all"], 2)
        self.assertEqual(f["rev"], {"yes": 1, "no": 1})
        self.assertEqual(f["det"]["yes"], 2)
        tiles = self.tiles(self.html())
        self.assertEqual(sum('data-reviewed="1"' in t for t in tiles), f["rev"]["yes"])
        self.assertEqual(sum('data-det="yes"' in t for t in tiles), f["det"]["yes"])

    def test_묶음이_하나면_묶음_칩을_안_낸다(self):
        self.assertNotIn('data-f="batch"', self.html())

    def test_옛_체크박스가_없다(self):
        html = self.html()
        self.assertNotIn('id="hidedone"', html)
        self.assertIn('id="vpfilter"', html)

    def test_제목_줄의_길이_버튼이다(self):
        m = re.search(r'<nav class="pagebtns"[^>]*>(.*?)</nav>', self.html(), re.S)
        self.assertIsNotNone(m)
        self.assertEqual(len(re.findall(r'<a class="pbtn', m.group(1))), 5)

    def test_통계_상자에_분류_막대가_있다(self):
        html = self.html()
        self.assertIn('class="dsstats"', html)
        self.assertEqual(len(re.findall(r'<div class="cbar"', html)),
                         len(data.dataset_detail("rs23")["class_bars"]))
