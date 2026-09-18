"""산출 비교의 「비교 대상」 거르기가 **실제로 줄을 감추는가** (204).

3겹(`tests/test_compare.py`)은 체크박스와 `data-cls` 가 HTML 에 있는 것까지만
본다. 여기서 보는 것은 그 밖이다 — 체크를 끄면 그 줄이 **화면에서** 빠지는가,
분류를 끄면 그 아래 종명 체크박스가 잠기는가, 막대가 **분류의 색**으로
그려지는가. 이벤트 배선과 CSS 는 이 겹으로만 잡힌다(CLAUDE.md).
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class CompareFilterTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        # 후보 넷 = round · round_frag · rod · rod_frag. rod 에 종명 하나.
        self.a = fx.make_world(slug=f"a-{self.uniq}", site_code=f"RS{self.uniq}",
                               n_candidates=4)
        self.b = fx.make_world(slug=f"b-{self.uniq}", site_code=f"RS{self.uniq}",
                               sample_code="231cm", depth_cm=231.0, n_candidates=4)
        fx.add_review(self.a.vp, self.a.keys()[2],
                      species="Fragilariopsis kerguelensis")

    def _url(self):
        return (f"{reverse('compare')}?s={self.a.slide.slug}"
                f"&s={self.b.slide.slug}")

    def test_체크를_끄면_줄이_빠지고_분류를_끄면_종명이_잠긴다(self):
        page = self.open(self._url())
        rows = 'table tbody tr[data-cls="rod"]'
        self.assertEqual(page.locator(rows).count(), 2)       # 분류 줄 + 종명 줄
        for i in range(2):
            self.assertTrue(page.locator(rows).nth(i).is_visible())

        # 종명 하나만 끈다 — 그 줄만 빠지고 분류 줄은 남는다.
        page.locator('.cmp-filter input[data-sp="rod-1"]').click()
        self.assertTrue(page.locator(rows).nth(0).is_visible())
        self.assertFalse(page.locator(rows).nth(1).is_visible())
        # 상자 다섯 — 원형·봉상·종명·원형조각·봉상조각.
        self.assertEqual(page.inner_text(".cmp-filter [data-count]"), "4/5")

        # 분류를 끈다 — 둘 다 빠지고 종명 체크박스는 잠긴다.
        page.locator('.cmp-filter input[data-cls="rod"]:not([data-sp])').click()
        self.assertFalse(page.locator(rows).nth(0).is_visible())
        self.assertTrue(page.locator('.cmp-filter input[data-sp="rod-1"]')
                        .is_disabled())

        # 「전부」 — 다 돌아온다.
        page.click('.cmp-filter [data-all="1"]')
        for i in range(2):
            self.assertTrue(page.locator(rows).nth(i).is_visible())
        self.assertEqual(page.inner_text(".cmp-filter [data-count]"), "전부")

    def test_막대가_분류의_색으로_그려진다(self):
        page = self.open(self._url())
        cell = page.locator('table tbody tr.cls[data-cls="rod"] td.v').first
        bg = cell.evaluate("e => getComputedStyle(e).backgroundImage")
        # `ClassDef.color` 의 `70,140,255` 가 그대로 막대 색이다 — 선 색으로
        # 그리면 안 보인다(204).
        self.assertIn("rgba(70, 140, 255", bg)
        self.assertNotIn("rgba(139, 147, 163", bg)
