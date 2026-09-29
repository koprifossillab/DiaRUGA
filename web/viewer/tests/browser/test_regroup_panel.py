"""시야 가르기 칸이 **눈에 보이게** 켜지는가 (2026-09-29).

칸은 JS 없이 체크박스와 CSS(`:has(input:checked)`)만으로 켜진 자리를 칠한다.
CSS 가 안 먹으면 예외도 경고도 없다 — 사람이 어디를 골랐는지 화면에서 안 보이고,
그것이 이번에 반대로 가른 사고의 절반이었다. 그래서 계산된 색으로 확인한다.

`DIARUGA_SHOT_DIR` 을 주면 펼침판과 확인 화면을 캡처해 둔다(눈으로 볼 때).
"""
import os

from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class RegroupPanelTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}",
                               n_viewpoints=2, n_frames=5)

    def snap(self, name):
        d = os.environ.get("DIARUGA_SHOT_DIR")
        if d:
            self.page.screenshot(path=os.path.join(d, name), full_page=True)

    def test_켠_칸이_칠해지고_확인_화면에_조각이_나온다(self):
        page = self.open(reverse("group", args=[self.w.slug, 0]))
        page.click(".resplit > summary")
        cuts = page.locator(".rg-cut")
        self.assertEqual(cuts.count(), 4)
        bg = lambda i: cuts.nth(i).evaluate(
            "e => getComputedStyle(e).backgroundColor")
        before = bg(1)
        cuts.nth(1).click()
        self.assertNotEqual(bg(1), before, "켠 칸이 칠해지지 않았다")
        self.assertEqual(bg(0), before)
        self.snap("regroup_panel.png")

        page.click(".resplit form[action$='/split'] button[type=submit]")
        page.wait_for_selector(".rg-piece")
        self.assertEqual(page.locator(".rg-piece").count(), 2)
        self.assertEqual(page.locator(".rg-piece").nth(1)
                         .locator("figcaption").first.inner_text().split()[0],
                         "21002")
        self.snap("regroup_split_confirm.png")

    def test_합치기_확인_화면에_붙는_자리가_나온다(self):
        page = self.open(reverse("group", args=[self.w.slug, 0]))
        page.click(".resplit > summary")
        page.click(".rg-merge button")
        page.wait_for_selector(".rg-piece")
        self.assertEqual(page.locator(".rg-gap.joint").count(), 1)
        self.snap("regroup_merge_confirm.png")
