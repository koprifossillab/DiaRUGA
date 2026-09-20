"""생층서 기준면 층 — P28.

전부 되살려서 잡히는 것을 봤다(어느 줄을 빼면 죽는지는 시험마다 적었다).

1. **재인용 겹침은 기본으로 안 그린다** — 원문 행과 값이 같은 것만.
   값이 다른 재인용과 원문이 없는 재인용은 남는다 (`_dedupe_via`)
2. **Cody 두 모델은 기본 평균만** · `both` 면 둘 다
3. **권역이 비면 아무것도 안 그린다** — 조용히 전체를 내지 않는다
4. **카드의 「기준면」 줄은 정확 일치이고 없으면 안 낸다**
5. **속 목록에 `기준면 N` 이 붙는다**
6. **저장소의 JSON 이 그대로 들어온다** (반입기 · 어휘 · 검산)
7. **`check_db` 13번이 가리키는 자리가 성립한다**
8. **배치** — 하한만 있는 대는 위 대의 하한이 상한 · MIS 눈금은 1.5 Ma 이하만
9. **파서의 이름 정규화** — 종소명 소문자 · `var.` 유지 · 비공식 이름은 이명법 없음
10. **학명 판정이 그림의 표에 붙는다** — 이명·없음만, 종마다 한 번
    (`taxon_names.json` 의 기준면 85 이름 답 · 09-18 저녁)
11. **210** — 속 여럿 · 종 숨기기(숨긴 것도 목록에 남는다) · 슬라이드의 종만
    (이명법 꼴만 맞추고 못 맞춘 표기는 말한다) · 점의 문헌 링크(쪽은 `#page=`)
12. **210 · 세로축 창** — 창 밖의 점은 안 그리고 막대는 잘려 열린다 · 창에
    안 걸치는 종은 열이 없다 · `MIS 5`–`MIS 11` 같은 이름도 읽는다 · 뒤집힌
    범위는 바로 세운다 · 눈금 간격은 창의 폭이 정한다
13. **210 · 오른쪽 여백** — 마지막 열의 기울인 이름이 뷰박스 안에 든다
    (`RIGHT_PAD` 를 0 으로 하면 죽는다)
14. **210 · `supersedes`** — 뒤 파일이 앞 파일의 출처를 대신하면 앞 행이 빠진다
"""
import importlib.util
import json
import sys
from pathlib import Path

from . import factories as fx
from .base import DiaRUGATestCase
from .. import biodatum as bd, data, mis
from ..models import (Atlas, AtlasEntry, Biodatum, Biozone, DiatomObject, Reference,
                      TaxonName)

_ROOT = Path(__file__).resolve().parents[3]


def _load(name, sub="ops"):
    path = _ROOT / sub / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def ref(key, year=2008, authors="Cody et al."):
    return Reference.objects.create(key=key, authors=authors, year=year, kind="paper",
                                    url=f"https://doi.org/10.1/{key}")


_SEQ = {}


def datum(ref_, name, kind, age, lo=None, hi=None, **kw):
    _SEQ[ref_.key] = _SEQ.get(ref_.key, 0) + 1
    words = name.split()
    row = dict(reference=ref_, seq=_SEQ[ref_.key], name=name, name_printed=name,
               binomial=" ".join(words[:2]) if len(words) >= 2 else "",
               genus=words[0], infra=" ".join(words[2:]),
               datum=kind, age=age, age_min=lo if lo is not None else age,
               age_max=hi if hi is not None else age, age_text=str(age),
               confidence="high")
    row.update(kw)
    return Biodatum.objects.create(**row)


class BiodatumChartTests(DiaRUGATestCase):
    def setUp(self):
        _SEQ.clear()
        self.cody = ref("cody2008")
        self.warnock = ref("warnock2025", 2025, "Warnock et al.")
        self.crampton = ref("crampton2016", 2016, "Crampton et al.")
        self.yan = ref("yanagisawa1998", 1998, "Yanagisawa & Akiba")
        # Cody 원문 — 두 모델
        datum(self.cody, "Rouxia antarctica", "LO", 1.495, 1.48, 1.51, variant="average")
        datum(self.cody, "Rouxia antarctica", "LO", 1.345, 1.26, 1.43, variant="total")
        datum(self.cody, "Rouxia antarctica", "FO", 4.5, 4.43, 4.57, variant="average")
        # Warnock Table 2 경유 재인용 — 값이 같은 것 하나, 다른 것 하나
        datum(self.cody, "Rouxia antarctica", "LO", 1.495, 1.48, 1.51, variant="average",
              via="warnock2025", confidence="recite")
        datum(self.cody, "Rouxia constricta", "LO", 0.24, 0.24, 0.24, variant="average",
              via="warnock2025", confidence="recite", note="원문은 0.43–0.5")
        # 원문이 없는 재인용 (Crampton 은 전부 경유)
        datum(self.crampton, "Rouxia antarctica", "LO", 1.31, variant="composite",
              via="warnock2025", confidence="recite")
        datum(self.warnock, "Rouxia antarctica", "LO", 1.637, uncertainty=0.004)
        # 북서태평양
        datum(self.yan, "Rouxia californica", "LCO", 6.57, code="#D 70", primary=True)
        a = Atlas.objects.create(key="east-antarctic", title="동남극", short="동남극")
        AtlasEntry.objects.create(atlas=a, seq=1, name="Rouxia antarctica", genus="Rouxia",
                                  binomial="Rouxia antarctica")

    def test_재인용_겹침은_기본으로_뺀다(self):
        got = data.biodatum_chart(areas=["antarctic"], genus="Rouxia")
        pts = [p for s in got["species"] for p in s["points"]]
        # 값이 같은 재인용(1.495 경유) 하나만 빠진다 — `_dedupe_via` 의 `direct` 집합을
        # 비우면 이 시험이 죽는다
        self.assertEqual(got["n_hidden_via"], 1)
        via = [p for p in pts if p["via"]]
        self.assertEqual({(p["name"], p["age"]) for p in via},
                         {("Rouxia constricta", 0.24), ("Rouxia antarctica", 1.31)})
        # 경유 문헌이 참고문헌에 남는다
        self.assertIn("warnock2025", {r["key"] for r in got["references"]})
        self.assertTrue(all(p["via_label"] for p in via))

    def test_재인용_겹침도_켜면_다_그린다(self):
        got = data.biodatum_chart(areas=["antarctic"], genus="Rouxia", include_via=True)
        self.assertEqual(got["n_hidden_via"], 0)
        self.assertEqual(sum(1 for s in got["species"] for p in s["points"] if p["via"]), 3)

    def test_Cody_모델은_기본_평균만(self):
        got = data.biodatum_chart(areas=["antarctic"], genus="Rouxia")
        variants = {p["variant"] for s in got["species"] for p in s["points"]}
        self.assertNotIn("total", variants)
        got = data.biodatum_chart(areas=["antarctic"], genus="Rouxia", model="total")
        variants = {p["variant"] for s in got["species"] for p in s["points"]}
        self.assertIn("total", variants)
        self.assertNotIn("average", variants)
        got = data.biodatum_chart(areas=["antarctic"], genus="Rouxia", model="both")
        variants = {p["variant"] for s in got["species"] for p in s["points"]}
        self.assertTrue({"total", "average"} <= variants)

    def test_권역이_비면_아무것도_안_그린다(self):
        got = data.biodatum_chart(areas=[], genus="Rouxia")
        self.assertEqual(got["species"], [])
        got = data.biodatum_chart(areas=["npacific"], genus="Rouxia")
        self.assertEqual([s["name"] for s in got["species"]], ["Rouxia californica"])
        both = data.biodatum_chart(areas=["antarctic", "npacific"], genus="Rouxia")
        self.assertEqual(both["n_species"], 3)
        # 바탕띠의 체계도 권역을 따른다
        Biozone.objects.create(scheme="npd", seq=1, name="NPD 12", base_ma=0.31)
        Biozone.objects.create(scheme="warnock2025", seq=1, name="T. lentiginosa Partial Range Zone",
                               top_ma=0, base_ma=0.527)
        self.assertEqual({z["scheme"] for z in data.biodatum_chart(areas=["npacific"], genus="Rouxia")["zones"]},
                         {"npd"})

    def test_도감에_없는_종을_말한다(self):
        got = data.biodatum_chart(areas=["antarctic", "npacific"], genus="Rouxia")
        by = {s["name"]: s["in_atlas"] for s in got["species"]}
        self.assertTrue(by["Rouxia antarctica"])
        self.assertFalse(by["Rouxia californica"])

    def test_학명_판정이_표에_붙는다(self):
        # `data.biodatum_chart` 의 `taxa = _taxon_names_by_binomial(...)` 을 빼면
        # `taxon` 이 None 이 되어 이명 칩이 안 뜬다
        TaxonName.objects.create(binomial="Rouxia antarctica", status="synonym",
                                 valid_name="Rouxia peragalloi var. antarctica",
                                 note="갱신 2015")
        TaxonName.objects.create(binomial="Rouxia californica", status="accepted")
        TaxonName.objects.create(binomial="Rouxia constricta", status="absent",
                                 note="AlgaeBase 에 없음")
        got = data.biodatum_chart(areas=["antarctic", "npacific"], genus="Rouxia")
        by = {s["name"]: s["taxon"] for s in got["species"]}
        self.assertEqual(by["Rouxia antarctica"]["valid_name"], "Rouxia peragalloi var. antarctica")
        self.assertIsNone(by["Rouxia californica"])  # 유효는 낼 것이 없다
        self.assertEqual(by["Rouxia constricta"]["status"], "absent")
        body = self.client.get("/atlas/datums/?area=antarctic&area=npacific&genus=Rouxia&f=1").content.decode()
        self.assertIn(">이명</span> <i class=\"dim\">Rouxia peragalloi var. antarctica</i>", body)
        self.assertIn("AlgaeBase 에 없다", body)

    def test_화면이_그린다(self):
        r = self.client.get("/atlas/datums/?area=antarctic&genus=Rouxia&f=1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('class="bd-ptg"', body)
        self.assertIn("재인용 겹침 1건 숨김", body)
        self.assertIn("Rouxia constricta", body)
        # 표에 경유 문헌이 적힌다
        self.assertIn("Warnock et al. (2025)</span>", body.replace(" 경유", ""))
        # 권역을 다 끄면 말한다
        r = self.client.get("/atlas/datums/?genus=Rouxia&f=1")
        self.assertIn("권역을 하나도 안 골랐습니다", r.content.decode())
        # 폼이 아닌 링크(f 없음)로 오면 둘 다 켠다
        r = self.client.get("/atlas/datums/?q=californica")
        self.assertIn("Rouxia californica", r.content.decode())
        # 속·검색어 없이는 결과가 없다
        r = self.client.get("/atlas/datums/")
        self.assertNotIn('class="bd-ptg"', r.content.decode())

    def test_카드의_기준면_줄은_정확_일치이고_없으면_안_낸다(self):
        got = data.atlas_search(q="Rouxia")
        rows = {r["binomial"]: r for r in got["rows"]}
        self.assertTrue(rows["Rouxia antarctica"]["biodatums"])
        # 카드는 평균만 · 값 같은 재인용은 뺀다
        ages = [(b["datum"], b["age"]) for b in rows["Rouxia antarctica"]["biodatums"]]
        self.assertNotIn(("LO", 1.345), ages)
        self.assertEqual(ages.count(("LO", 1.495)), 1)
        a = Atlas.objects.get(key="east-antarctic")
        AtlasEntry.objects.create(atlas=a, seq=2, name="Rouxia peragalli", genus="Rouxia",
                                  binomial="Rouxia peragalli")
        got = data.atlas_search(q="Rouxia peragalli")
        self.assertEqual(got["rows"][0]["biodatums"], [])
        r = self.client.get("/atlas/?q=Rouxia+peragalli")
        self.assertNotIn("entryextra biodatums", r.content.decode())
        r = self.client.get("/atlas/?q=Rouxia+antarctica")
        self.assertIn("entryextra biodatums", r.content.decode())

    def test_속_목록에_기준면_수가_붙는다(self):
        rows = {g["genus"]: g for g in data.atlas_genera()}
        self.assertEqual(rows["Rouxia"]["nd"], Biodatum.objects.filter(genus="Rouxia").count())
        r = self.client.get("/atlas/")
        self.assertIn("· 기준면 ", r.content.decode())
        # 기준면 쪽 속 목록은 도감에 없는 속을 그렇게 말한다
        datum(self.cody, "Alveus marinus", "FO", 10.0)
        g = {x["genus"]: x for x in data.biodatum_genera(["antarctic"])}
        self.assertFalse(g["Alveus"]["in_atlas"])
        self.assertTrue(g["Rouxia"]["in_atlas"])


    def test_속_여럿과_종_숨기기(self):
        """210. `genus` 목록 → 두 속이 한 그림에. `hide` 는 열만 빼고 목록에는
        남는다 — `all_species` 에서 숨긴 것을 빼면 다시 켤 체크박스가 없다."""
        datum(self.cody, "Thalassiosira kolbei", "LO", 1.9, variant="average")
        got = data.biodatum_chart(areas=["antarctic"], genus=["Rouxia", "thalassiosira"])
        names = [s["name"] for s in got["species"]]
        self.assertIn("Thalassiosira kolbei", names)
        self.assertIn("Rouxia antarctica", names)
        got = data.biodatum_chart(areas=["antarctic"], genus=["Rouxia", "Thalassiosira"],
                                  hide=["Rouxia antarctica", "없는 이름"])
        self.assertNotIn("Rouxia antarctica", [s["name"] for s in got["species"]])
        self.assertEqual(got["n_hidden"], 1)
        self.assertEqual([x["name"] for x in got["all_species"] if x["hidden"]],
                         ["Rouxia antarctica"])
        # 화면 — 체크박스 둘 다 있고, 숨긴 것은 꺼진 채 `hide` 를 나른다
        body = self.client.get("/atlas/datums/?area=antarctic&genus=Rouxia&genus=Thalassiosira"
                               "&hide=Rouxia+antarctica&f=1").content.decode()
        self.assertIn('name="genus" value="Rouxia" form="bdq"', body)
        self.assertIn('<input type="hidden" name="hide" value="Rouxia antarctica" form="bdq">', body)
        self.assertIn("종 1 숨김", body)
        self.assertNotIn("Rouxia antarctica</i>{% if", body)

    def test_슬라이드의_종만(self):
        """210. 슬라이드에서 사람이 적은 종명(`DiatomObject.species`)의 이명법만
        남긴다. `sp.`·명명자 붙은 것은 못 맞춘 표기로 말한다."""
        w = fx.make_world(slug="rs23-bd", site_code="RSBD")
        DiatomObject.objects.create(viewpoint=w.vp, species="Rouxia antarctica Heiden")
        DiatomObject.objects.create(viewpoint=w.vp, species="Rouxia antarctica")
        DiatomObject.objects.create(viewpoint=w.vp, species="Thalassiosira sp.")
        got = data.biodatum_slide_species("rs23-bd")
        self.assertEqual(got["binomials"], {"Rouxia antarctica"})
        self.assertEqual(got["unmatched"], ["Thalassiosira sp."])
        chart = data.biodatum_chart(areas=["antarctic", "npacific"], binomials=got["binomials"])
        self.assertEqual([s["name"] for s in chart["species"]], ["Rouxia antarctica"])
        # 빈 집합은 "아무것도 없다" 다 — 전체를 내면 안 된다
        self.assertEqual(data.biodatum_chart(areas=["antarctic"], binomials=set())["species"], [])
        body = self.client.get("/atlas/datums/?slide=rs23-bd").content.decode()
        self.assertIn("이명법으로 맞춘 것 1", body)
        self.assertIn("<i>Thalassiosira sp.</i>", body)
        self.assertIn("Rouxia antarctica", body)
        self.assertNotIn("Rouxia californica", body)
        self.assertIn("그런 슬라이드가 없습니다",
                      self.client.get("/atlas/datums/?slide=nope").content.decode())

    def test_점이_문헌의_쪽을_연다(self):
        """210. 쪽을 아는 행은 `url#page=N`, 모르는 행은 문헌 주소, 주소가 없으면
        링크가 없다."""
        datum(self.cody, "Rouxia peragalloi", "FO", 3.0, page=12)
        nourl = Reference.objects.create(key="kato2024", authors="Kato", year=2024)
        datum(nourl, "Rouxia peragalloi", "LO", 1.0)
        got = data.biodatum_chart(areas=["antarctic"], q="peragalloi")
        links = {(p["ref"], p["datum"]): p["link"] for s in got["species"] for p in s["points"]}
        self.assertEqual(links[("cody2008", "FO")], "https://doi.org/10.1/cody2008#page=12")
        self.assertEqual(links[("kato2024", "LO")], "")
        body = self.client.get("/atlas/datums/?q=peragalloi").content.decode()
        self.assertIn('<a href="https://doi.org/10.1/cody2008#page=12" target="_blank"', body)
        self.assertIn("누르면 문헌 p.12 을 연다", body)

    def test_축_창을_화면에서_고른다(self):
        """210. `from`·`to` 가 창이 되고, 왼쪽 기둥의 띠가 그 범위로 가는 링크다."""
        body = self.client.get("/atlas/datums/?area=antarctic&genus=Rouxia&f=1"
                               "&from=MIS+5&to=MIS+11").content.decode()
        self.assertIn("축 0.071–0.424 Ma", body)
        # 창 밖의 점(1.495 · 4.5 — 막대 1.26–4.57 도 창에 안 걸친다)은 표에 없고,
        # 안의 점(0.24)은 있다. 종 체크박스 목록에는 둘 다 남는다(창은 보기다)
        self.assertIn("<td><i>Rouxia constricta</i>", body)
        self.assertNotIn("<td><i>Rouxia antarctica</i>", body)
        self.assertIn("<i>Rouxia antarctica</i></label>", body)
        self.assertIn("&amp;from=", body)
        self.assertIn(">전체</a>", body)
        # 띠 링크는 지금 거르개를 그대로 든다
        self.assertRegex(body, r'href="/atlas/datums/\?[^"]*genus=Rouxia[^"]*&amp;from=0\.0?&amp;to=')


class LayoutTests(DiaRUGATestCase):
    def test_하한만_있는_대는_위_대의_하한이_상한이다(self):
        zones = [
            {"scheme": "npd", "seq": 1, "name": "NPD 12", "top_ma": None, "base_ma": 0.31,
             "top_def": "", "base_def": "", "author": ""},
            {"scheme": "npd", "seq": 2, "name": "NPD 11", "top_ma": None, "base_ma": 1.1,
             "top_def": "", "base_def": "", "author": ""},
        ]
        L = bd.layout([], zones, y_max=2.0)
        bands = {b["name"]: b for b in L["bands"]}
        self.assertEqual(bands["NPD 12"]["y1"], L["top"])
        self.assertEqual(bands["NPD 11"]["y1"], bands["NPD 12"]["y2"])
        self.assertTrue(bands["NPD 12"]["open_top"])
        self.assertFalse(bands["NPD 11"]["open_top"])
        self.assertGreater(bands["NPD 11"]["h"], 0)

    def test_MIS_눈금은_짧은_축에만(self):
        self.assertTrue(bd.layout([], [], y_max=1.0)["mis_ticks"])
        self.assertEqual(bd.layout([], [], y_max=5.0)["mis_ticks"], [])

    def test_막대는_젊은_LO_에서_오래된_FO_까지(self):
        sp = [{"name": "Aaaa b", "binomial": "Aaaa b", "genus": "Aaaa", "infra": "", "in_atlas": True,
               "points": [{"datum": "LO", "age": 1.0, "age_min": 0.9, "age_max": 1.1},
                          {"datum": "LO", "age": 1.5, "age_min": 1.5, "age_max": 1.5},
                          {"datum": "FO", "age": 4.0, "age_min": 3.9, "age_max": 4.2}]}]
        L = bd.layout(sp, [], y_max=5.0)
        col = L["cols"][0]
        self.assertEqual(col["bar"]["y1"], col["points"][0]["y1"])   # 0.9
        self.assertEqual(col["bar"]["y2"], col["points"][2]["y2"])   # 4.2
        self.assertFalse(col["bar"]["open_top"] or col["bar"]["open_base"])
        sp[0]["points"] = sp[0]["points"][:2]
        self.assertTrue(bd.layout(sp, [], y_max=5.0)["cols"][0]["bar"]["open_base"])
        self.assertEqual(col["label"], "A. b")

    def test_창_밖은_안_그리고_막대는_잘려_열린다(self):
        """210. 12번. 창(1–3 Ma)에 LO(0.9–1.1)는 걸치고 FO(4.0)는 안 걸친다 —
        점은 하나, 막대는 아래가 잘려 열린다. 창(5–6)에는 아무것도 없다."""
        sp = [{"name": "Aaaa b", "binomial": "Aaaa b", "genus": "Aaaa", "infra": "", "in_atlas": True,
               "points": [{"datum": "LO", "age": 1.0, "age_min": 0.9, "age_max": 1.1},
                          {"datum": "FO", "age": 4.0, "age_min": 3.9, "age_max": 4.2}]}]
        L = bd.layout(sp, [], y_max=3.0, y_min=1.0)
        col = L["cols"][0]
        self.assertEqual([p["datum"] for p in col["points"]], ["LO"])
        self.assertEqual(col["points"][0]["y1"], L["top"])          # 0.9 는 창 위에서 잘린다
        self.assertTrue(col["bar"]["open_base"])
        self.assertTrue(col["bar"]["open_top"])      # 막대 위끝 0.9 도 창 위라 잘렸다
        self.assertEqual(col["bar"]["y2"], L["axis_bottom"])
        self.assertFalse(bd.layout(sp, [], y_max=3.0, y_min=0.5)["cols"][0]["bar"]["open_top"])
        self.assertEqual((L["n_species"], L["n_points"]), (1, 1))
        self.assertEqual(L["ticks"][0]["ma"], 1.0)
        self.assertEqual(L["ticks"][1]["ma"], 1.25)
        self.assertEqual(bd.layout(sp, [], y_max=6.0, y_min=5.0)["cols"], [])
        # 기·세·절·MIS 띠도 창 위쪽 것은 없다
        L = bd.layout([], [], y_max=0.8, y_min=0.4)
        self.assertTrue(all(b["base_ma"] > 0.4 for b in L["gts_bands"]))
        self.assertTrue(all(b["base_ma"] > 0.4 for b in L["mis_bands"]))
        self.assertAlmostEqual(L["ticks"][1]["ma"] - L["ticks"][0]["ma"], 0.05)
        # 좁힌 창은 눈금이 촘촘하고 종결면·MIS 경계선이 창 안의 것만이다
        self.assertTrue(all(0.4 <= t["ma"] <= 0.8 for t in L["mis_ticks"]))

    def test_창_읽기(self):
        self.assertEqual(bd.window("MIS 5", "MIS 11"), (0.071, 0.424))
        self.assertEqual(bd.window("3", "1"), (1.0, 3.0))       # 뒤집힌 것은 바로 세운다
        self.assertEqual(bd.window("", "2"), (None, 2.0))
        self.assertEqual(bd.window("모름", ""), (None, None))
        self.assertEqual(bd.window("2", "2"), (2.0, 2.01))      # 폭 0 은 안 된다
        self.assertEqual(mis.stage_span("G2"), (2.638, 2.652))
        self.assertIsNone(mis.stage_span("MIS 999"))

    def test_마지막_열의_이름이_잘리지_않는다(self):
        """210. 13번. 뷰박스 오른쪽이 마지막 열 + 기울인 이름의 가로 길이
        이상이어야 한다. `RIGHT_PAD` 를 0 으로 되돌리면 죽는다."""
        import math
        sp = [{"name": f"Aaaa b{i}", "binomial": "", "genus": "Aaaa", "infra": "", "in_atlas": True,
               "points": [{"datum": "LO", "age": 1.0, "age_min": 1.0, "age_max": 1.0}]}
              for i in range(3)]
        L = bd.layout(sp, [], y_max=2.0)
        overhang = bd.LABEL_H / math.tan(math.radians(L["label_deg"]))
        self.assertGreaterEqual(L["width"], L["cols"][-1]["x"] + overhang)
        self.assertLess(L["x_right"], L["width"])

    def test_MIS_단계(self):
        self.assertEqual(mis.stage_of(0.121), "5")
        self.assertEqual(mis.stage_of(0.135), "6")
        self.assertEqual(mis.stage_of(2.62), "G1")
        self.assertEqual(mis.stage_of(9.0), "")


class ParserTests(DiaRUGATestCase):
    def setUp(self):
        self.mod = _load("parse_biodatums", "tools")

    def test_이름_정규화(self):
        sn = self.mod.split_name
        self.assertEqual(sn("Rouxia Antarctica"), ("Rouxia antarctica", "Rouxia antarctica", "Rouxia", ""))
        self.assertEqual(sn("–Crucidenticula nicobarica")[0], "Crucidenticula nicobarica")
        self.assertEqual(sn("Denticulopsis prae dimorpha")[0], "Denticulopsis praedimorpha")
        name, binom, genus, infra = sn("Actinocyclus ingens var. ovalis")
        self.assertEqual((name, binom, infra), ("Actinocyclus ingens var. ovalis", "Actinocyclus ingens", "var. ovalis"))
        # 비공식 이름 — 사건은 유효하지만 맞출 종이 없다
        name, binom, genus, infra = sn("Actinocyclus F Zielinski and Gersonde 2003")
        self.assertEqual((binom, genus), ("", "Actinocyclus"))
        self.assertEqual(name, "Actinocyclus F Zielinski and Gersonde 2003")
        self.assertEqual(sn("Nitzschia 17 Schrader 1976")[1], "")
        # 도감과 같은 속명 고침
        self.assertEqual(sn("Chaetoceras bulbosum")[1], "Chaetoceros bulbosum")

    def test_note_에서_칸으로_올린다(self):
        v, via, primary, rest = self.mod.lift_note(
            "Average Range Model · 기록 18 (10) · 평균 misfit 1.11 · 주요 지시종(+)", "")
        self.assertEqual((v, via, primary, rest), ("average", "", True, "기록 18 (10) · 평균 misfit 1.11"))
        v, via, primary, rest = self.mod.lift_note("Average Range Model · Warnock et al. (2025) Table 2 경유", "")
        self.assertEqual((v, via, rest), ("average", "warnock2025", ""))
        v, *_ = self.mod.lift_note("SSODZ 대 하한 정의로부터 환산", "SSODZ")
        self.assertEqual(v, "SSODZ")
        with self.assertRaises(SystemExit):
            self.mod.lift_note("Warnock et al. (2025) 부록 경유", "")

    def test_MERGE_OK_밖의_합침은_멈춘다(self):
        doc = {"sources": {"cody2008": {"label": "Cody et al. (2008)"}},
               "rows": [self._row("Rouxia Antarctica"), self._row("Rouxia antarctica"),
                        self._row("Thalassiosira Kolbei"), self._row("Thalassiosira kolbei")]}
        with self.assertRaises(SystemExit):
            self.mod.convert(doc)
        doc["rows"] = doc["rows"][:2]
        refs, datums, merged = self.mod.convert(doc)
        self.assertEqual(len(datums), 2)
        self.assertEqual({d["name"] for d in datums}, {"Rouxia antarctica"})

    def test_어휘_밖이면_멈춘다(self):
        doc = {"sources": {"cody2008": {"label": "Cody et al. (2008)"}},
               "rows": [self._row("Rouxia antarctica", datum="FOO")]}
        with self.assertRaises(SystemExit):
            self.mod.convert(doc)
        doc["rows"] = [self._row("Rouxia antarctica", age=2.0, age_min=0.5, age_max=1.0)]
        with self.assertRaises(SystemExit):
            self.mod.convert(doc)

    @staticmethod
    def _row(species, **kw):
        r = {"source": "cody2008", "species": species, "species_printed": species,
             "datum": "LO", "age": 1.0, "age_min": 1.0, "age_max": 1.0, "uncertainty": "",
             "age_text": "1.0", "confidence": "높음(원문 대조)", "note": "", "code": ""}
        r.update(kw)
        return r


    def test_supersedes_가_앞_파일의_출처를_뺀다(self):
        """210. 14번. 뒤 파일이 같은 출처키를 `supersedes` 로 들면 앞 파일의
        그 행·출처는 빠지고 `seq` 도 안 센다. 앞에 없는 키면 멈춘다."""
        m = self.mod
        row = lambda src, sp: {"source": src, "species": sp, "species_printed": sp, "datum": "FO",
                               "age": 1.0, "age_min": 1.0, "age_max": 1.0, "age_text": "1.0",
                               "confidence": "높음(원문 대조)", "note": ""}
        src = lambda key: {key: {"label": f"{key.title()} (2002)"}}
        first = {"sources": {**src("aaa"), **src("bbb")},
                 "rows": [row("aaa", "Rouxia antarctica"), row("bbb", "Rouxia antarctica")]}
        second = {"sources": src("bbb"), "supersedes": ["bbb"],
                  "rows": [row("bbb", "Rouxia constricta"), row("bbb", "Rouxia peragalloi")]}
        dropped = m.superseded([first, second])
        self.assertEqual(dropped, {"bbb": 1})
        seq, merged, refs, datums = {}, {}, [], []
        for i, doc in enumerate([first, second]):
            skip = {k for k, j in dropped.items() if j > i}
            r, d, merged = m.convert(doc, seq, merged, skip)
            refs += r
            datums += d
        self.assertEqual([r["key"] for r in refs], ["aaa", "bbb"])
        self.assertEqual([(d["reference"], d["seq"], d["name"]) for d in datums],
                         [("aaa", 1, "Rouxia antarctica"), ("bbb", 1, "Rouxia constricta"),
                          ("bbb", 2, "Rouxia peragalloi")])
        with self.assertRaises(SystemExit):
            m.superseded([first, {"sources": src("ccc"), "supersedes": ["ccc"], "rows": []}])
        with self.assertRaises(SystemExit):
            m.superseded([first, {"sources": src("zzz"), "supersedes": ["bbb"], "rows": []}])


class TaxonNamesAnswerTests(DiaRUGATestCase):
    """기준면 85 이름의 AlgaeBase 답(마크다운 표)을 `parse_taxon_names` 가 읽는다."""

    def setUp(self):
        self.mod = _load("parse_taxon_names", "tools")

    def test_마크다운_표를_읽는다(self):
        md = (
            "| # | 이름 | AlgaeBase 현재 통용명 | 비고 |\n|---|---|---|---|\n"
            "| 1 | *Actinocyclus F Zielinski and Gersonde 2003* | AlgaeBase에 없음 | 비공식 |\n"
            "| 2 | *Azpeitia nodulifer* | **Azpeitia nodulifera** | 갱신 2018 · 교정 |\n"
            "| 3 | *Fragilariopsis matuyamae* | (그대로 유효) | 갱신 2026 |\n"
            "| 4 | *Fragilariopsis matuyamae heteropola* | (그대로 유효) | 갱신 2026 · 열쇠 |\n"
            "| 5 | *Thalassiosira kolbei* | 확인 필요 | 갱신 2004 |\n"
            "| 6 | *Nitzschia 17 Schrader 1976* | AlgaeBase에 없음 | 비공식 |\n"
            "| 7 | *Thalassiosira jacksonii* | AlgaeBase에 없음 |  |\n"
        )
        path = self._tmp / "answered.md"
        path.write_text(md, encoding="utf-8")
        got = self.mod.from_answered_md(path, "t")
        # 비공식 둘은 열쇠가 없다 — `Actinocyclus f` 같은 열쇠를 만들지 않는다
        self.assertEqual(set(got), {"Azpeitia nodulifer", "Fragilariopsis matuyamae",
                                    "Thalassiosira kolbei", "Thalassiosira jacksonii"})
        self.assertEqual(got["Azpeitia nodulifer"]["status"], "synonym")
        self.assertEqual(got["Azpeitia nodulifer"]["valid_name"], "Azpeitia nodulifera")
        self.assertEqual(got["Azpeitia nodulifer"]["checked"], "2018")
        self.assertEqual(got["Fragilariopsis matuyamae"]["status"], "accepted")
        self.assertEqual(got["Thalassiosira kolbei"]["status"], "unassessed")
        self.assertEqual(got["Thalassiosira jacksonii"]["status"], "absent")
        # 같은 열쇠에 다른 판정이면 멈춘다
        path.write_text(md + "| 8 | *Fragilariopsis matuyamae* | **Nitzschia x** | 갱신 2020 |\n",
                        encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.mod.from_answered_md(path, "t")

    def test_저장소의_taxon_names_에_기준면_답이_들어_있다(self):
        rows = {r["binomial"]: r for r in json.loads(
            (_ROOT / "taxon_names.json").read_text(encoding="utf-8"))}
        self.assertGreaterEqual(len(rows), 2108)
        self.assertEqual(rows["Thalassiosira tetraoestrupii"]["status"], "synonym")
        self.assertTrue(rows["Thalassiosira tetraoestrupii"]["valid_name"]
                        .startswith("Shionodiscus tetraoestrupii"))
        # 정리 노트가 반영하지 말라고 한 것 — 중심규조 → 깃돌말 오연결
        self.assertEqual(rows["Actinocyclus maccollumii"]["status"], "unassessed")
        self.assertIn("오연결", rows["Actinocyclus maccollumii"]["note"])
        # 오식은 합치지 않았다
        self.assertEqual(rows["Shionodiscus tetraoestruppii"]["status"], "absent")
        self.assertNotIn("Actinocyclus f", rows)


class ImportBiodatumsTests(DiaRUGATestCase):
    def setUp(self):
        self.mod = _load("import_biodatums")
        self.chk = _load("check_db")
        self.chk.problems.clear()

    def run_check(self):
        self.chk.problems.clear()
        self.chk.check_biodatum(None)
        return {name for name, _n, _why in self.chk.problems}

    def test_저장소의_JSON_이_그대로_들어온다(self):
        src = _ROOT / "atlas" / "biodatum" / "datums.json"
        self.assertTrue(src.exists(), "atlas/biodatum/datums.json 이 없다 (tools/parse_biodatums.py)")
        d = json.loads(src.read_text(encoding="utf-8"))
        nr, nd, nz = self.mod.put(d)
        self.assertEqual(self.mod.verify(d), [])
        # 2026-09-18 의 표 — 출처 14 · 기준면 728 · 대 43. **09-19 에 Gersonde &
        # Burckle (1990) 한 편이 더 왔다**(209) — 기준면 61 · 대 16. **09-20 에
        # Winter & Iwai (2002) 를 원문 표로 갈아 끼웠다**(210) — 웹 요약 28행이
        # 빠지고 시추공별 43행 · 대 12 가 들어왔다: 789 − 28 + 43 = 804
        self.assertEqual((nr, nd, nz), (15, 804, 71))
        self.assertEqual(Biodatum.objects.exclude(via="").count(), 102)
        # 원문 미대조(low) 행은 이제 없다 — 다시 생기면 누가 웹 요약을 넣은 것이다
        self.assertEqual(Biodatum.objects.filter(confidence="low").count(), 0)
        wi = Biodatum.objects.filter(reference__key="winter_iwai2002")
        self.assertEqual(wi.count(), 43)
        self.assertEqual(set(wi.values_list("variant", flat=True)),
                         {"Site 1095", "Site 1096", "Site 1101"})
        self.assertEqual(set(wi.values_list("page", flat=True)), {14, 17, 22})
        self.assertEqual(Biozone.objects.filter(scheme="winter2002").count(), 12)
        # 두 번 넣어도 같다
        self.mod.put(d)
        self.assertEqual(Biodatum.objects.count(), 804)
        self.assertEqual(Reference.objects.count(), 15)
        # 재인용 겹침 — (모델까지) 값이 같은 것이 41. Warnock Table 2 가 Cody
        # 값을 옮긴 48행 중 42행이 연령이 같은데, 그중 LO Hemidiscus karstenii
        # 는 평균 모델이라 적고 전범위 모델 값을 옮긴 것이라 겹침이 아니다
        rows = list(Biodatum.objects.select_related("reference"))
        self.assertEqual(len(rows) - len(data._dedupe_via(rows)), 41)
        # 13번 검사가 통과한다
        self.assertEqual(self.run_check(), set())

    def test_못_보던_출처면_멈춘다(self):
        d = {"references": [{"key": "nobody2030", "label": "Nobody (2030)", "authors": "Nobody",
                             "year": 2030, "citation": "", "url": ""}],
             "zones": [], "datums": []}
        with self.assertRaises(SystemExit):
            self.mod.put(d)

    def test_검사가_어긋난_것을_잡는다(self):
        r = ref("cody2008")
        datum(r, "Rouxia antarctica", "LO", 1.0, via="warnock2025")
        self.assertIn("경유 문헌이 Reference 에 없다", self.run_check())
        ref("warnock2025", 2025)
        self.assertNotIn("경유 문헌이 Reference 에 없다", self.run_check())
        Biodatum.objects.update(age_min=2.0)
        self.assertIn("연령이 하한·상한 밖이다", self.run_check())
