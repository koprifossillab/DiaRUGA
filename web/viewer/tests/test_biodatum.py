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
"""
import importlib.util
import json
import sys
from pathlib import Path

from .base import DiaRUGATestCase
from .. import biodatum as bd, data, mis
from ..models import Atlas, AtlasEntry, Biodatum, Biozone, Reference

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
        # 2026-09-18 의 표 — 출처 14 · 기준면 728 · 대 43
        self.assertEqual((nr, nd, nz), (14, 728, 43))
        self.assertEqual(Biodatum.objects.exclude(via="").count(), 102)
        # 두 번 넣어도 같다
        self.mod.put(d)
        self.assertEqual(Biodatum.objects.count(), 728)
        self.assertEqual(Reference.objects.count(), 14)
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
