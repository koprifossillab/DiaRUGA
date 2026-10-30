"""묶음 상자와 옮긴 내보내기 단추 — 브라우저에서만 갈리는 것 (2026-10-30).

1. **상자를 누르면 `leave()` 로 떠난다** (116). 상자는 링크라 그냥 두면
   브라우저가 곧바로 옮긴다 — 밀어낸 저장이 거절당해도 떠나 버리고, 판단이
   실패 띠와 함께 화면에서 사라진다. 엔진 라디오가 옛 모양으로 남아 그렇게
   됐던 자리다.
2. **내보내기는 「보기」 묶음에 있고 읽기 전용에서도 보인다.** 읽기 전용 화면은
   사진 위 도구를 감추는데(`group.html`), 내보내기는 보는 일이다.
"""
import json

from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import ObjectReview


class BatchBoxLeaveTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=2)
        self.run = fx.add_other_engine(self.w.vp, label=f"yolo-4차-{self.uniq}")
        self.url = reverse("group", args=[self.w.slug, self.w.vp.idx])

    def tearDown(self):
        # 409 는 시험이 일부러 낸 것이다 (`test_done_lost` 와 같다)
        self.errors = [e for e in self.errors if "409" not in e]
        super().tearDown()

    def block_review(self):
        self.page.route(
            "**/review",
            lambda route: route.fulfill(
                status=409, content_type="application/json",
                body=json.dumps({"ok": False, "error": "시험으로 막았다"})))

    def delete_first(self):
        """첫 후보를 오검출로 지운다 — 픽스처의 (40,50,60,40)."""
        self.context_menu_at(40 + 60 // 2, 50 + 40 // 2)
        self.page.get_by_text("오검출로 삭제", exact=False).first.click()

    def other_box(self):
        return f'#bpick-stack a.bbox[href*="batch={self.run.pk}"]'

    def test_상자가_보이고_주_묶음이_지금_보는_것이다(self):
        page = self.open(self.url)
        self.assertTrue(page.is_visible("#bpick-stack .bbox.now.prim"))
        self.assertIn("주 묶음", page.inner_text("#bpick-stack .bbox.now"))
        self.assertTrue(page.is_visible(self.other_box()))

    def test_저장이_거절당하면_상자를_눌러도_안_떠난다(self):
        page = self.open(self.url)
        here = page.url
        self.block_review()
        self.delete_first()
        page.click(self.other_box())
        page.wait_for_timeout(900)
        self.assertEqual(page.url, here,
                         "저장이 거절당했는데 다른 묶음으로 떠났다")
        self.assertIsNotNone(page.query_selector(".errbar.savefail"))

    def test_저장이_되면_저장하고_떠난다(self):
        """**대조군이다.** 아예 못 떠나게 만들어도 위 시험은 통과한다."""
        page = self.open(self.url)
        self.delete_first()
        with page.expect_navigation():
            page.click(self.other_box())
        self.assertIn(f"batch={self.run.pk}", page.url)
        self.assertTrue(ObjectReview.objects.filter(
            viewpoint=self.w.vp, removed=True).exists(),
            "떠나기 전에 밀어낸 저장이 안 나갔다")
        # 읽기 전용 화면에서는 그 상자가 지금 보는 것이다
        self.assertTrue(page.is_visible(self.other_box() + ".now"))


class ExportButtonPlaceTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=2)
        self.run = fx.add_other_engine(self.w.vp)
        self.url = reverse("group", args=[self.w.slug, self.w.vp.idx])

    def test_보기_묶음_안에_있다(self):
        page = self.open(self.url)
        self.assertIsNotNone(page.query_selector("#viewtool-stack #export-stack"))
        self.assertIsNone(page.query_selector("#tabs-stack #export-stack"))
        self.assertTrue(page.is_visible("#export-stack"))

    def test_읽기_전용에서도_보이고_열린다(self):
        page = self.open(f"{self.url}?batch={self.run.pk}")
        # 전제 — 이 화면은 사진 위 도구를 감춘다
        self.assertFalse(page.is_visible("#tools-stack"),
                         "전제가 틀렸다 — 읽기 전용인데 도구가 보인다")
        self.assertTrue(page.is_visible("#export-stack"),
                        "읽기 전용에서 내보내기가 감춰졌다")
        page.click("#export-stack")
        page.wait_for_selector("#exdlg-stack:not([hidden])")
