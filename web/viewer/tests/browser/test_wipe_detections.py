"""판의 검출을 한 번에 오검출로 돌린다 (220).

검출이 시원찮은 판은 전부 지우고 다시 그리는 편이 빠르다(사용자 2026-10-08 ·
yolo-3차). 연필 옆 단추(⊘)와 `S` 가 같은 함수를 부른다.

**밟기 쉬운 자리가 둘이다.**

- **사람이 그린 개체까지 지우면** 그리다가 한 번 더 누를 때 방금 그린 것이
  사라진다 — "검출" 만 비워야 한다
- `history` 를 개체마다 쌓으면 Ctrl+Z 를 개체 수만큼 눌러야 돌아온다 —
  확인 창 없이 지우는 근거가 "한 번에 되돌린다" 이므로 한 칸이어야 한다
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import ObjectReview

# 픽스처 개체(40,50 / 160,130 / 280,210)와 안 겹치는 빈 자리
PTS = [(420, 300), (500, 300), (500, 360), (420, 360)]


class WipeDetectionsTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)

    def open_review(self):
        return self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]))

    def removed_engine(self):
        return ObjectReview.objects.filter(removed=True,
                                           batch__isnull=False).count()

    def press(self, key, wait=1200):
        self.page.keyboard.press(key)
        self.page.wait_for_timeout(wait)            # 지연 저장 400 ms

    def test_S_는_판의_검출을_전부_지운다(self):
        self.open_review()
        self.assertEqual(self.removed_engine(), 0)
        self.press("s")
        self.assertEqual(self.removed_engine(), 3, "검출이 전부 지워지지 않았다")

    def test_단추도_같은_일을_한다(self):
        page = self.open_review()
        page.click('#dv-stack button[data-act="wipe"]')
        page.wait_for_timeout(1200)
        self.assertEqual(self.removed_engine(), 3)

    def test_단추가_연필_옆에_보인다(self):
        page = self.open_review()
        b = page.query_selector('#dv-stack button[data-act="wipe"]')
        self.assertTrue(b and b.is_visible(), "지우기 단추가 안 보인다")
        # 레이어 토글과 겹치면 누를 수 없다 — 자리를 물렸는가
        wb = b.bounding_box()
        lb = page.query_selector("#dv-stack .layers").bounding_box()
        self.assertLessEqual(lb["x"] + lb["width"], wb["x"],
                             "레이어 토글이 지우기 단추를 덮는다")

    def test_그린_개체는_남긴다(self):
        page = self.open_review()
        page.click('#dv-stack button[data-act="draw"]')
        page.wait_for_timeout(150)
        for x, y in PTS:
            self.click_image(x, y)
        self.click_image(*PTS[0])                   # 첫 점을 다시 눌러 닫는다
        page.wait_for_timeout(900)
        self.assertEqual(ObjectReview.objects.filter(source="manual").count(), 1)

        self.press("s")
        self.assertEqual(self.removed_engine(), 3)
        m = ObjectReview.objects.get(source="manual")
        self.assertFalse(m.removed, "S 가 사람이 그린 개체까지 지웠다")

    def test_Ctrl_Z_한_번에_전부_돌아온다(self):
        self.open_review()
        self.press("s")
        self.assertEqual(self.removed_engine(), 3)
        self.press("Control+z")
        self.assertEqual(self.removed_engine(), 0,
                         "되돌리기 한 번에 전부 안 돌아왔다")
