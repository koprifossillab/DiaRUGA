"""사진 위 도구 묶음 둘 · 길이 재기 · 사진만 전체 화면 · 세 칸 높이 (230).

지키는 것:

1. **아이콘을 눌러도 단추가 듣는다.** 단추 안에 아이콘·이름이 들어가면서
   `e.target` 이 단추가 아니게 됐다 — `dataset.act` 만 보면 아이콘 위의 클릭이
   조용히 아무 일도 안 한다
2. **길이 재기의 클릭은 점 찍기다** — 개체가 골라지거나 저장이 나가면 안 된다.
   읽기 전용에서도 돈다(교정이 아니다)
3. **전체 화면에서도 검토한다** — 사진 칸이 창을 덮고, 우클릭 메뉴가 그 위에 뜬다
   (메뉴는 `body` 에 붙는다 — 사진 칸만 전체 화면으로 올리면 메뉴가 안 보인다)
4. **양옆 칸을 접어도 사진이 안 커지고**, 세 칸의 바닥이 맞는다
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import Detection, ObjectReview


class ReviewToolsTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)

    def open_review(self, q=""):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]) + q)
        page.wait_for_timeout(300)
        return page

    def umpp(self):
        d = Detection.objects.filter(viewpoint=self.w.vp, is_current=True).first()
        return d.um_per_pixel

    # --- 1. 아이콘 위의 클릭 ------------------------------------------------

    def test_아이콘을_눌러도_그리기가_켜진다(self):
        page = self.open_review()
        page.click('#dv-stack button[data-act="draw"] svg')
        page.wait_for_timeout(150)
        self.assertIn("drawing", page.get_attribute("#dv-stack", "class"),
                      "아이콘을 눌렀는데 그리기가 안 켜진다")
        # 한 번 누르면 한 번만 돈다 — 연필 상자가 도구 상자 안이라 두 번 걸면
        # 켜졌다 바로 꺼진다
        page.click('#dv-stack button[data-act="draw"] span')
        page.wait_for_timeout(150)
        self.assertNotIn("drawing", page.get_attribute("#dv-stack", "class"))

    # --- 2. 길이 재기 -------------------------------------------------------

    def measure(self, page, pts):
        page.click('#dv-stack button[data-act="measure"]')
        page.wait_for_timeout(100)
        for x, y in pts:
            self.click_image(x, y)
        self.click_image(*pts[-1])        # 같은 자리 다시 = 끝

    def test_길이를_µm_로_잰다(self):
        page = self.open_review()
        # 개체(280,210) 위를 지나게 찍는다 — 골라지면 안 된다. 왼쪽 위 모서리는
        # 도구 묶음이 덮고 있어 피한다
        self.measure(page, [(100, 210), (280, 210), (400, 210)])
        out = page.text_content("#measout-stack")
        um = 300 * (self.umpp() or 1)
        self.assertIn(f"{um:.1f} µm" if um < 100 else f"{round(um)} µm", out)
        self.assertIn("새로 잰다", out, "두 번 눌렀는데 끝나지 않았다")
        self.assertIn("2구간", out)
        self.assertEqual(page.text_content("#selinfo-stack").strip(), "선택 없음",
                         "재는 중의 클릭이 선택으로 샜다")
        page.wait_for_timeout(600)
        self.assertFalse(ObjectReview.objects.exists(), "재기가 저장을 냈다")
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        self.assertFalse(page.is_visible("#measout-stack"), "Esc 로 안 꺼진다")
        self.assertEqual(page.query_selector_all("svg.masks g.measure circle"), [])
        self.assertEqual(self.errors, [])

    def test_읽기_전용에서도_잰다(self):
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        page = self.open_review(f"?batch={run.pk}")
        self.assertFalse(page.is_visible('#dv-stack button[data-act="draw"]'))
        self.measure(page, [(100, 100), (400, 100)])
        self.assertIn("µm" if self.umpp() else "px", page.text_content("#measout-stack"))
        self.assertEqual(self.errors, [])

    # --- 3. 전체 화면 -------------------------------------------------------

    def test_전체_화면에서_우클릭_메뉴가_보인다(self):
        page = self.open_review()
        page.click('#dv-stack button[data-act="full"]')
        page.wait_for_timeout(300)
        box = page.query_selector("#dv-stack").bounding_box()
        self.assertGreaterEqual(box["width"], 1399, "사진 칸이 창을 안 덮는다")
        self.assertGreaterEqual(box["height"], 899)
        # 돌아오는 단추가 보인다
        self.assertTrue(page.is_visible('#dv-stack button[data-act="full"]'))
        self.assertIn("돌아가기", page.text_content('#dv-stack button[data-act="full"]'))
        menu = self.context_menu_at(160, 130)
        self.assertIsNotNone(menu, "전체 화면에서 메뉴가 안 열린다")
        mb = menu.bounding_box()
        top = page.evaluate("([x, y]) => !!document.elementFromPoint(x, y).closest('.ctxmenu')",
                            [mb["x"] + mb["width"] / 2, mb["y"] + mb["height"] / 2])
        self.assertTrue(top, "메뉴가 사진 칸 밑에 깔렸다")
        page.keyboard.press("Escape")
        page.click('#dv-stack button[data-act="full"]')
        page.wait_for_timeout(300)
        self.assertNotIn("full", page.get_attribute("#dv-stack", "class"))
        self.assertLess(page.query_selector("#dv-stack").bounding_box()["width"], 1300)
        self.assertEqual(self.errors, [])

    # --- 4. 세 칸 높이 ------------------------------------------------------

    def bottoms(self, page):
        return page.evaluate("""() => ['.detrow .dvside', '.detrow .dvcenter', '.detrow .notes']
            .map(s => document.querySelector(s))
            .filter(e => e && e.offsetParent)
            .map(e => Math.round(e.getBoundingClientRect().bottom))""")

    def test_양옆을_접어도_사진이_안_커지고_바닥이_맞는다(self):
        page = self.open_review()
        b = self.bottoms(page)
        self.assertEqual(len(b), 3)
        self.assertLessEqual(max(b) - min(b), 1, f"세 칸 바닥이 어긋난다 {b}")
        before = page.query_selector("#canvas-stack").bounding_box()
        page.click('[data-lay="left"]')
        page.click('[data-lay="right"]')
        page.wait_for_timeout(300)
        after = page.query_selector("#canvas-stack").bounding_box()
        self.assertAlmostEqual(after["height"], before["height"], delta=2,
                               msg="양옆을 접었더니 사진이 커졌다")
        self.assertLessEqual(after["y"] + after["height"], 900, "사진이 창을 넘는다")
