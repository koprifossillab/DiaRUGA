"""첫 화면 로고 (235) — 탭을 새로 열면 덮개가 뜨고, 걷히고, 같은 탭에서는 다시
안 뜬다.

덮개는 클래스로 켜고 끄므로 `display` 로만 잡힌다. 다른 브라우저 시험은 이것을
본 것으로 치고 연다(`base.py` 의 `skip_splash`).
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class SplashTest(BrowserTestCase):

    skip_splash = False

    def make_data(self):
        fx.make_classes()
        fx.make_world(slug=f"sp-{self.uniq}", with_files=False)

    def shown(self):
        return self.page.evaluate(
            "() => getComputedStyle(document.getElementById('splash')).display")

    def test_새_탭에서_뜨고_걷히고_같은_탭에서는_다시_안_뜬다(self):
        page = self.open(reverse("index"))
        self.assertEqual(self.shown(), "flex")
        # GIF 를 받는다 — 주소가 살아 있다
        self.assertIn("/splash/logo.", page.get_attribute("#splash img", "src"))
        # 2.44초 + 0.9초 + 걷는 0.42초 안에 걷힌다
        page.wait_for_function(
            "() => !document.documentElement.classList.contains('splashing')",
            timeout=8000)
        self.assertEqual(self.shown(), "none")
        self.assertTrue(page.evaluate(
            "() => document.getElementById('splash').querySelector('img')"
            ".src.endsWith('logo.png')"), "끝 장면에서 원본 PNG 로 안 바꿨다")

        page = self.open(reverse("index") + "?area=kr")
        self.assertEqual(self.shown(), "none", "같은 탭에서 또 떴다")

    def test_누르면_바로_걷힌다(self):
        page = self.open(reverse("index"))
        self.assertEqual(self.shown(), "flex")
        page.click("#splash")
        page.wait_for_function(
            "() => !document.documentElement.classList.contains('splashing')",
            timeout=2000)
        self.assertEqual(self.shown(), "none")
