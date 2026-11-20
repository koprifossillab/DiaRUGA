"""카탈로그의 **크기 슬라이더**를 실제로 끌어 본다 (265).

3겹(`tests/test_catalog_filters.py`)은 주소를 받으면 무엇이 놓이는지까지 본다.
여기서 보는 것은 **손잡이가 그 주소를 만드는가**다 — 손잡이 둘을 한 줄에 포갠
것이라 깔린 쪽이 안 잡히거나, 둘이 엇갈려 아래 끝이 위 끝을 넘는 자리가
브라우저 안에서만 난다.
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import RunBatch


SET = """([sel, v]) => {
  const el = document.querySelector(sel);
  el.value = v;
  el.dispatchEvent(new Event('input', {bubbles: true}));
}"""


class CatalogSizeSliderTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=4)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        for _vp in self.w.viewpoints:
            fx.review_done(_vp)

    def open_catalog(self, q="?frag=1"):
        return self.open(reverse("catalog", args=[self.w.slide.slug]) + q)

    def bounds(self, page):
        box = page.locator("#fsize")
        return int(box.get_attribute("data-lo")), int(box.get_attribute("data-hi"))

    def lens(self, page):
        """카드의 「크기」 줄에 적힌 장축들."""
        return [float(t) for t in
                page.locator(".catcard .row.axes .v b:first-child").all_inner_texts()]

    def test_손잡이를_놓으면_그_범위로_걸린다(self):
        page = self.open_catalog()
        lo, hi = self.bounds(page)
        self.assertGreater(hi - lo, 2, "눈금이 좁아 시험이 헛돈다")
        before = self.lens(page)
        mid = (lo + hi) // 2
        page.evaluate(SET, ["#fsize input.a", str(mid)])
        # 끄는 동안은 글자만 따라간다 — 아직 안 떠났다
        self.assertEqual(page.locator("#fsize .va").inner_text(), str(mid))
        self.assertNotIn("lmin", page.url)
        with page.expect_navigation():
            page.locator("#fsize input.a").dispatch_event("change")
        self.assertIn(f"lmin={mid}", page.url)
        self.assertNotIn("lmax", page.url, "안 건드린 쪽 끝까지 걸었다")
        self.assertIn("frag=1", page.url, "걸어 둔 것이 풀렸다")
        after = self.lens(page)
        self.assertTrue(after and all(v >= mid for v in after), after)
        self.assertLess(len(after), len(before), "아무것도 안 걸러졌다")
        # 다시 열린 화면의 손잡이가 건 자리에 있다
        self.assertEqual(page.locator("#fsize input.a").input_value(), str(mid))
        with page.expect_navigation():
            page.locator("#fsize .fclear").click()
        self.assertNotIn("lmin", page.url)
        self.assertEqual(len(self.lens(page)), len(before))

    def test_키보드로도_걸린다(self):
        page = self.open_catalog()
        lo, hi = self.bounds(page)
        page.locator("#fsize input.b").focus()
        with page.expect_navigation():
            page.keyboard.press("ArrowLeft")
        self.assertIn(f"lmax={hi - 1}", page.url)

    def test_아래_끝이_위_끝을_못_넘는다(self):
        page = self.open_catalog()
        lo, hi = self.bounds(page)
        mid = (lo + hi) // 2
        page.evaluate(SET, ["#fsize input.b", str(mid)])
        page.evaluate(SET, ["#fsize input.a", str(hi)])
        self.assertEqual(page.locator("#fsize input.a").input_value(), str(mid))
        self.assertEqual(page.locator("#fsize .va").inner_text(), str(mid))

    def test_위쪽_끝에서_겹치면_아래_끝_손잡이가_잡힌다(self):
        """둘 다 위 끝에 있으면 덮은 쪽은 더 올릴 데가 없다 — 깔린 쪽이 안
        잡히면 범위를 다시 넓힐 길이 없다."""
        page = self.open_catalog()
        lo, hi = self.bounds(page)
        page.evaluate(SET, ["#fsize input.a", str(hi)])
        box = page.locator("#fsize input.a").bounding_box()
        # 손잡이의 자리(오른쪽 끝)에서 맨 위에 있는 것이 아래 끝 입력이어야 한다
        top = page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y).className",
            [box["x"] + box["width"] - 7, box["y"] + box["height"] / 2])
        self.assertEqual(top, "a")

    def test_정렬을_누르면_긴_것부터_놓인다(self):
        page = self.open_catalog()
        with page.expect_navigation():
            page.locator(".catfilters .chip", has_text="장축 긴 것부터").click()
        got = self.lens(page)
        self.assertEqual(got, sorted(got, reverse=True))
        self.assertGreater(len(set(got)), 1, "길이가 다 같아 시험이 헛돈다")
        self.assertIn("frag=1", page.url)
