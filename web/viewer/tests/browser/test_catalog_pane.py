"""검토 화면 오른쪽 칸의 **개체 카탈로그** — 화면 쪽 (183).

서버가 재료를 싣는 것과 저장 문이 도는 것은 3겹(`tests/test_catalog_pane.py`)이
본다. 여기서 보는 것은 **눌러서 되는가**이고 그건 3겹에서 안 보인다.

- 개체를 고르면 그 카드가 뜨는가 (선택 배선)
- 적으면 DB 로 가는가 — `/catalog/save` 는 개체 하나만 고치는 좁은 문이다
- **읽기 전용에서 칸이 잠기는가** (051). 저장만 막으면 사람이 적어 놓고 저장된
  줄 안다 — 그 판단은 어디에도 안 남는다
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import DiatomObject, ObjectReview, RunBatch


class CatalogPaneBrowserTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}",
                               n_frames=3, n_candidates=2)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        self.key = self.w.keys()[0]

    def open_review(self, query=""):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx])
                         + query)
        page.wait_for_selector(".detview .box")
        return page

    def pick_first(self):
        """첫 개체를 고른다 — 픽스처가 (40,50)에 60×40 으로 세운 것."""
        self.click_image(40 + 30, 50 + 20)
        self.page.wait_for_timeout(200)

    def box(self):
        return self.page.query_selector("#catbox-stack")

    def test_고르면_카드가_뜨고_해제하면_사라진다(self):
        self.open_review()
        self.assertTrue(self.box().is_hidden(), "고르기 전인데 카드가 떠 있다")
        self.pick_first()
        self.assertTrue(self.box().is_visible(), "개체를 골랐는데 카드가 없다")
        # **아직 아무도 안 본 후보다** — 카드가 없다고 말해야 한다
        self.assertIn("아직 카드가 없습니다",
                      self.page.inner_text("#catno-stack"))

    # --- 고른 것이 없을 때의 개체 목록 (2026-11-19) ---

    def rows(self):
        return self.page.query_selector_all("#catlist-stack .crowl")

    def test_고르기_전에는_개체_목록이_뜬다(self):
        """안내 한 줄만 있던 자리다 — 줄에 유형·종명이 실리고 유형은 제 색이다."""
        fx.add_review(self.w.vp, self.key, species="Eucampia antarctica",
                      label="rod")
        self.open_review()
        rows = self.rows()
        self.assertEqual(len(rows), 2, "개체가 둘인데 줄 수가 다르다")
        self.assertTrue(self.page.query_selector("#catsay-stack").is_hidden(),
                        "목록이 떴는데 안내가 함께 남아 있다")
        mine = [r for r in rows if "Eucampia antarctica" in r.inner_text()]
        self.assertEqual(len(mine), 1, "종명이 줄에 안 실렸다")
        want = self.page.evaluate(
            "() => JSON.parse(document.getElementById('cls-stack').textContent)"
            ".find(d => d.key === 'rod').color")
        got = self.page.evaluate(
            "e => getComputedStyle(e.querySelector('.cls')).color", mine[0])
        self.assertEqual(got.replace(" ", ""), f"rgb({want})".replace(" ", ""),
                         "유형 글자가 그 유형의 색이 아니다")

    def test_목록의_줄을_누르면_그_개체의_카드가_뜬다(self):
        self.open_review()
        self.rows()[0].click()
        self.page.wait_for_timeout(200)
        self.assertTrue(self.box().is_visible(), "줄을 눌렀는데 카드가 없다")
        self.assertTrue(self.page.query_selector("#catlist-stack").is_hidden(),
                        "카드가 떴는데 목록이 남아 있다")
        self.assertEqual(len(self.page.query_selector_all(".detview .box.sel")),
                         1, "줄을 눌렀는데 사진에서 고른 표시가 없다")

    def test_지운_개체는_목록에서_빠진다(self):
        self.open_review()
        self.pick_first()
        self.page.keyboard.press("Space")          # 오검출로 지운다
        self.page.wait_for_timeout(300)
        self.assertTrue(self.page.query_selector("#catlist-stack").is_visible(),
                        "지우고 나서 목록이 안 돌아왔다")
        self.assertEqual(len(self.rows()), 1, "지운 개체가 목록에 남아 있다")

    def test_칸이_좁으면_두_줄_넓으면_한_줄이다(self):
        """칸 폭은 사람이 끌어 바꾼다 — 화면 폭이 아니라 **칸의 폭**을 본다."""
        self.open_review()
        tops = ("e => [e.querySelector('.no'), e.querySelector('.cls')]"
                ".map(x => Math.round(x.getBoundingClientRect().top))")
        no, cls = self.page.evaluate(tops, self.rows()[0])
        self.assertGreater(cls, no, "좁은 칸인데 유형이 순번과 같은 줄에 있다")
        self.page.evaluate(
            "() => { var n = document.getElementById('notes-stack');"
            " n.style.flex = '0 0 460px'; n.style.width = '460px'; }")
        self.page.wait_for_timeout(200)
        no, cls = self.page.evaluate(tops, self.rows()[0])
        self.assertLess(abs(cls - no), 4, "넓은 칸인데 두 줄로 남아 있다")

    def test_종명을_적으면_개체에_저장된다(self):
        """**그 순간 개체가 생긴다** — 적기 전에는 카드가 없는 것이 맞다."""
        self.open_review()
        self.pick_first()
        self.page.fill("#catsp-stack", "Eucampia antarctica")
        self.page.wait_for_timeout(900)          # 지연 저장 400ms + 응답
        row = ObjectReview.objects.filter(mask_key=self.key).first()
        self.assertIsNotNone(row, "판정 줄이 안 생겼다")
        self.assertEqual(row.diatom_object.species, "Eucampia antarctica")
        # 방금 생긴 카드의 번호가 화면에 놓인다 — 새로고침을 안 기다린다
        self.assertIn("S1", self.page.inner_text("#catno-stack"))

    def test_유형은_이_화면의_문으로_간다(self):
        """유형은 `labels` 라 판 payload 가 통째로 보내는 값이다 (104).

        카탈로그의 문으로 적으면 화면이 모르는 값이 되어 **다음 저장이 방금
        적은 것을 지운다** — 그래서 이 칸만 `setLabel` 로 간다. 지정한 뒤
        마스크의 색까지 바뀌는지 함께 본다(그 길로 갔다는 증거다).
        """
        self.open_review()
        self.pick_first()
        self.page.select_option("#catcls-stack", "rod")
        self.page.wait_for_timeout(900)
        obj = ObjectReview.objects.get(mask_key=self.key).diatom_object
        self.assertEqual(obj.label, "rod")
        self.assertEqual(
            len(self.masks_svg().query_selector_all("polygon.rod")), 1,
            "유형을 지정했는데 마스크 색이 안 따라왔다")

    def test_등급과_자세는_완형에만_뜬다(self):
        """파편으로 지정하면 두 칸이 아예 없다 — 서버도 `check_grade_pose` 로
        다시 막는다(063: 화면에서 막는 것은 막는 것이 아니다)."""
        self.open_review()
        self.pick_first()
        self.assertTrue(self.page.query_selector("#catgp-stack").is_visible(),
                        "분류 전인데 등급·자세가 감춰져 있다")
        self.page.select_option("#catcls-stack", "rod_frag")
        self.page.wait_for_timeout(900)
        self.assertTrue(self.page.query_selector("#catgp-stack").is_hidden(),
                        "파편인데 등급·자세 칸이 남아 있다")

    def test_읽기_전용에서는_칸이_잠긴다(self):
        """다른 엔진을 고른 화면이다 — 저장만 막으면 사람이 헛검토한다 (051)."""
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        self.open_review(f"?batch={run.id}")
        # **다른 엔진은 다른 자리에 낸다** — 픽스처가 (300,250)부터 세운다.
        # 현재 검출의 좌표로 누르면 아무것도 안 골라져 이 시험이 헛돈다.
        self.click_image(300 + 27, 250 + 22)
        self.page.wait_for_timeout(200)
        box = self.box()
        if box.is_hidden():
            self.fail("읽기 전용 화면에서 개체를 골랐는데 카드가 안 떴다")
        for sel in ("#catsp-stack", "#catcls-stack", "#catnote-stack"):
            self.assertTrue(self.page.query_selector(sel).is_disabled(),
                            f"읽기 전용인데 칸이 살아 있다: {sel}")

    def test_시야_메모_상자가_없다(self):
        """183 에서 걷었다 — 우클릭 메뉴 항목까지 함께 걷었는지 본다."""
        self.open_review()
        self.assertIsNone(self.page.query_selector("#gnote-stack"))
        menu = self.context_menu_at(600, 500)
        if menu is not None:
            self.assertNotIn("시야 코멘트", menu.inner_text())

    def test_카드가_지워지면_화면도_그렇게_말한다(self):
        """표시가 하나도 안 남으면 그 줄을 지운다 (`_catalog_prune`)."""
        self.open_review()
        self.pick_first()
        self.page.fill("#catsp-stack", "Eucampia sp.")
        self.page.wait_for_timeout(900)
        self.assertTrue(DiatomObject.objects.filter(viewpoint=self.w.vp)
                        .exists())
        self.page.fill("#catsp-stack", "")
        self.page.wait_for_timeout(900)
        self.assertFalse(DiatomObject.objects.filter(viewpoint=self.w.vp)
                         .exists(), "다 비웠는데 개체가 남았다")
        self.assertIn("아직 카드가 없습니다",
                      self.page.inner_text("#catno-stack"))
