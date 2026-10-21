"""넓힌 검토 화면의 세 칸 (229).

[왼쪽: 화면 조정 · 시야 바둑판 · 통계 · 안내] [사진 + 프레임 줄] [오른쪽: 개체
카탈로그 · 도감 · 선택 정보 · 시야에 하는 일]. 지키는 것:

1. **시야에 하는 일(오프라인 꺼내기 · 가르기)은 한 화면에 한 번만 그려진다.**
   오른쪽 칸에 놓이는 갈래와 예전처럼 사진 아래 놓이는 갈래가 겹치면 `<details>`
   의 id 가 둘이 되고, 화면 배선이 아무 쪽이나 집는다
2. **읽기 전용(`?batch=`)에서는 오른쪽 칸에 가르기가 안 실린다** — 조각으로
   뗐다고 027 의 조건이 풀리면 안 된다(`test_regroup` 이 칸 자체를 본다)
3. **바둑판은 슬라이드의 시야를 전부 싣고 지금 시야를 표시한다.** 다른 엔진을
   보는 중이면 링크가 `?batch=` 를 들고 간다 — 맨 주소로 가면 엔진이 풀린다
4. **도감 칸은 오프라인 파일에 안 실린다** — 물어볼 서버가 없다
"""
import re

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx


class ReviewLayoutTest(DiaRUGATestCase):

    def setUp(self):
        fx.make_classes()
        self.w = fx.make_world(slug="rs23", n_viewpoints=3, n_frames=3)
        self.c = Client()

    def _page(self, gid=0, q=""):
        r = self.c.get(reverse("group", args=[self.w.slug, gid]) + q)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_넓힌_화면이다(self):
        self.assertIn('<main class="wide">', self._page())

    def test_시야에_하는_일은_오른쪽_칸에_한_번만(self):
        html = self._page()
        self.assertEqual(html.count('class="resplit"'), 1)
        notes = html.index('<aside class="notes"')
        end = html.index("</aside>", notes)
        self.assertTrue(notes < html.index('class="resplit"') < end,
                        "가르기가 오른쪽 칸 밖에 놓였다")

    def test_읽기_전용이면_오른쪽_칸에_가르기가_없다(self):
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        html = self._page(q=f"?batch={run.pk}")
        self.assertNotIn('class="resplit"', html)

    def test_바둑판이_시야를_전부_싣고_지금_시야를_표시한다(self):
        html = self._page(gid=1)
        grid = html[html.index('id="vgrid-stack"'):]
        grid = grid[:grid.index("</div>")]
        hrefs = re.findall(r'href="([^"]+)"', grid)
        self.assertEqual(hrefs, [reverse("group", args=[self.w.slug, i])
                                 for i in range(3)])
        cur = re.findall(r'<a href="([^"]+)"\s+class="vt[^"]*\bcur\b', grid)
        self.assertEqual(cur, [reverse("group", args=[self.w.slug, 1])])

    def test_다른_엔진을_보는_중이면_바둑판이_엔진을_들고_간다(self):
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        html = self._page(q=f"?batch={run.pk}")
        grid = html[html.index('id="vgrid-stack"'):]
        grid = grid[:grid.index("</div>")]
        for h in re.findall(r'href="([^"]+)"', grid):
            self.assertTrue(h.endswith(f"?batch={run.pk}"), h)

    def test_검토율이_목록과_같은_집계다(self):
        html = self._page()
        m = re.search(r"검토 (\d+)/(\d+) \((\d+)%\)", html)
        self.assertIsNotNone(m, "검토율이 없다")
        self.assertEqual(m.group(2), "3")
