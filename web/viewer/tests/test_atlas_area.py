"""도감 화면의 권역 구분 (196) — 한국 · 남극 · 전역.

권역은 파일에도 DB 에도 없는 **사람의 판단**이라 `viewer/atlas.py` 의
`AREA_OF` 에 못 박혀 있고, 세 자리(도감 카드 · 검색 거르개 · 오프라인
꾸러미)가 같은 표를 본다. 여기서 세우는 것은 그 셋이 어긋나는 자리다.

## 되살려서 잡히는가

- 1번 — `data._atlas_scope` 에서 `area` 갈래를 빼면 실패한다. 남극을
  골랐는데 한국 도감이 나온다
- 2번 — `_atlas_chips` 의 권역 칩에서 `atlas=""` 를 빼면 실패한다. 한국
  도감을 고른 채 남극을 누르면 화면은 남극이고 결과는 한국 도감이다
- 3번 — `_atlas_area_groups` 에서 `("", "권역 미정")` 을 빼거나 `area_of`
  가 모르는 코드를 `"global"` 로 뭉개면 실패한다. 새 도감이 조용히 "전역"
  에 앉는다
- 4번 — `atlas_index` 의 `area_unknown` 을 빼면 실패한다. 모르는 권역을
  받아 놓고 아무 말 없이 빈 화면을 낸다
- 5번 — `atlas_suggest` 뷰가 `area` 를 안 넘기면 실패한다. 남극으로 걸러
  놓고 치는데 한국 이름을 권한다 — 골라도 결과가 빈다
- 6번 — `render_atlas_pages.LEFT_PARITY` 에 도감을 더하면서 `AREA_OF` 를
  안 채우면 실패한다. 굽는 표가 곧 "우리가 가진 도감" 의 목록이다
- 7번 — `atlas/*.json` 을 더하면서 `AREA_OF` 를 안 채우면 실패한다. 6번은
  **굽는 도감(책 셋)만 본다** — 논문 도판집은 쪽을 안 구워 그 표에 없고,
  카드도 안 서서 "권역 미정" 이 화면에 안 뜬다. 그런데 거르개는 `area_of`
  를 보므로 **권역을 골라 찾으면 그 논문의 종이 조용히 빠진다**(207 —
  `2002-censarek-miocene` 이 `?area=antarctic` 에서 사라졌다)
"""
import json
from pathlib import Path

from django.conf import settings
from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase, write_image
from .. import atlas as atlas_mod
from ..models import Atlas, AtlasEntry, AtlasPlacement


def seed_plates(root: Path, codes):
    """도감 코드마다 권 하나 · 쪽 하나. 목록 파일도 굽는 스크립트 모양으로."""
    mf = {}
    for code in codes:
        write_image(f"atlas/{code}/main/p0001.png", size=(40, 56))
        mf[code] = {"code": code, "label": f"{code} 도감",
                    "volumes": [{"code": "main", "label": "본권", "pages": 1}]}
    (root / "atlas").mkdir(parents=True, exist_ok=True)
    (root / "atlas" / "atlases.json").write_text(
        json.dumps({"dpi": 300, "atlases": mf}), encoding="utf-8")


class AtlasAreaTests(DiaRUGATestCase):
    def setUp(self):
        super().setUp()
        self.c = Client()
        k = Atlas.objects.create(key="korean", title="한국동식물도감 제9권",
                                 short="한국 도감", sort_order=0)
        s = Atlas.objects.create(key="schmidt", title="A. Schmidt, Atlas",
                                 short="Schmidt Atlas", sort_order=1)
        e = Atlas.objects.create(key="east-antarctic", title="동남극 도판집",
                                 short="동남극", sort_order=2)
        for atlas, seq, name, genus in (
                (k, 1, "Navicula koreana", "Navicula"),
                (s, 1, "Navicula abrupta", "Navicula"),
                (e, 1, "Navicula glaciei", "Navicula"),
                (e, 2, "Fragilariopsis curta", "Fragilariopsis")):
            en = AtlasEntry.objects.create(atlas=atlas, seq=seq, name=name,
                                           genus=genus, binomial=name,
                                           rank="species")
            AtlasPlacement.objects.create(entry=en, seq=0, plate=1, pdf_page=1)

    def get(self, **q):
        return self.c.get(reverse("atlas"), q).content.decode()

    # 1) 권역으로 거르면 그 권역의 도감만 나온다
    def test_area_filters_search(self):
        html = self.get(q="Navicula", area="antarctic")
        self.assertIn("Navicula glaciei", html)
        self.assertNotIn("Navicula koreana", html)
        self.assertNotIn("Navicula abrupta", html)
        # 도감 칩도 그 권역 것만 — 권역 밖의 도감을 고를 문이 없어야 한다
        self.assertIn("동남극", html)
        self.assertNotIn('title="A. Schmidt, Atlas"', html)
        # 속 목록도 그 권역 것만
        self.assertIn('<option value="Fragilariopsis">', html)
        self.assertNotIn('<option value="Navicula" selected>', html)

    # 2) 권역 칩은 도감을 떼고, 도감 칩은 권역을 들고 간다
    def test_area_chip_drops_atlas_and_atlas_chip_keeps_area(self):
        html = self.get(q="Navicula", atlas="korean")
        # 권역 칩 — `atlas=` 가 없어야 한다
        for line in html.splitlines():
            if 'href="' in line and "area=antarctic" in line and 'class="chip' in line:
                self.assertNotIn("atlas=", line)
                break
        else:
            self.fail("남극 권역 칩이 없다")
        html = self.get(q="Navicula", area="antarctic")
        self.assertIn("atlas=east-antarctic&amp;area=antarctic", html)

    # 3) 카드가 권역별로 서고, 모르는 도감은 "권역 미정" 으로 따로 선다
    def test_cards_grouped_by_area_with_unknown_bucket(self):
        seed_plates(Path(settings.DATA_ROOT),
                    ["korean", "schmidt", "east-antarctic", "zz-newatlas"])
        html = self.get()
        heads = [ln for ln in html.splitlines() if 'class="areahead"' in ln]
        labels = [h.split(">", 1)[1].split("\n")[0].strip() for h in heads]
        self.assertEqual(labels[:3], ["한국", "남극", "전역"])
        self.assertIn("권역 미정", html)
        self.assertEqual(atlas_mod.area_of("zz-newatlas"), "",
                         "모르는 도감을 어느 권역에 뭉갰다")
        # 권역을 고르면 그 묶음 하나만
        html = self.get(area="korea")
        self.assertIn("korean 도감", html)
        self.assertNotIn("schmidt 도감", html)
        self.assertNotIn("권역 미정", html)

    # 4) 모르는 권역은 말한다 — 조용히 전체를 내지 않는다
    def test_unknown_area_says_so(self):
        seed_plates(Path(settings.DATA_ROOT), ["korean"])
        html = self.get(area="mars")
        self.assertIn("모르는 권역", html)
        self.assertNotIn("korean 도감", html)
        html = self.get(q="Navicula", area="mars")
        self.assertNotIn("Navicula koreana", html)

    # 5) 자동완성도 거르개 안의 이름만 권한다
    def test_suggest_respects_area_and_atlas(self):
        url = reverse("atlas_suggest")
        rows = self.c.get(url, {"q": "Navi", "area": "antarctic"}).json()["rows"]
        self.assertEqual([r["value"] for r in rows], ["Navicula glaciei"])
        rows = self.c.get(url, {"q": "Navi", "atlas": "korean"}).json()["rows"]
        self.assertEqual([r["value"] for r in rows], ["Navicula koreana"])
        # 거르개가 없으면 셋 다
        rows = self.c.get(url, {"q": "Navi"}).json()["rows"]
        self.assertEqual(len(rows), 3)
        # 화면의 검색창이 그 문을 쓴다
        html = self.get()
        self.assertIn('list="atlas-suggest"', html)
        self.assertIn(url, html)

    # 6) 굽는 표의 도감마다 권역이 정해져 있다
    def test_every_rendered_atlas_has_an_area(self):
        import importlib.util
        src = Path(settings.BASE_DIR).parent / "tools" / "render_atlas_pages.py"
        spec = importlib.util.spec_from_file_location("render_atlas_pages", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        missing = sorted(set(mod.LEFT_PARITY) - set(atlas_mod.AREA_OF))
        self.assertEqual(missing, [],
                         f"권역이 안 정해진 도감: {missing} — atlas.AREA_OF 에 적는다")
        for code, area in atlas_mod.AREA_OF.items():
            self.assertIn(area, atlas_mod.AREA_LABEL, f"{code}: 모르는 권역 {area}")

    # 7) 저장소의 도감 JSON 마다 권역이 정해져 있다 — 논문 도판집까지
    def test_every_atlas_json_has_an_area(self):
        src = Path(settings.BASE_DIR).parent / "atlas"
        keys = {json.loads(f.read_text(encoding="utf-8"))["atlas"]["key"]
                for f in src.glob("*.json")}
        # 작업 이름(186)은 도감이 아니라 권역이 없는 것이 맞다
        keys.discard("working-names")
        missing = sorted(keys - set(atlas_mod.AREA_OF))
        self.assertEqual(missing, [],
                         f"권역이 안 정해진 도감: {missing} — atlas.AREA_OF 에 적는다")
