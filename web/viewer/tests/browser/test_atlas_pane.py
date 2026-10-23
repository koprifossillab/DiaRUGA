"""검토 화면 도감 칸 — 속 목록과 도판 확대·축소 (232).

사용자 2026-10-23: 속명 줄은 "선택이 너무 불편하네, 드롭다운 같은 걸로",
"정렬 기준이 무야? 찾기가 너무 불편하게", "도판도 확대축소 하게".

- 속은 **이름순** 고르는 목록이다. 229 는 많은 순으로 다시 정렬했다 —
  `views.group` 의 그 정렬을 되살리면 첫 시험이 죽는다(`Zeta` 가 앞에 온다)
- 도판은 휠로 커서 자리를 붙잡고 키우고, 두 번 누르면 맞춤으로 돌아온다.
  칸 폭보다 크게 보게 되면 **큰 그림(`w=2048`)으로 갈아 끼운다** — 900 짜리를
  늘려 보면 글자가 뭉개진다
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ..base import write_image
from ...models import Atlas, AtlasEntry, AtlasPlacement

SEL = "#atlasgen-stack"


class AtlasPaneTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}")
        a = Atlas.objects.create(key="schmidt", title="A. Schmidt, Atlas",
                                 short="Schmidt Atlas", sort_order=1)
        # **많은 순과 이름순이 갈리게 세운다** — Zeta 셋, Alpha 하나
        for i in range(3):
            AtlasEntry.objects.create(
                atlas=a, seq=10 + i, name=f"Zetaria sp{i}", genus="Zetaria",
                binomial=f"Zetaria sp{i}", rank="species")
        e = AtlasEntry.objects.create(
            atlas=a, seq=1, name="Alphaia minor", genus="Alphaia",
            binomial="Alphaia minor", rank="species")
        AtlasPlacement.objects.create(entry=e, seq=0, plate=3, volume="Band1",
                                      pdf_page=22, pdf_plate_page=23)
        write_image("atlas/schmidt/band1/p0023.png", size=(1200, 1600))

    def open_review(self):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]))
        page.wait_for_selector(SEL)
        return page

    def pick_alphaia(self):
        page = self.open_review()
        page.select_option(SEL, "Alphaia")
        page.wait_for_selector("#atlasrows-stack .arow")
        return page

    def open_plate(self):
        page = self.pick_alphaia()
        self.assertEqual(page.input_value("#atlasq-stack"), "Alphaia",
                         "속을 골랐는데 찾기 칸에 안 들어갔다")
        page.click("#atlasrows-stack .arow")
        page.wait_for_selector("#atlasplate-stack:not([hidden])")
        page.wait_for_function(
            "() => { const i = document.querySelector('#atlasplate-stack img');"
            " return i && i.complete && i.naturalWidth > 0; }")
        return page

    def test_속은_이름순_목록이다(self):
        page = self.open_review()
        tag = page.eval_on_selector(SEL, "e => e.tagName")
        self.assertEqual(tag, "SELECT", "속이 고르는 목록이 아니다")
        vals = page.eval_on_selector(
            SEL, "e => [...e.options].map(o => o.value).filter(Boolean)")
        self.assertEqual(vals, ["Alphaia", "Zetaria"],
                         f"이름순이 아니다 — 많은 순으로 정렬된 것 같다: {vals}")

    def test_속을_고르면_그_속으로_찾고_도판이_뜬다(self):
        page = self.open_plate()
        self.assertTrue(page.is_visible("#atlasplate-stack .pzoom img"))

    def test_휠로_키우고_두_번_누르면_맞춤이다(self):
        page = self.open_plate()
        box = page.query_selector("#atlasplate-stack .pzoom")
        box.scroll_into_view_if_needed()
        b = box.bounding_box()
        page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        for _ in range(8):
            page.mouse.wheel(0, -100)
            page.wait_for_timeout(40)
        tr = page.eval_on_selector("#atlasplate-stack img",
                                   "i => i.style.transform")
        self.assertIn("scale", tr, "휠로 안 커졌다")
        src = page.eval_on_selector("#atlasplate-stack img", "i => i.src")
        self.assertIn("w=2048", src, "키웠는데 큰 그림으로 안 바꿨다")
        # 상자 크기는 그대로다 — 도판이 칸을 밀어내면 안 된다
        self.assertAlmostEqual(box.bounding_box()["width"], b["width"], delta=1)
        box.dblclick()
        tr = page.eval_on_selector("#atlasplate-stack img",
                                   "i => i.style.transform")
        self.assertEqual(tr, "", "두 번 눌러도 맞춤으로 안 돌아왔다")

    def test_단추로_키우고_줄인다(self):
        page = self.open_plate()
        page.click('#atlasplate-stack button[data-z="in"]')
        self.assertIn("scale(1.5)", page.eval_on_selector(
            "#atlasplate-stack img", "i => i.style.transform"))
        page.click('#atlasplate-stack button[data-z="out"]')
        self.assertEqual(page.eval_on_selector(
            "#atlasplate-stack img", "i => i.style.transform"), "")
