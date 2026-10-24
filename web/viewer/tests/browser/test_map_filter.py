"""보일 슬라이드 고르기 · 로스해 확대의 나무 (203) — 배선.

3겹은 열쇠와 클래스가 **있다**는 것까지 본다. 여기가 더하는 것은 체크를
끄면 실제로 줄·마커가 사라지고 숫자가 따라오는가, 다시 열어도 남는가,
확대 상태에서 틀 밖 지점이 나무에서 빠지는가다. `.mhid` 가 `.maptree
.mslide` 의 display 에 지는 종류의 고장(063)은 `getComputedStyle` 로만 잡힌다.
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import Locality, Site


class MapFilterTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        u = self.uniq
        self.site = f"RS{u}"
        self.a = f"a-{u}"
        self.b = f"b-{u}"
        fx.make_world(slug=self.a, site_code=self.site, loc_code="GC02",
                      sample_code="10cm", depth_cm=10, n_viewpoints=2,
                      with_files=False)
        fx.make_world(slug=self.b, site_code=self.site, loc_code="GC02",
                      sample_code="20cm", depth_cm=20, n_viewpoints=3,
                      with_files=False)
        Locality.objects.filter(site__code=self.site).update(
            lat=-77.399902, lon=176.299317)
        # 틀 밖 — 남극반도
        self.wap = f"wap-{u}"
        fx.make_world(slug=self.wap, site_code=f"WAP{u}", loc_code="GC47",
                      with_files=False)
        Site.objects.filter(code=f"WAP{u}").update(lat=-65.3676, lon=-64.455)

    def display(self, sel):
        # 선택자에 따옴표가 든다 — 문자열에 끼워 넣지 않고 인자로 넘긴다.
        return self.page.evaluate(
            "s => getComputedStyle(document.querySelector(s)).display", sel)

    def open_map(self):
        page = self.open(reverse("index") + "?area=ant")
        page.click("#viewtoggle button[data-view=map]")
        return page

    def pick(self, page, core):
        page.click(f".maptree .mcore[data-core='{core}'] .mpick")

    def test_체크를_끄면_줄이_사라지고_숫자가_따라온다(self):
        page = self.open_map()
        self.pick(page, f"{self.site}-GC02")
        row = f".mapdetail .mslide[data-slug='{self.a}']"
        self.assertEqual(self.display(row), "table-row")
        self.assertEqual(page.inner_text(
            f".maptree .msite[data-site='{self.site}'] .nsl"), "2")

        page.click("#mapfilter summary")
        page.uncheck(f"#mapfilter input[data-slug='{self.a}']")
        self.assertEqual(self.display(row), "none")
        self.assertEqual(self.display(
            f".mapdetail .mslide[data-slug='{self.b}']"), "table-row")
        self.assertEqual(page.inner_text(
            f".maptree .msite[data-site='{self.site}'] .nsl"), "1")
        # 마커의 시야 수도 남은 줄로 다시 센다 (2 + 3 → 3)
        # SVG 글자라 `inner_text` 가 안 된다 — `text_content` 로 읽는다
        self.assertEqual(page.text_content(
            f".antmap:not(.rossmap) a[data-site='{self.site}'] .sub"), "시야 3")
        self.assertEqual(page.inner_text("#mapfilter-n"), "감춤 1장")

        # 다시 열어도 남는다
        page = self.open_map()
        self.assertEqual(self.display(row), "none",
                         "감춘 것을 다시 열었을 때 잊었다")
        page.click("#mapfilter summary")
        page.click("#mapfilter-all")
        self.assertEqual(self.display(row), "table-row")
        self.assertEqual(page.inner_text("#mapfilter-n"), "")

    def test_전부_끄면_지점과_마커까지_사라진다(self):
        page = self.open_map()
        marker = f".antmap:not(.rossmap) a[data-site='{self.site}']"
        self.assertNotEqual(self.display(marker), "none")
        page.click("#mapfilter summary")
        page.uncheck(f"#mapfilter input[data-slug='{self.a}']")
        page.uncheck(f"#mapfilter input[data-slug='{self.b}']")
        self.assertEqual(self.display(
            f".maptree .msite[data-site='{self.site}']"), "none")
        self.assertEqual(self.display(marker), "none")
        self.assertEqual(self.display(
            f".rossmap a[data-core='{self.site}-GC02']"), "none")

    def test_로스해_확대에서는_틀_밖_지점이_나무에서_빠진다(self):
        page = self.open_map()
        wap = f".maptree .msite[data-site='WAP{self.uniq}']"
        self.assertNotEqual(self.display(wap), "none")
        page.click("#mapzoom button[data-zoom=ross]")
        self.assertEqual(self.display(wap), "none")
        self.assertNotEqual(self.display(
            f".maptree .msite[data-site='{self.site}']"), "none")
        page.click("#mapzoom button[data-zoom=all]")
        self.assertNotEqual(self.display(wap), "none")


class MapCorePickTest(BrowserTestCase):
    """지도 화면의 세 칸 (234) — 나무에서 코어를 고르면 오른쪽 칸에 그 코어의
    관찰이 놓인다. 상자를 다 그려 두고 클래스로 갈아 끼우므로 `display` 로만
    잡힌다."""

    make_data = MapFilterTest.make_data
    display = MapFilterTest.display
    open_map = MapFilterTest.open_map

    def box(self, core):
        return f".mapdetail .mcorebox[data-core='{core}']"

    def test_고른_코어만_오른쪽에_놓이고_기억된다(self):
        rs, wap = f"{self.site}-GC02", f"WAP{self.uniq}-GC47"
        page = self.open_map()
        # 처음에는 무엇이든 하나가 골라져 있다 — 빈 칸으로 열지 않는다
        self.assertEqual(page.locator(".mapdetail .mcorebox.on").count(), 1)
        self.assertEqual(self.display(".mapdetail .mdempty"), "none")

        page.click(f".maptree .mcore[data-core='{wap}'] .mpick")
        self.assertEqual(self.display(self.box(wap)), "block")
        self.assertEqual(self.display(self.box(rs)), "none")
        self.assertEqual(page.get_attribute(
            f".maptree .mcore[data-core='{wap}'] .mpick", "aria-pressed"), "true")

        page.click(f".maptree .mcore[data-core='{rs}'] .mpick")
        self.assertEqual(self.display(self.box(rs)), "block")
        self.assertEqual(self.display(self.box(wap)), "none")
        self.assertEqual(self.display(
            f"{self.box(rs)} .mslide[data-slug='{self.b}']"), "table-row")

        # 지도에서도 그 지점을 짚는다 — 전체 지도는 지역, 확대는 지점 마커
        def picked(sel):
            return page.evaluate(
                "s => document.querySelector(s).classList.contains('picked')", sel)
        def stroke(sel):
            return page.evaluate(
                "s => getComputedStyle(document.querySelector(s + ' .dot')).strokeOpacity", sel)
        full = ".antmap:not(.rossmap) a[data-site='{}']"
        self.assertTrue(picked(full.format(self.site)))
        self.assertFalse(picked(full.format(f"WAP{self.uniq}")))
        self.assertTrue(picked(f".rossmap a[data-core='{rs}']"))
        self.assertEqual(stroke(full.format(self.site)), "0.35")

        page = self.open_map()
        self.assertEqual(self.display(self.box(rs)), "block",
                         "고른 코어를 다시 열었을 때 잊었다")

    def test_고른_코어를_통째로_감추면_다른_코어로_옮긴다(self):
        rs = f"{self.site}-GC02"
        page = self.open_map()
        page.click(f".maptree .mcore[data-core='{rs}'] .mpick")
        page.click("#mapfilter summary")
        page.uncheck(f"#mapfilter input[data-slug='{self.a}']")
        # 하나만 끄면 그대로 있고, 감춘 수를 적는다
        self.assertEqual(self.display(self.box(rs)), "block")
        self.assertEqual(page.inner_text(f"{self.box(rs)} .mdoff"), "1")
        page.uncheck(f"#mapfilter input[data-slug='{self.b}']")
        self.assertEqual(self.display(self.box(rs)), "none")
        self.assertEqual(page.locator(".mapdetail .mcorebox.on").count(), 1)
