"""산출표의 셈 (P34 2·3단계) — 슬라이드 화면 `분류 | 종` 단추.

**여기서 잡는 것은 세는 규칙이 갈라지는 것이다.** 산출표는 비교 화면(202·204)과
같은 SQL(`per_sp`)과 같은 파편 비율 식(`data.count_column`)을 쓴다 — 두 화면이
같은 슬라이드에 다른 수를 내면 보고서에 어느 쪽을 실을지 묻게 된다.

사용자가 정한 것(11-13): **파편은 세지 않는다**(파편에 붙은 종명도) · 분모는
**종명이 붙은 개체** · 파편은 비율 한 줄로만.
"""
import json
import re

from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data, tally


def _done(w):
    for vp in w.viewpoints:
        fx.review_done(vp)


class TallyColumnTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 후보 넷 = round · round_frag · rod · rod_frag (CLASSES 차례)
        cls.w = fx.make_world(slug="a", depth_cm=71.0, n_candidates=4)
        k = cls.w.keys()
        fx.add_review(cls.w.vp, k[0], species="Thalassiosira gracilis")
        fx.add_review(cls.w.vp, k[1], species="Thalassiosira gracilis")   # 파편
        fx.add_review(cls.w.vp, k[2], species="Fragilariopsis curta")
        fx.add_review(cls.w.vp, k[3], species="Fragilariopsis curta")     # 파편
        _done(cls.w)

    def col(self, slug="a"):
        return tally.column(data.dataset_detail(slug))

    def test_파편에_붙은_종명은_안_센다(self):
        c = self.col()
        self.assertEqual(c["per_species"], {"Thalassiosira gracilis": 1,
                                            "Fragilariopsis curta": 1})
        self.assertEqual(c["n_identified"], 2)
        self.assertEqual(c["n_frag"], 2)

    def test_파편_비율이_비교_화면과_같다(self):
        """식을 한 자리에 뒀다(`count_column`). 갈라지면 여기서 잡힌다."""
        c = self.col()
        cmp_col = data.compare_slides(["a"])["cols"][0]
        for k in ("n_counted", "n_frag", "frag_pct", "n_detected"):
            self.assertEqual(c[k], cmp_col[k], k)
        self.assertEqual(c["frag_pct"], 50.0)

    def test_동정률과_종명_없음(self):
        c = self.col()
        self.assertEqual((c["n_counted"], c["n_identified"], c["n_unnamed"]), (2, 2, 0))
        self.assertEqual(c["id_pct"], 100.0)

    def test_검토를_안_마친_시야의_종명은_안_센다(self):
        """산출은 검토를 마친 시야만 센다(P32 ③) — 산출표도 같은 규칙이다."""
        w = fx.make_world(slug="raw", depth_cm=10.0, sample_code="10cm",
                          n_candidates=3)
        fx.add_review(w.vp, w.keys()[2], species="Fragilariopsis curta")
        c = self.col("raw")
        self.assertEqual(c["n_identified"], 0)
        self.assertEqual(c["per_species"], {})

    def test_api_가_여전히_JSON_으로_나간다(self):
        """집계가 `/api/d/<slug>.json` 으로 그대로 나간다 — 튜플 열쇠를 실으면 죽는다."""
        r = self.client.get(reverse("api_dataset", args=["a"]))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertIn({"cls": "rod", "species": "Fragilariopsis curta", "n": 1},
                      body["species_counts"])


class SpeciesBarsTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 분류를 한 바퀴 돌고 round 가 한 번 더 → round 둘 · rod 하나 …
        cls.w = fx.make_world(slug="b", depth_cm=50.0,
                              n_candidates=len(fx.CLASSES) + 1)
        keys = cls.w.keys()
        cls_of = {k: fx.CLASSES[i % len(fx.CLASSES)][0] for i, k in enumerate(keys)}
        rounds = [k for k in keys if cls_of[k] == "round"]
        rod = next(k for k in keys if cls_of[k] == "rod")
        # 같은 종명이 분류 둘에 걸친다 — 종 막대는 하나로 더한다
        for k in rounds:
            fx.add_review(cls.w.vp, k, species="Eucampia antarctica")
        fx.add_review(cls.w.vp, rod, species="Eucampia antarctica")
        _done(cls.w)

    def setUp(self):
        self.html = self.client.get(reverse("dataset", args=["b"])).content.decode()
        self.ctx = data.dataset_detail("b")

    def test_분류_둘에_걸친_종명은_막대_하나다(self):
        bars = self.ctx["species_bars"]
        self.assertEqual([(b["label"], b["n"]) for b in bars],
                         [("Eucampia antarctica", 3)])
        # 색은 가장 많이 붙은 분류(round 둘)의 마스크 색
        self.assertEqual(bars[0]["cls"], "round")
        self.assertEqual(bars[0]["color"], "60,220,120")
        self.assertEqual(bars[0]["share"], 100.0)

    def test_화면에_종_막대가_서버에서_그려진다(self):
        self.assertEqual(len(re.findall(r'<div class="cbar spbar"', self.html)),
                         len(self.ctx["species_bars"]))
        self.assertIn("Eucampia antarctica", self.html)

    def test_종_쪽은_처음에_감춰져_있다(self):
        """처음은 `분류`. 종 칸은 `hidden` 으로 내려간다 — CSS 가 그것을 지는지는
        `.axpane[hidden]` 규칙이 막는다(`.cbars` 의 `display: grid` 가 이긴다)."""
        m = re.search(r'<div class="axpane" data-ax="sp"( hidden)?>', self.html)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), " hidden")
        self.assertIn(".dsstats .axpane[hidden] { display: none; }", self.html)

    def test_종명_없음이_적힌다(self):
        tc = self.ctx["tally_col"]
        self.assertEqual(tc["n_unnamed"], tc["n_counted"] - tc["n_identified"])
        self.assertRegex(self.html, r"종명 없음 <b>%d</b>" % tc["n_unnamed"])


class NoSpeciesTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="c", n_candidates=2)
        _done(cls.w)

    def test_종명이_없으면_안내가_뜬다(self):
        html = self.client.get(reverse("dataset", args=["c"])).content.decode()
        self.assertIn("종명이 붙은 개체가 아직 없습니다", html)
        self.assertNotIn('class="cbar spbar"', html)


class LocalityTableTest(DiaRUGATestCase):
    """지점 산출표 (P34 4단계) — 열은 시료, 줄은 종."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 71 cm 에 관찰 둘 (같은 시료) — 후보 넷 = round · round_frag · rod · rod_frag
        a1 = fx.make_world(slug="a1", depth_cm=71.0, n_candidates=4)
        k = a1.keys()
        fx.add_review(a1.vp, k[0], species="Thalassiosira gracilis")
        fx.add_review(a1.vp, k[2], species="Fragilariopsis curta")
        fx.add_review(a1.vp, k[3], species="Fragilariopsis curta")       # 파편
        a2 = fx.make_world(slug="a2", depth_cm=71.0, n_candidates=4)
        fx.add_review(a2.vp, a2.keys()[2], species="Fragilariopsis curta")
        b = fx.make_world(slug="b", depth_cm=231.0, sample_code="231cm",
                          n_candidates=4)
        fx.add_review(b.vp, b.keys()[0], species="Actinocyclus actinochilus")
        fx.add_review(b.vp, b.keys()[2], species="Actinocyclus ingens")
        # 집계 제외 관찰 — 산출표에서 빠진다
        x = fx.make_world(slug="x", depth_cm=300.0, sample_code="300cm",
                          n_candidates=4)
        fx.add_review(x.vp, x.keys()[0], species="Eucampia antarctica")
        x.slide.exclude_from_totals = True
        x.slide.save()
        for w in (a1, a2, b, x):
            _done(w)

    def t(self, **kw):
        return tally.locality_table("RS23", "GC03", **kw)

    def test_열은_시료이고_관찰은_더한다(self):
        t = self.t()
        self.assertEqual([c["head"] for c in t["cols"]], ["71 cm", "231 cm"])
        self.assertEqual([c["n_obs"] for c in t["cols"]], [2, 1])
        self.assertEqual(t["n_excluded"], 1)

    def test_줄은_속_알파벳순이고_윗줄과_같은_속은_줄인다(self):
        rows = self.t()["rows"]
        self.assertEqual([r["name"] for r in rows],
                         ["Actinocyclus actinochilus", "Actinocyclus ingens",
                          "Fragilariopsis curta", "Thalassiosira gracilis"])
        self.assertEqual([r["short"] for r in rows],
                         ["Actinocyclus actinochilus", "A. ingens",
                          "Fragilariopsis curta", "Thalassiosira gracilis"])

    def test_파편은_안_세고_집계_제외는_빠진다(self):
        t = self.t()
        cur = next(r for r in t["rows"] if r["name"] == "Fragilariopsis curta")
        self.assertEqual([x["n"] for x in cur["cells"]], [2, 0])
        self.assertNotIn("Eucampia antarctica", [r["name"] for r in t["rows"]])

    def test_퍼센트의_분모는_그_열의_종명_붙은_개체다(self):
        t = self.t()
        c71 = t["cols"][0]
        self.assertEqual(c71["n_identified"], 3)
        cur = next(r for r in t["rows"] if r["name"] == "Fragilariopsis curta")
        self.assertEqual(cur["cells"][0]["pct"], 66.7)

    def test_더한_열의_파편_비율은_더한_수에서_다시_낸다(self):
        """비율을 평균하지 않는다 — 관찰 둘의 수를 더해 비교 화면 식으로 낸다."""
        c71 = self.t()["cols"][0]
        a1 = data.compare_slides(["a1"])["cols"][0]
        a2 = data.compare_slides(["a2"])["cols"][0]
        want = round(100.0 * (a1["n_frag"] + a2["n_frag"])
                     / (a1["n_detected"] + a2["n_detected"]), 1)
        self.assertEqual(c71["frag_pct"], want)

    def test_관찰마다_가를_수_있다(self):
        t = self.t(split_obs=True)
        self.assertEqual(len(t["cols"]), 3)
        self.assertEqual([c["slugs"] for c in t["cols"]], [["a1"], ["a2"], ["b"]])

    def test_화면_0은_빈칸이고_관찰_하나인_열만_카탈로그로_간다(self):
        html = self.client.get(reverse("tally", args=["RS23", "GC03"])).content.decode()
        self.assertIn(reverse("catalog", args=["b"]) + "?q=Actinocyclus%20ingens", html)
        # 71 cm 은 관찰 둘을 더한 열 — 어느 관찰로 갈지 고를 근거가 없다
        self.assertNotIn(reverse("catalog", args=["a1"]) + "?q=", html)
        self.assertRegex(html, r'<td class="n"></td>')
        self.assertIn("<i>A. ingens</i>", html)

    def test_CSV_는_줄이지_않고_0도_적는다(self):
        r = self.client.get(reverse("tally", args=["RS23", "GC03"]) + "?format=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        body = r.content.decode("utf-8")
        self.assertTrue(body.startswith("﻿"))
        lines = body.lstrip("﻿").splitlines()
        self.assertEqual(lines[0], "species,71 cm,231 cm,total")
        self.assertIn("Actinocyclus ingens,0,1,1", lines)
        self.assertIn("Fragilariopsis curta,2,0,2", lines)

    def test_지점_화면에서_산출표로_간다(self):
        html = self.client.get(reverse("core", args=["RS23", "GC03"])).content.decode()
        self.assertIn(f'href="{reverse("tally", args=["RS23", "GC03"])}"', html)

    def test_없는_지점은_404(self):
        r = self.client.get(reverse("tally", args=["RS23", "NOPE"]))
        self.assertEqual(r.status_code, 404)


class TallyPlotTest(DiaRUGATestCase):
    """산출 그래프 (P34 5단계)."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 71 cm: round(T. gracilis) · rod(F. curta) · 파편 둘
        a = fx.make_world(slug="a", depth_cm=71.0, n_candidates=4)
        fx.add_review(a.vp, a.keys()[0], species="Thalassiosira gracilis")
        fx.add_review(a.vp, a.keys()[2], species="Fragilariopsis curta")
        # 231 cm: 종명 없음 — 종 패널에 점이 없어야 한다(0 이 아니다)
        b = fx.make_world(slug="b", depth_cm=231.0, sample_code="231cm",
                          n_candidates=4)
        # 369 cm: F. curta 하나
        c = fx.make_world(slug="c", depth_cm=369.0, sample_code="369cm",
                          n_candidates=4)
        fx.add_review(c.vp, c.keys()[2], species="Fragilariopsis curta")
        for w in (a, b, c):
            _done(w)
        cls.loc = a.locality

    def url(self, qs=""):
        return reverse("tally", args=["RS23", "GC03"]) + "?view=plot" + qs

    def panels(self, html):
        import xml.etree.ElementTree as ET
        m = re.search(r"<svg [^>]*font-family=.*?</svg>", html, re.S)   # 머리줄 아이콘 svg 를 피한다
        self.assertIsNotNone(m)
        root = ET.fromstring(m.group(0))        # **파싱해서 본다** — 문자열이 있다 ≠ 그려진다
        ns = "{http://www.w3.org/2000/svg}"
        return [(g.get("data-kind"), len(g.findall(f"{ns}path[@class='pt']")),
                 "".join(t.text or "" for t in g.findall(f"{ns}text")[:2]))
                for g in root.findall(f"{ns}g")]

    def test_분모가_종은_종명_분류는_세는_개체다(self):
        t = tally.locality_table("RS23", "GC03")
        sp = tally.taxon_values(t["cols"], "Fragilariopsis curta")
        self.assertEqual(sp, [50.0, None, 100.0])          # 231 은 분모 없음
        crs = tally.taxon_values(t["cols"], "cls:rod")
        self.assertEqual(crs, [50.0, 50.0, 50.0])          # 세는 개체 둘 중 rod 하나

    def test_고른_것이_없으면_전역_기본(self):
        ps = self.panels(self.client.get(self.url()).content.decode())
        self.assertEqual(len(ps), len(tally.DEFAULT_TAXA) + 2)
        # 기본 여섯의 끝이 CRS — 이름은 `ClassDef.short` 다(운영은 `CRS`, 시험
        # 자료는 다른 약칭이라 글자를 박지 않고 그 칸에서 읽는다)
        want = tally.taxon_label("cls:chaetoceros")["name"]
        self.assertTrue(ps[-3][2].startswith(want), ps[-3])

    def test_점은_분모가_있는_시료에만(self):
        ps = self.panels(self.client.get(
            self.url("&pick=1&sp=Fragilariopsis+curta")).content.decode())
        self.assertEqual(len(ps), 3)                       # 종 하나 + 동정률 + 시야당
        self.assertEqual(ps[0][1], 2)                      # 71 · 369 — 231 은 없다
        self.assertEqual(ps[1][1], 3)                      # 동정률은 세 시료 다

    def test_pick_만_있고_종이_없으면_다_끈_것이다(self):
        ps = self.panels(self.client.get(self.url("&pick=1")).content.decode())
        self.assertEqual(len(ps), 2)

    def test_차례는_주소가_아니라_목록의_차례다(self):
        a = self.client.get(self.url("&pick=1&sp=Thalassiosira+gracilis&sp=Fragilariopsis+curta")).content
        b = self.client.get(self.url("&pick=1&sp=Fragilariopsis+curta&sp=Thalassiosira+gracilis")).content
        self.assertEqual(self.panels(a.decode()), self.panels(b.decode()))

    def test_설정과_지점_목록이_기본을_바꾼다(self):
        from ..models import Setting
        Setting.objects.create(key=tally.SETTING_KEY, value=["Fragilariopsis curta"])
        self.assertEqual(len(self.panels(self.client.get(self.url()).content.decode())), 3)
        self.loc.tally_taxa = ["Thalassiosira gracilis", "cls:rod"]
        self.loc.save()
        self.assertEqual(len(self.panels(self.client.get(self.url()).content.decode())), 4)

    def test_저장은_POST_로만_하고_비우면_전역으로(self):
        save = reverse("tally_taxa_save", args=["RS23", "GC03"])
        self.assertEqual(self.client.get(save).status_code, 405)
        r = self.client.post(save, {"sp": ["Fragilariopsis curta", "cls:rod", "cls:rod"]})
        self.assertEqual(r.status_code, 302)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.tally_taxa, ["Fragilariopsis curta", "cls:rod"])
        self.client.post(save, {"reset": "1"})
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.tally_taxa, [])

    def test_SVG_내려받기(self):
        r = self.client.get(self.url("&pick=1&sp=Fragilariopsis+curta&format=svg"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("image/svg+xml"))
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(r.content.startswith(b"<svg "))

    def test_코어_자료를_같은_축에_얹는다(self):
        from ..models import CorePoint, CoreSeries
        cs = CoreSeries.objects.create(locality=self.loc, key="opal", label="Opal", unit="%")
        for mm, v in ((0, 10.0), (2000, 20.0), (4000, 15.0)):
            CorePoint.objects.create(series=cs, depth_mm=mm, value=v)
        ps = self.panels(self.client.get(
            self.url("&pick=1&series=opal&series=nope")).content.decode())
        self.assertEqual([k for k, _, _ in ps], ["core", "pct", "pct"])


class TallyOutcropPlotTest(DiaRUGATestCase):
    """노두는 cm 축을 안 그린다 — 시료 차례를 같은 간격으로."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        for no, slug in ((1, "o1"), (2, "o2")):
            w = fx.make_world(slug=slug, kind="outcrop", area="kr", site_code="BP",
                              loc_code="BP09", sample_code=f"090{no}", n_candidates=3)
            fx.add_review(w.vp, w.keys()[2], species="Paralia sulcata")
            _done(w)

    def test_축이_시료_차례다(self):
        html = self.client.get(reverse("tally", args=["BP", "BP09"])
                               + "?view=plot&pick=1&sp=Paralia+sulcata").content.decode()
        self.assertIn("시료 차례", html)
        self.assertNotIn("깊이 (cm)", html)
        self.assertNotIn("코어 자료 (같은 깊이 축)", html)
