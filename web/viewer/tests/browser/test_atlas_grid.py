"""도감 바둑판 보기·비교에 담기 (238).

**이 레이어로만 잡힌다.** 보기 고르기·담기·잠그기는 전부 JS 와 `localStorage`
라 3레이어(테스트 클라이언트)은 두 보기가 다 들어 있는 HTML 만 본다.

## 되살려서 잡히는가

- 1번 — 보기를 저장하지 않거나(`localStorage.setItem(VKEY…)` 를 빼면),
  앞머리 스크립트가 저장한 보기를 안 읽으면 실패한다. 새로고침하면 목록으로
  돌아가 사람이 판마다 다시 누른다
- 2번 — `.av-list .agrid` 감추기를 빼면 실패한다. 두 보기가 한꺼번에 놓인다
- 3번 — 「비교」의 주소를 담은 것에서 안 만들면 실패한다. 비교 화면이 주소로
  받으므로 새로고침하면 그대로여야 한다
- 4번 — 다섯이 찼을 때 나머지 고르기 칸을 안 잠그면 실패한다
- 5번 — 비교 표를 감싼 칸의 `overflow-x: auto` 를 빼면 실패한다. 좁은 화면에서
  **페이지 전체**가 가로로 굴러 머리줄까지 밀린다
"""
from django.urls import reverse

from .base import BrowserTestCase
from ..base import write_image
from ...models import Atlas, AtlasEntry, AtlasPlacement


class AtlasGridTest(BrowserTestCase):

    def make_data(self):
        a = Atlas.objects.create(key=f"t{self.uniq}", title="Test atlas",
                                 short="Test", sort_order=0)
        self.akey = a.key
        for i in range(7):
            e = AtlasEntry.objects.create(
                atlas=a, seq=i + 1, name=f"Navicula sp{i} AUTH.", genus="Navicula",
                binomial=f"Navicula sp{i}", rank="species",
                extra={"ecology": f"생태 {i}"})
            rel = f"atlas/{a.key}/crops/fig{i}.png"
            write_image(rel, size=(300, 200))
            AtlasPlacement.objects.create(entry=e, seq=0, plate=1, figures=str(i),
                                          pdf_page=1, pdf_plate_page=2, crop_image=rel)

    def search(self):
        page = self.open(reverse("atlas") + "?genus=Navicula")
        page.wait_for_selector("#aresults")
        return page

    def visible(self, page, sel):
        return page.evaluate(
            f"getComputedStyle(document.querySelector({sel!r})).display") != "none"

    # --- 1·2번 ---------------------------------------------------------------

    def test_바둑판으로_바꾸면_새로고침해도_남는다(self):
        page = self.search()
        self.assertTrue(self.visible(page, ".alist"))
        self.assertFalse(self.visible(page, ".agrid"), "목록 보기에 바둑판이 같이 놓였다")
        page.click("[data-aview=grid]")
        self.assertTrue(self.visible(page, ".agrid"))
        self.assertFalse(self.visible(page, ".alist"), "바둑판 보기에 목록이 같이 놓였다")
        # 그림이 실제로 뜬다 — 주소가 틀리면 "아직 안 떴다" 로 떨어진다
        page.wait_for_function(
            "() => document.querySelector('.acard img').naturalWidth > 0", timeout=10_000)
        page.reload()
        page.wait_for_selector("#aresults")
        self.assertTrue(self.visible(page, ".agrid"), "새로고침하니 목록으로 돌아갔다")
        self.assertIn("on", page.get_attribute("[data-aview=grid]", "class"))

    # --- 3번 -----------------------------------------------------------------

    def test_둘을_담아_비교로_가면_주소에_남는다(self):
        page = self.search()
        page.click("[data-aview=grid]")
        self.assertIn("off", page.get_attribute("#atray-go", "class"),
                      "하나도 안 담았는데 「비교」가 열려 있다")
        cbs = page.locator(".apick-cb")
        cbs.nth(3).check()
        cbs.nth(1).check()
        self.assertEqual(page.inner_text("#atray-n"), "2")
        with page.expect_navigation():
            page.click("#atray-go")
        self.assertIn("/atlas/compare/", page.url)
        names = page.locator("#cmp thead .cname").all_inner_texts()
        self.assertEqual(names, ["Navicula sp3 AUTH.", "Navicula sp1 AUTH."],
                         "고른 차례대로 놓이지 않았다")
        page.reload()
        self.assertEqual(page.locator("#cmp thead .cname").count(), 2,
                         "새로고침하니 비교가 사라졌다")
        # 비교 화면에서 뺀 것이 도감 화면의 담은 것에도 빠진다
        with page.expect_navigation():
            page.locator("#cmp thead .cdrop").first.click()
        page = self.search()
        self.assertEqual(page.inner_text("#atray-n"), "1")

    # --- 4번 -----------------------------------------------------------------

    def test_다섯이_차면_나머지를_잠근다(self):
        page = self.search()
        page.click("[data-aview=grid]")
        cbs = page.locator(".apick-cb")
        for i in range(5):
            cbs.nth(i).check()
        self.assertTrue(cbs.nth(5).is_disabled(), "다섯이 찼는데 여섯째를 고를 수 있다")
        cbs.nth(0).uncheck()
        self.assertFalse(cbs.nth(5).is_disabled(), "하나를 뺐는데 잠긴 채다")

    # --- 5번 -----------------------------------------------------------------

    def test_좁은_화면에서는_표만_가로로_민다(self):
        page = self.page
        page.set_viewport_size({"width": 390, "height": 800})
        keys = [f"{self.akey}:Navicula sp{i} AUTH." for i in range(4)]
        from urllib.parse import urlencode
        page = self.open(reverse("atlas_compare") + "?" + urlencode([("e", k) for k in keys]))
        page.wait_for_selector("#cmp")
        m = page.evaluate("""() => {
          const w = document.querySelector('.cmpwrap');
          return {doc: document.documentElement.scrollWidth, win: window.innerWidth,
                  inner: w.scrollWidth, outer: w.clientWidth};
        }""")
        self.assertLessEqual(m["doc"], m["win"] + 1, f"페이지 전체가 가로로 구른다 {m}")
        self.assertGreater(m["inner"], m["outer"], f"표가 좁은 화면에 눌려 들어갔다 {m}")
