"""첫 화면의 기본값과 해역 머리 접기 (2026-10-30) — 배선.

3겹(`test_index_seas.py`)은 `data-first` 와 열쇠가 **있다**는 것까지 본다.
여기가 더하는 것은 스크립트가 그것을 실제로 따르는가다 — 기억해 둔 보기
방식·지도 범위·고른 코어가 있어도 인자 없는 첫 화면은 지도 · 남극 전체 ·
RS14-GC04 로 열리고, 주소에 `area` 가 실리면 다시 기억대로 열린다. 그리고
해역 머리를 접으면 그 아래 지역·지점 `<tbody>` 가 실제로 사라진다
(`display` 는 여기서만 잡힌다).
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import Site

MEMORY = ("() => { localStorage.setItem('diaruga.dsview', 'table');"
          " localStorage.setItem('diaruga.mapzoom', 'ross');"
          " localStorage.setItem('diaruga.mapcore', 'RS23-GC03'); }")


class FirstScreenTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        u = self.uniq
        fx.make_world(slug=f"r23-{u}", site_code="RS23", loc_code="GC03",
                      sample_code=f"{u}1cm", depth_cm=u * 10 + 1, with_files=False)
        fx.make_world(slug=f"r14-{u}", site_code="RS14", loc_code="GC04",
                      sample_code=f"{u}6cm", depth_cm=u * 10 + 6, with_files=False)
        fx.make_world(slug=f"am-{u}", site_code="AM22", loc_code="GC10B",
                      sample_code=f"{u}5cm", depth_cm=u * 10 + 5, with_files=False)
        Site.objects.filter(code__in=["RS23", "RS14"]).update(
            region="로스해", lat=-75.0, lon=170.0)
        Site.objects.filter(code="AM22").update(region="아문젠해",
                                                lat=-73.0, lon=-110.0)

    def display(self, sel):
        return self.page.evaluate(
            "s => getComputedStyle(document.querySelector(s)).display", sel)

    def state(self):
        return self.page.evaluate("""() => ({
          view: document.querySelector('#viewtoggle button.on').dataset.view,
          zoom: document.querySelector('#mapzoom button.on').dataset.zoom,
          core: (document.querySelector('.maptree .mcore.on') || {dataset: {}}).dataset.core,
        })""")

    def test_첫_화면은_기억과_상관없이_지도_남극_전체_RS14_GC04_다(self):
        page = self.open(reverse("index") + "?area=ant")
        page.evaluate(MEMORY)

        page = self.open(reverse("index"))
        self.assertEqual(self.state(), {"view": "map", "zoom": "all",
                                        "core": "RS14-GC04"})
        self.assertEqual(self.display(".mapdetail .mcorebox[data-core='RS14-GC04']"),
                         "block")
        # 기억은 덮지 않았다
        self.assertEqual(page.evaluate(
            "() => localStorage.getItem('diaruga.mapcore')"), "RS23-GC03")

        # 주소에 권역이 실리면 기억대로 연다
        page = self.open(reverse("index") + "?area=ant")
        self.assertEqual(self.state(), {"view": "table", "zoom": "ross",
                                        "core": "RS23-GC03"})
        self.assertEqual(self.errors, [])

    def test_해역_머리를_접으면_지역과_지점이_사라진다(self):
        page = self.open(reverse("index") + "?area=ant")
        page.click("#viewtoggle button[data-view=table]")
        site = "tbody.ssgroup[data-gkey='site:RS14']"
        core = "tbody.csgroup[data-gkey='RS14/GC04']"
        other = "tbody.ssgroup[data-gkey='site:AM22']"
        self.assertNotEqual(self.display(site), "none")

        page.click("tbody.seagroup[data-gkey='sea:로스해'] .chead")
        self.assertEqual(self.display(site), "none")
        self.assertEqual(self.display(core), "none")
        self.assertNotEqual(self.display(other), "none")
        # 카드도 같은 열쇠를 따른다
        self.assertFalse(page.evaluate(
            "() => document.querySelector(\"details.zgroup[data-gkey='sea:로스해']\").open"))

        # 다시 열어도 남는다 — 지역만 접은 것은 따로 기억된다
        page = self.open(reverse("index") + "?area=ant")
        self.assertEqual(self.display(core), "none")
        page.click("tbody.seagroup[data-gkey='sea:로스해'] .chead")
        self.assertNotEqual(self.display(core), "none")
        page.click(f"{site} .chead")
        self.assertEqual(self.display(core), "none")
        self.assertNotEqual(self.display(site), "none")
        self.assertEqual(self.errors, [])
