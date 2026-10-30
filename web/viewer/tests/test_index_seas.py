"""첫 화면 — 해역 → 지역 → 지점 묶음 · 인자 없는 첫 화면 · 이름표는 코드 (2026-10-30).

잡는 것 넷:

- **해역 겹이 표·카드·지도 나무에 같이 있다.** 해역은 `Site.region` 이고, 같은
  해역의 지역은 코드가 떨어져 있어도 한 머리에 모인다. 해역이 하나도 없는 권역
  (한국)은 해역 머리 없이 지역부터다.
- **머리 숫자는 숨긴 것까지 센다** — 지점 머리줄과 같은 규칙이다.
- **인자 없이 열면 남극이고 첫 화면 표시가 붙는다.** 주소에 무엇이든 있으면 안 붙는다.
- **지역의 이름표는 어디서나 코드다.** 해역·이름을 채워도 "RS14" 가 "로스해" 로
  안 바뀐다 — 예전에는 해역 → 이름 → 코드 순으로 골랐다.
"""
import importlib
import re

from django.apps import apps as django_apps
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .test_detection_js import js_blocks
from .. import data
from ..models import Site, Slide


def tbody_heads(html):
    """표의 `<tbody>` 를 나온 순서대로 (클래스, 열쇠, data-sea, data-site)."""
    out = []
    for m in re.finditer(r'<tbody class="(\w+)" data-gkey="([^"]*)"([^>]*)>', html):
        rest = m.group(3)
        sea = re.search(r'data-sea="([^"]*)"', rest)
        site = re.search(r'data-site="([^"]*)"', rest)
        out.append((m.group(1), m.group(2), sea and sea.group(1),
                    site and site.group(1)))
    return out


class SeaGroupingTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 코드순으로 AM22 · GC03 · RS21 · RS23 · ZZ99 — 남극반도(GC03)와 그 짝을
        # 떨어뜨려 놓으려고 ZZ99 를 남극반도로 둔다. 해역이 빈 XX01 은 끝으로 간다.
        for slug, sc, lc, d in [("am", "AM22", "GC10B", 25), ("gc", "GC03", "C1", 72),
                                ("r1", "RS21", "GC02", 4), ("r2", "RS21", "GC05", 6),
                                ("r3", "RS23", "GC03", 71), ("r4", "RS23", "GC03", 231),
                                ("xx", "XX01", "GC01", 10), ("zz", "ZZ99", "GC09", 9)]:
            fx.make_world(slug=slug, site_code=sc, loc_code=lc,
                          sample_code=f"{d}cm", depth_cm=d, with_files=False)
        for code, sea in [("AM22", "아문젠해"), ("GC03", "남극반도"), ("RS21", "로스해"),
                          ("RS23", "로스해"), ("ZZ99", "남극반도")]:
            Site.objects.filter(code=code).update(region=sea)
        # 지도에 찍히려면 자리가 있어야 한다(없으면 `map_points` 가 뺀다)
        Site.objects.filter(area="ant").update(lat=-75.0, lon=170.0)
        # 숨긴 슬라이드 — 머리 숫자에는 들어간다
        Slide.objects.filter(slug="r4").update(hide_in_list=True)
        fx.make_world(slug="bp", area="kr", kind="outcrop", site_code="BP",
                      loc_code="BP09", sample_code="0901", with_files=False)
        Site.objects.filter(code="BP").update(lat=37.5, lon=129.1)

    def html(self, **q):
        r = self.client.get(reverse("index"), q)
        self.assertEqual(r.status_code, 200)
        return r, r.content.decode()

    def test_표의_머리가_해역_지역_지점_순으로_놓인다(self):
        _, html = self.html(area="ant")
        heads = tbody_heads(html)
        seas = [k for c, k, _, _ in heads if c == "seagroup"]
        # 처음 나온 순서 · 같은 해역은 한 머리 · 빈 해역은 끝
        self.assertEqual(seas, ["sea:아문젠해", "sea:남극반도", "sea:로스해",
                                "sea:"])
        i = heads.index(("seagroup", "sea:남극반도", None, None))
        self.assertEqual(heads[i + 1], ("ssgroup", "site:GC03", "sea:남극반도", None))
        self.assertEqual(heads[i + 2],
                         ("csgroup", "GC03/C1", "sea:남극반도", "site:GC03"))
        self.assertEqual(heads[i + 3], ("ssgroup", "site:ZZ99", "sea:남극반도", None))
        # RS21 의 지점 둘이 한 지역 머리 아래
        j = heads.index(("ssgroup", "site:RS21", "sea:로스해", None))
        self.assertEqual([h[1] for h in heads[j + 1:j + 3]], ["RS21/GC02", "RS21/GC05"])
        self.assertIn("해역 미정", html)

    def test_머리_숫자는_숨긴_것까지_센다(self):
        r, _ = self.html(area="ant")
        seas = r.context["seas"]
        ross = next(z for z in seas if z["sea"] == "로스해")
        rs23 = next(s for s in ross["sites"] if s["site_code"] == "RS23")
        self.assertEqual(rs23["n"], 1)
        self.assertEqual(rs23["n_hidden"], 1)
        rows = data.datasets("ant")
        want = data.datasets_total([x for x in rows if x["site_code"] == "RS23"])
        self.assertEqual(rs23["totals"]["n_images"], want["n_images"])
        self.assertEqual(ross["totals"]["n_images"], sum(
            s["totals"]["n_images"] for s in ross["sites"]))
        self.assertEqual(ross["n_loc"], 3)

    def test_카드도_같은_겹이다(self):
        _, html = self.html(area="ant")
        cards = html[html.index('class="asCards'):]
        self.assertIn('<details class="cgroup zgroup" data-gkey="sea:로스해" open>', cards)
        self.assertIn('<details class="cgroup sgroup" data-gkey="site:RS21" open>', cards)

    def test_지도_나무도_해역_아래에_지역을_놓는다(self):
        _, html = self.html(area="ant")
        tree = html[html.index('<ul class="maptree">'):]
        tree = tree[:tree.index('</ul>\n  </div>')]
        sea = tree.index('data-sea="sea:로스해"')
        self.assertLess(sea, tree.index('data-site="RS21"'))
        self.assertLess(tree.index('data-sea="sea:남극반도"'), tree.index('data-site="ZZ99"'))
        self.assertLess(tree.index('data-site="ZZ99"'), sea)

    def test_해역이_없는_권역은_해역_머리가_없다(self):
        _, html = self.html(area="kr")
        heads = tbody_heads(html)
        self.assertFalse([h for h in heads if h[0] == "seagroup"])
        self.assertIn(("ssgroup", "site:BP", None, None), heads)
        self.assertNotIn('class="msea', html)
        self.assertNotIn("해역 미정", html)

    def test_스크립트가_파싱된다(self):
        _, html = self.html(area="ant")
        self.assert_js_parses(html)

    def assert_js_parses(self, html):
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("node 가 없다")
        for src in js_blocks(html):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write(src)
            p = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)


class FirstScreenTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        fx.make_world(slug="rs14", site_code="RS14", loc_code="GC04",
                      sample_code="6cm", depth_cm=6, with_files=False)
        fx.make_world(slug="bp", area="kr", kind="outcrop", site_code="BP",
                      loc_code="BP09", sample_code="0901", with_files=False)

    def test_인자_없이_열면_남극이고_첫_화면_표시가_붙는다(self):
        r = self.client.get(reverse("index"))
        self.assertEqual(r.context["area"]["selected"], "ant")
        html = r.content.decode()
        self.assertIn('data-first="1" data-first-core="RS14-GC04"', html)
        # 고를 코어가 나무에 있다 — 열쇠가 어긋나면 스크립트가 첫 코어로 물러난다
        self.assertIn('data-core="RS14-GC04"', html)

    def test_주소에_값이_있으면_첫_화면이_아니다(self):
        for q in ({"area": "all"}, {"area": "ant"}, {"area": "kr"},
                  {"area": "ant", "hidden": "1"}):
            r = self.client.get(reverse("index"), q)
            self.assertNotIn('data-first="1"', r.content.decode(), q)
        self.assertEqual(self.client.get(reverse("index"), {"area": "all"})
                         .context["area"]["selected"], "all")


class SiteLabelIsCodeTest(DiaRUGATestCase):
    """해역·이름이 채워져 있어도 이름표는 코드다 (사용자 2026-10-30)."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        fx.make_world(slug="rs14", site_code="RS14", loc_code="GC04",
                      sample_code="6cm", depth_cm=6, with_files=False)
        Site.objects.filter(code="RS14").update(region="로스해", name="어느 이름")

    def test_목록_지도_비교_상세_지점_화면이_코드를_쓴다(self):
        self.assertEqual(data.datasets("ant")[0]["site"], "RS14")
        self.assertEqual(data.map_points("ant")[0]["label"], "RS14")
        self.assertEqual(str(Site.objects.get(code="RS14")), "RS14")
        # 지점 화면은 속성 칸에 이름·해역을 그대로 적는다 — 이름표인 머리만 본다
        html = self.client.get(reverse("core", args=["RS14", "GC04"])).content.decode()
        h2 = re.search(r"<h2>GC04 .*?</h2>", html, re.S).group(0)
        self.assertIn("RS14", h2)
        self.assertNotIn("로스해", h2)
        self.assertNotIn("어느 이름", h2)
        for url in (reverse("index") + "?area=ant",
                    reverse("dataset", args=["rs14"]),
                    reverse("compare") + "?s=rs14"):
            html = self.client.get(url).content.decode()
            self.assertNotIn("어느 이름", html, url)
            # 해역은 해역 머리에서만 — 첫 화면 밖에는 안 나온다
            if "?area=" not in url:
                self.assertNotIn(">로스해<", html, url)

    def test_첫_화면의_줄과_머리는_코드를_쓴다(self):
        html = self.client.get(reverse("index"), {"area": "ant"}).content.decode()
        core_cell = re.search(r'<td class="dscore">(.*?)</td>', html, re.S).group(1)
        self.assertIn("RS14", core_cell)
        self.assertNotIn("로스해", core_cell)
        head = re.search(r'<section class="mcorebox"[^>]*>.*?</div>', html, re.S).group(0)
        self.assertIn("RS14", head)
        self.assertNotIn("로스해", head)


class SeaMigrationTest(DiaRUGATestCase):
    """0054 — 빈 칸만 채우고, 되돌릴 때는 자기가 넣은 값만 비운다."""

    def setUp(self):
        self.mig = importlib.import_module("viewer.migrations.0054_site_region_seas")
        Site.objects.create(code="RS14", area="ant")
        Site.objects.create(code="RS21", area="ant", region="사람이 넣은 값")
        Site.objects.create(code="GC03", area="ant", name="Elephant Island")
        Site.objects.create(code="WAP13", area="ant", region="Bigo Bay")

    def region(self, code):
        return Site.objects.get(code=code).region

    def test_빈_칸만_채우고_사람_값은_안_덮는다(self):
        self.mig.fill(django_apps, None)
        self.assertEqual(self.region("RS14"), "로스해")
        self.assertEqual(self.region("GC03"), "남극반도")
        self.assertEqual(self.region("RS21"), "사람이 넣은 값")
        self.assertEqual(self.region("WAP13"), "Bigo Bay")
        self.mig.unfill(django_apps, None)
        self.assertEqual(self.region("RS14"), "")
        self.assertEqual(self.region("RS21"), "사람이 넣은 값")
