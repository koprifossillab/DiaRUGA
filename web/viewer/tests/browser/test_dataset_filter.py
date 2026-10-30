"""시야 목록의 거르기 줄이 **실제로 거르는가** (2026-10-30 · 사용자).

3겹(`tests/test_dataset_page.py`)은 칩과 `data-*` 가 나오는 것까지 본다. 여기서
보는 것은 그 밖이다 — 칩을 누르면 표지가 감춰지는가, 찾기 칸이 듣는가, 고른 것이
다시 열어도 남는가. `[hidden]` 은 `.tile { display: … }` 에 지는 일이 두 번
있었다(063) — 감췄다고 적어 놓고 보이는 것을 `is_visible` 로 잡는다.
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class DatasetFilterTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}",
                               n_viewpoints=3, n_candidates=2)
        fx.review_done(self.w.viewpoints[0])

    def visible(self, page):
        return [t.query_selector(".t").inner_text().split(" ")[0]
                for t in page.query_selector_all(".grid .tile") if t.is_visible()]

    def test_칩이_거르고_수를_적는다(self):
        page = self.open(reverse("dataset", args=[self.w.slide.slug]))
        page.evaluate("() => localStorage.removeItem('diaruga.vpfilter')")
        page.reload()
        self.assertEqual(len(self.visible(page)), 3)

        page.click('.fgrp[data-f="rev"] .chip[data-v="no"]')
        done = f"g{self.w.viewpoints[0].idx}"
        self.assertNotIn(done, self.visible(page), "검토 완료 시야가 그대로 보인다")
        self.assertEqual(len(self.visible(page)), 2)
        self.assertIn("2 / 3", page.inner_text("#vpfilter-n"))

        page.click('.fgrp[data-f="rev"] .chip[data-v="yes"]')
        self.assertEqual(self.visible(page), [done])

        # **다시 열어도 남는다** — 검토하고 돌아올 때마다 다시 켜면 뜻이 없다
        page.reload()
        self.assertEqual(self.visible(page), [done])
        on = page.query_selector('.fgrp[data-f="rev"] .chip.on')
        self.assertEqual(on.get_attribute("data-v"), "yes")
        page.evaluate("() => localStorage.removeItem('diaruga.vpfilter')")

    def test_찾기_칸이_시야_번호로_찾는다(self):
        page = self.open(reverse("dataset", args=[self.w.slide.slug]))
        page.evaluate("() => localStorage.removeItem('diaruga.vpfilter')")
        page.reload()
        want = f"g{self.w.viewpoints[1].idx}"
        page.fill("#vpq", want)
        self.assertEqual(self.visible(page), [want])
        page.fill("#vpq", "")
        self.assertEqual(len(self.visible(page)), 3)
