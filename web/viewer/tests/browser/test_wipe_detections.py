"""판의 검출을 한 번에 오검출로 돌린다 (220).

검출이 시원찮은 판은 전부 지우고 다시 그리는 편이 빠르다(사용자 2026-10-08 ·
yolo-3차). 연필 옆 단추(⊘)와 `S` 가 같은 함수를 부른다. **`S` 는 두 번 연속이어야
지운다**(223) — 한 번 누르면 ⊘ 에 빨간 불만 들어온다. 단추도 같다.

**밟기 쉬운 자리가 둘이다.**

- **사람이 그린 개체까지 지우면** 그리다가 한 번 더 누를 때 방금 그린 것이
  사라진다 — "검출" 만 비워야 한다
- `history` 를 개체마다 쌓으면 Ctrl+Z 를 개체 수만큼 눌러야 돌아온다 —
  확인 창 없이 지우는 근거가 "한 번에 되돌린다" 이므로 한 칸이어야 한다
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import Image, ObjectReview, RunBatch

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

    def press_ss(self, wait=1200):
        self.page.keyboard.press("s")
        self.page.wait_for_timeout(100)
        self.press("s", wait)

    def armed(self):
        return self.page.eval_on_selector(
            '#dv-stack button[data-act="wipe"]',
            "b => b.classList.contains('armed')")

    def test_S_두_번이면_판의_검출을_전부_지운다(self):
        self.open_review()
        self.assertEqual(self.removed_engine(), 0)
        self.press_ss()
        self.assertEqual(self.removed_engine(), 3, "검출이 전부 지워지지 않았다")
        self.assertFalse(self.armed(), "지운 뒤에도 불이 켜져 있다")

    def test_S_한_번은_불만_켜고_안_지운다(self):
        page = self.open_review()
        self.press("s", 300)
        self.assertTrue(self.armed(), "S 한 번에 ⊘ 에 불이 안 들어왔다")
        bg = page.eval_on_selector('#dv-stack button[data-act="wipe"]',
                                   "b => getComputedStyle(b).backgroundColor")
        self.assertNotEqual(bg, "rgba(0, 0, 0, 0.62)", "불이 CSS 에서 안 먹었다")
        page.wait_for_timeout(1600)                 # 기다리면 꺼진다
        self.assertFalse(self.armed(), "기다려도 불이 안 꺼진다")
        self.assertEqual(self.removed_engine(), 0, "S 한 번에 지워졌다")

    def test_사이에_다른_키를_누르면_풀린다(self):
        self.open_review()
        self.press("s", 100)
        self.press("x", 100)
        self.assertFalse(self.armed(), "다른 키에 불이 안 꺼졌다")
        self.press("s")
        self.assertEqual(self.removed_engine(), 0, "S·x·S 로 지워졌다")

    def test_너무_늦게_누른_두_번째는_다시_불만_켠다(self):
        self.open_review()
        self.press("s", 1700)
        self.press("s")
        self.assertEqual(self.removed_engine(), 0, "늦게 누른 S 로 지워졌다")

    def test_단추도_두_번_눌러야_지운다(self):
        page = self.open_review()
        page.click('#dv-stack button[data-act="wipe"]')
        page.wait_for_timeout(300)
        self.assertTrue(self.armed(), "단추 한 번에 불이 안 들어왔다")
        self.assertEqual(self.removed_engine(), 0, "단추 한 번에 지워졌다")
        page.click('#dv-stack button[data-act="wipe"]')
        page.wait_for_timeout(1200)
        self.assertEqual(self.removed_engine(), 3)

    def test_단추가_연필_옆에_보인다(self):
        page = self.open_review()
        b = page.query_selector('#dv-stack button[data-act="wipe"]')
        self.assertTrue(b and b.is_visible(), "지우기 단추가 안 보인다")
        # 레이어 토글과 겹치면 누를 수 없다 — 230 부터 연필·지우기는 왼쪽 「도구」,
        # 레이어는 오른쪽 「보기」 묶음이다. 지우기가 연필 바로 밑에 붙는다
        wb = b.bounding_box()
        lb = page.query_selector("#dv-stack .layers").bounding_box()
        self.assertLessEqual(wb["x"] + wb["width"], lb["x"],
                             "레이어 토글이 지우기 단추를 덮는다")
        db = page.query_selector('#dv-stack button[data-act="draw"]').bounding_box()
        self.assertAlmostEqual(db["x"], wb["x"], delta=1)
        self.assertLess(abs(wb["y"] - (db["y"] + db["height"])), 6, "지우기가 연필 곁에 없다")

    def test_그린_개체는_남긴다(self):
        page = self.open_review()
        page.click('#dv-stack button[data-act="draw"]')
        page.wait_for_timeout(150)
        for x, y in PTS:
            self.click_image(x, y)
        self.click_image(*PTS[0])                   # 첫 점을 다시 눌러 닫는다
        page.wait_for_timeout(900)
        self.assertEqual(ObjectReview.objects.filter(source="manual").count(), 1)

        self.press_ss()
        self.assertEqual(self.removed_engine(), 3)
        m = ObjectReview.objects.get(source="manual")
        self.assertFalse(m.removed, "S 가 사람이 그린 개체까지 지웠다")

    def test_Ctrl_Z_한_번에_전부_돌아온다(self):
        self.open_review()
        self.press_ss()
        self.assertEqual(self.removed_engine(), 3)
        self.press("Control+z")
        self.assertEqual(self.removed_engine(), 0,
                         "되돌리기 한 번에 전부 안 돌아왔다")


class WipeSoloDetectionsTest(BrowserTestCase):
    """「프레임 지움」 — 이 판에만 있는 검출만 지운다 (231).

    **다른 판과 묶인 개체는 남긴다.** 묶음은 사람이 "여러 판이 한 규조각" 이라고
    정한 것이다 — 한 판에서 비우는 일이 그 판단까지 지우면 안 된다. 단축키는
    없고(사용자 2026-10-23), 단추를 두 번 눌러야 지운다.
    """

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}",
                               n_frames=3, n_candidates=3)
        self.extra = fx.add_frame_detections(self.w.vp, n_candidates=3)
        batch = RunBatch.objects.get(label="sam2-시험")
        self.stack_img = Image.objects.get(viewpoint=self.w.vp, kind="stack")
        self.frame, self.frame_img, _ = self.extra[0]
        # 합성본과 첫 프레임의 첫 개체를 한 개체로 묶는다 (test_link_label 과 같다)
        self.key = self.w.keys()[0]
        rows = [fx.new_review(viewpoint=self.w.vp, image=img, batch=batch,
                              mask_key=self.key, bind_method="exact",
                              geom={"bbox_xywh": [40, 50, 60, 40]})
                for img in (self.stack_img, self.frame_img)]
        fx.link_reviews(rows, rep=0)

    def removed_on(self, img):
        return set(ObjectReview.objects.filter(image=img, removed=True,
                                               batch__isnull=False)
                   .values_list("mask_key", flat=True))

    def pick_frame(self):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]))
        page.wait_for_selector(".detview .box")
        el = page.query_selector(f'.shot[data-detkey="{self.frame.name}"]')
        el.scroll_into_view_if_needed()
        el.hover()
        page.wait_for_timeout(350)
        el.click()
        page.wait_for_timeout(400)
        return page

    def btn(self):
        return '#dv-stack button[data-act="wipesolo"]'

    def test_묶인_개체는_남기고_이_판에만_있는_것을_지운다(self):
        page = self.pick_frame()
        page.click(self.btn())
        page.wait_for_timeout(300)
        self.assertEqual(self.removed_on(self.frame_img), set(),
                         "단추 한 번에 지워졌다")
        page.click(self.btn())
        page.wait_for_timeout(1200)
        gone = self.removed_on(self.frame_img)
        self.assertEqual(len(gone), 2, f"이 판에만 있는 둘이 안 지워졌다: {gone}")
        self.assertNotIn(self.key, gone, "다른 판과 묶인 개체까지 지웠다")
        self.assertEqual(self.removed_on(self.stack_img), set(),
                         "다른 판(합성본)까지 지웠다")

    def test_전부_지움_아래에_놓인다(self):
        page = self.pick_frame()
        sb = page.query_selector(self.btn())
        self.assertTrue(sb and sb.is_visible(), "프레임 지움 단추가 안 보인다")
        s, w = sb.bounding_box(), page.query_selector(
            '#dv-stack button[data-act="wipe"]').bounding_box()
        self.assertAlmostEqual(s["x"], w["x"], delta=1)
        self.assertLess(abs(s["y"] - (w["y"] + w["height"])), 6,
                        "프레임 지움이 전부 지움 바로 밑에 없다")

    def test_S_는_전부_지움이다(self):
        """단축키를 안 단다 — `S` 두 번은 묶인 것까지 전부 지운다(220 그대로)."""
        page = self.pick_frame()
        page.click(self.btn())                  # 프레임 지움에 불을 켜 놓고
        page.wait_for_timeout(100)
        page.keyboard.press("s")                # S 는 그 불을 쓰지 않는다
        page.wait_for_timeout(1200)
        self.assertEqual(self.removed_on(self.frame_img), set(),
                         "프레임 지움 불이 S 로 이어졌다")
