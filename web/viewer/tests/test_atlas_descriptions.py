"""도감 기재문이 반입에서 얹히고 화면에 나온다 (257).

기재문은 색인 JSON 이 아니라 `atlas/descriptions/<도감>.json` 으로 따로 실려
와 `ops/import_atlas.py` 가 `extra` 에 얹는다. **열쇠(`seq`)가 밀리면 기재문이
옆 종에 붙고 예외는 안 난다** — 그래서 표제어를 함께 대조하고, 그것을 여기서
되살려 본다.
"""
import json

from django.utils.html import escape

from viewer.models import AtlasEntry

from .base import DiaRUGATestCase
from .test_atlas import _ROOT, _load, doc, entry


def desc(*rows):
    return {"atlas": "test-atlas", "entries": [
        {"seq": s, "name": n, **kw} for s, n, kw in rows]}


class DescriptionMergeTest(DiaRUGATestCase):

    def setUp(self):
        self.mod = _load("import_atlas")
        self.d = doc([entry(1, "Melosira ambigua", "Melosira",
                            extra={"ecology": "담수산 플랑크톤이다."}),
                      entry(2, "Melosira distans", "Melosira")])

    def test_기재문이_extra_에_얹히고_있던_칸은_남는다(self):
        n, bad = self.mod.merge_descriptions(self.d, desc(
            (1, "Melosira ambigua", {"description": "세포는 원통상이다. 직경은 4~15 μ",
                                     "description_text": "세포는 원통상이다. 직경은 4~15"})))
        self.assertEqual((n, bad), (1, []))
        self.mod.put(self.d, 0)
        x = AtlasEntry.objects.get(seq=1).extra
        self.assertEqual(x["description"], "세포는 원통상이다. 직경은 4~15 μ")
        self.assertEqual(x["description_text"], "세포는 원통상이다. 직경은 4~15")
        self.assertEqual(x["ecology"], "담수산 플랑크톤이다.")
        self.assertNotIn("description", AtlasEntry.objects.get(seq=2).extra)

    def test_표제어가_다르면_안_얹는다(self):
        # 색인을 다시 뽑아 seq 가 한 칸 밀린 모양이다
        n, bad = self.mod.merge_descriptions(self.d, desc(
            (2, "Melosira ambigua", {"description": "세포는 원통상이다."})))
        self.assertEqual(n, 0)
        self.assertTrue(any("표제어" in b for b in bad))
        self.assertNotIn("description", self.d["entries"][1]["extra"])

    def test_색인에_없는_seq_는_걸린다(self):
        n, bad = self.mod.merge_descriptions(self.d, desc(
            (9, "Melosira varians", {"description": "…"})))
        self.assertEqual(n, 0)
        self.assertTrue(any("색인에 없다" in b for b in bad))

    def test_저장소의_기재문이_색인과_맞는다(self):
        files = sorted((_ROOT / "atlas" / "descriptions").glob("*.json"))
        self.assertTrue(files, "atlas/descriptions/*.json 이 저장소에 없다")
        for f in files:
            d = json.loads((_ROOT / "atlas" / f.name).read_text(encoding="utf-8"))
            ds = self.mod.load_descriptions(f)
            n, bad = self.mod.merge_descriptions(d, ds)
            self.assertEqual(bad, [], f.name)
            self.assertEqual(n, len(ds["entries"]), f.name)
            self.assertGreater(n, 0, f.name)


class DescriptionScreenTest(DiaRUGATestCase):

    def setUp(self):
        mod = _load("import_atlas")
        d = doc([entry(1, "Melosira ambigua", "Melosira"),
                 entry(2, "Melosira distans", "Melosira")])
        mod.merge_descriptions(d, desc(
            (1, "Melosira ambigua", {"description": "세포는 원통상(圓筒狀)이다.",
                                     "description_text": "세포는 원통상()이다."})))
        mod.put(d, 0)

    def test_도감_목록에_기재문이_나온다(self):
        body = self.client.get("/atlas/?q=Melosira").content.decode()
        self.assertIn("세포는 원통상(圓筒狀)이다.", body)
        self.assertIn("세포는 원통상()이다.", body)
        # 기재문이 없는 항목에는 빈 틀이 안 생긴다
        self.assertEqual(body.count('class="entryextra entrydesc"'), 1)
        # **기계가 읽은 것임을 화면이 말한다** — 원문으로 알고 인용하면 안 된다
        self.assertIn("기계가 읽은 원문", body)

    def test_비교_화면에_기재_줄이_생긴다(self):
        ks = [f"test-atlas:{e.name}" for e in AtlasEntry.objects.order_by("seq")]
        r = self.client.get("/atlas/compare/", {"e": ks})
        self.assertEqual(r.status_code, 200)
        self.assertIn("세포는 원통상(圓筒狀)이다.", r.content.decode())


class RealDescriptionScreenTest(DiaRUGATestCase):
    """저장소의 기재문을 **그대로** 반입해 화면에 낸다 (257 · Schmidt·논문).

    Schmidt 는 한 항목에 자리가 여럿이면 `Taf. N, Fig. x: …` 를 ` ／ ` 로 잇고,
    1985 논문은 한 항목이 5천 자를 넘는다. 합성 자료로는 그 모양이 안 나온다.
    """

    def _put(self, stem):
        mod = _load("import_atlas")
        d = json.loads((_ROOT / "atlas" / f"{stem}.json").read_text(encoding="utf-8"))
        ds = mod.load_descriptions(_ROOT / "atlas" / "descriptions" / f"{stem}.json")
        n, bad = mod.merge_descriptions(d, ds)
        self.assertEqual(bad, [])
        mod.put(d, 0)
        return ds["entries"]

    def _longest(self, stem, pred=lambda x: True):
        ents = self._put(stem)
        x = max((x for x in ents if pred(x)), key=lambda x: len(x["description"]))
        r = self.client.get("/atlas/", {"q": x["name"]})
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn(escape(x["description"]), body)
        return x, body

    def test_Schmidt_의_여러_자리_해설이_한_칸에_나온다(self):
        x, body = self._longest("schmidt", lambda x: " ／ " in x["description"])
        self.assertIn("Taf. ", x["description"])
        self.assertIn("기계가 읽은 원문", body)

    def test_논문의_긴_기재가_잘리지_않고_나온다(self):
        x, _ = self._longest("1985-akiba-yanagisawa")
        self.assertGreater(len(x["description"]), 3000)
