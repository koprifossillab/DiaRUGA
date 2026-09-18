"""코어 자료 — 축·반입·매핑표 (P17 2·3단계).

**되살려서 잡히는 것만 적는다** (064). 여기 있는 것은 실제로 물릴 자리들이다:

- 관찰이 없는 코어는 축이 안 섰다. `RS14-GC04`·`RS19-GC17` 이 그 상태로
  들어온다 — 자료를 다 넣어 놓고도 화면이 빈다.
- 재반입이 사람이 넣은 항목을 덮으면 다시 만들 수 없다.
- 깊이 단위를 잘못 읽으면 **예외 없이** 프로파일이 코어 맨 위에 뭉친다.
  `RS14-GC04` 의 `MS`·`Opal` 이 실제로 머리글과 단위가 다르다.
"""
import csv
import importlib.util
import sys
import tempfile
import tomllib
from pathlib import Path

from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data
from ..models import CorePoint, CoreSeries, Locality, Site

_ROOT = Path(__file__).resolve().parents[3]
_MAPPING = _ROOT / "coredata" / "mapping.toml"


def _load(rel: str, name: str):
    """저장소의 스크립트를 모듈로 들인다 (`test_check_db_grade_pose` 와 같은 문)."""
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _series(loc, key, *, source="import", default_on=False, points=()):
    cs = CoreSeries.objects.create(locality=loc, key=key, label=key.upper(),
                                   unit="%", source=source,
                                   default_on=default_on)
    CorePoint.objects.bulk_create(
        [CorePoint(series=cs, depth_mm=mm, value=v) for mm, v in points])
    return cs


def _bare_locality(site_code="RS14", loc_code="GC04"):
    """**관찰이 하나도 없는 지점.** 새 코어가 들어오는 모습 그대로다."""
    site = Site.objects.create(code=site_code, area="ant")
    return Locality.objects.create(site=site, code=loc_code, kind="core")


class CoreSeriesReadTest(DiaRUGATestCase):
    """`data.core_series()` — 목록과 범위."""

    def test_범위를_cm_로_낸다(self):
        loc = _bare_locality()
        _series(loc, "opal", points=[(0, 48.5), (200, 44.0), (3620, 41.0)])
        (row,) = data.core_series(loc)
        self.assertEqual(row["n"], 3)
        # DB 는 mm, 화면은 cm. 바꾸는 자리가 이 함수 하나다.
        self.assertEqual(row["min_cm"], 0)
        self.assertEqual(row["max_cm"], 362)

    def test_점이_없는_항목은_범위가_None_이다(self):
        """**0 으로 두지 않는다** — 0 cm 에서 잰 것과 구별이 안 된다."""
        loc = _bare_locality()
        _series(loc, "opal")
        (row,) = data.core_series(loc)
        self.assertEqual(row["n"], 0)
        self.assertIsNone(row["min_cm"])
        self.assertIsNone(row["max_cm"])


class CoreAxisTest(DiaRUGATestCase):
    """축의 근거 (P17 6절). **시료와 코어 자료 둘 중 하나만 있어도 선다.**"""

    def test_관찰이_없어도_자료가_있으면_축이_선다(self):
        loc = _bare_locality()
        _series(loc, "opal", points=[(0, 48.5), (3620, 41.0)])
        ctx = data.locality_detail("RS14", "GC04")
        self.assertIsNotNone(ctx["axis"], "코어 자료만으로도 축이 서야 한다")
        self.assertGreaterEqual(ctx["axis"]["bottom"], 362)
        self.assertEqual(ctx["rows"], [])

    def test_자료도_관찰도_없으면_축이_안_선다(self):
        loc = _bare_locality()
        ctx = data.locality_detail("RS14", "GC04")
        self.assertIsNone(ctx["axis"])

    def test_점이_없는_항목은_축을_안_잡는다(self):
        """이름만 만들어 둔 항목. `max_cm` 이 `None` 이라 비교에서 죽던 자리다."""
        loc = _bare_locality()
        _series(loc, "opal")
        ctx = data.locality_detail("RS14", "GC04")
        self.assertIsNone(ctx["axis"])

    def test_자료가_없어도_시료가_있으면_축이_선다(self):
        """넓히기 전부터 되던 것. **되돌아가지 않는지 본다.**"""
        fx.make_world(slug="rs23", depth_cm=71.0)
        ctx = data.locality_detail("RS23", "GC03")
        self.assertIsNotNone(ctx["axis"])

    def test_더_깊은_쪽이_축을_잡는다(self):
        """시료는 71 cm 인데 자료가 362 cm 까지 있으면 축은 362 를 덮어야 한다."""
        w = fx.make_world(slug="rs23", depth_cm=71.0)
        _series(w.locality, "opal", points=[(0, 48.5), (3620, 41.0)])
        ctx = data.locality_detail("RS23", "GC03")
        self.assertGreaterEqual(ctx["axis"]["bottom"], 362)


class CorePageTest(DiaRUGATestCase):
    """화면. **자료가 어느 갈래로 가는지를 본다** (086)."""

    def test_관찰이_없는_코어_페이지가_뜬다(self):
        loc = _bare_locality()
        _series(loc, "opal", default_on=True,
                points=[(0, 48.5), (3620, 41.0)])
        r = self.client.get(reverse("core", args=["RS14", "GC04"]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        # **글자로 짚지 않는다** — `base.html` 의 CSS 주석에 "코어 자료" 가
        # 들어 있어서 어느 화면에서나 걸린다. 렌더된 블록을 본다.
        self.assertIn('class="csbox"', html)
        self.assertIn("OPAL", html)
        # 축이 섰으므로 "축을 그릴 수 없습니다" 가 뜨면 안 된다
        self.assertNotIn("축을 그릴 수 없습니다", html)

    def test_아무것도_없으면_편집하러_보내지_않는다(self):
        """관찰이 없는 코어에 "정보 편집에서 깊이를 채우세요" 는 갈 곳이 없다."""
        _bare_locality()
        r = self.client.get(reverse("core", args=["RS14", "GC04"]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("아직 관찰도 코어 자료도 없습니다", html)
        self.assertNotIn("정보 편집에서 깊이를 채우면", html)

    def test_노두에는_안_뜬다(self):
        """노두에는 cm 축이 없다 — 그 자리는 현장 사진이 쓴다."""
        w = fx.make_world(slug="bp09", site_code="BP", loc_code="BP09",
                          kind="outcrop", area="kr", sample_code="0901")
        r = self.client.get(reverse("core", args=["BP", "BP09"]))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('class="csbox"', r.content.decode())


class ImportCoredataTest(DiaRUGATestCase):
    """`ops/import_coredata.py` — **자기 출처만 갈아치운다** (P17 3.1)."""

    def setUp(self):
        super().setUp()
        self.mod = _load("ops/import_coredata.py", "import_coredata_under_test")
        self.loc = _bare_locality()
        self.dir = Path(tempfile.mkdtemp(prefix="diaruga-test-coredata-"))

    def _write(self, name="RS14-GC04", series=(), points=()):
        with (self.dir / f"{name}.series.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "label", "unit", "default_on", "sort_order",
                        "origin"])
            w.writerows(series)
        with (self.dir / f"{name}.points.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "depth_mm", "value"])
            w.writerows(points)

    def test_반입한다(self):
        self._write(series=[["opal", "Opal", "%", "1", "50", "x.xlsx::Opal"]],
                    points=[["opal", 0, 48.5], ["opal", 3620, 41.0]])
        rc = self.mod.load_one("RS14", "GC04",
                               self.dir / "RS14-GC04.series.csv",
                               self.dir / "RS14-GC04.points.csv", False)
        self.assertEqual(rc, 0)
        cs = CoreSeries.objects.get(locality=self.loc, key="opal")
        self.assertTrue(cs.default_on)
        self.assertEqual(cs.points.count(), 2)

    def test_다시_돌려도_두_벌이_안_된다(self):
        args = ("RS14", "GC04", self.dir / "RS14-GC04.series.csv",
                self.dir / "RS14-GC04.points.csv", False)
        self._write(series=[["opal", "Opal", "%", "1", "50", "x"]],
                    points=[["opal", 0, 48.5]])
        self.mod.load_one(*args)
        self.mod.load_one(*args)
        self.assertEqual(CoreSeries.objects.filter(locality=self.loc).count(), 1)
        self.assertEqual(CorePoint.objects.count(), 1)

    def test_사람이_넣은_항목은_안_덮는다(self):
        """**이것이 `source` 를 가른 이유다.** 063 과 같은 줄."""
        _series(self.loc, "chaetoceros", source="manual",
                points=[(0, 120.0), (500, 88.0)])
        self._write(series=[["opal", "Opal", "%", "1", "50", "x"]],
                    points=[["opal", 0, 48.5]])
        self.mod.load_one("RS14", "GC04",
                          self.dir / "RS14-GC04.series.csv",
                          self.dir / "RS14-GC04.points.csv", False)
        kept = CoreSeries.objects.get(locality=self.loc, key="chaetoceros")
        self.assertEqual(kept.source, "manual")
        self.assertEqual(kept.points.count(), 2)

    def test_dry_run_은_아무것도_안_쓴다(self):
        self._write(series=[["opal", "Opal", "%", "1", "50", "x"]],
                    points=[["opal", 0, 48.5]])
        rc = self.mod.load_one("RS14", "GC04",
                               self.dir / "RS14-GC04.series.csv",
                               self.dir / "RS14-GC04.points.csv", True)
        self.assertEqual(rc, 0)
        self.assertEqual(CoreSeries.objects.count(), 0)

    def test_지점이_없으면_만들지_않고_멈춘다(self):
        self._write(name="RS99-GC01",
                    series=[["opal", "Opal", "%", "0", "50", "x"]],
                    points=[["opal", 0, 48.5]])
        rc = self.mod.load_one("RS99", "GC01",
                               self.dir / "RS99-GC01.series.csv",
                               self.dir / "RS99-GC01.points.csv", False)
        self.assertEqual(rc, 1)
        self.assertFalse(Locality.objects.filter(code="GC01").exists())

    def test_항목에_없는_key_가_점에_있으면_멈춘다(self):
        self._write(series=[["opal", "Opal", "%", "0", "50", "x"]],
                    points=[["opal", 0, 48.5], ["ms_whole", 0, 8.2]])
        rc = self.mod.load_one("RS14", "GC04",
                               self.dir / "RS14-GC04.series.csv",
                               self.dir / "RS14-GC04.points.csv", False)
        self.assertEqual(rc, 1)
        self.assertEqual(CoreSeries.objects.count(), 0)


class _FakeSheet:
    """`read_block` 이 엑셀에서 쓰는 것은 `iter_rows` 하나뿐이다."""

    def __init__(self, rows):
        self.rows = rows

    def iter_rows(self, min_row=1, values_only=True):
        return iter(self.rows[min_row - 1:])


class ExtractTest(DiaRUGATestCase):
    """`tools/coredata_extract.py` 의 순수 부분. **xlsx 없이 돈다.**"""

    def setUp(self):
        super().setUp()
        self.mod = _load("tools/coredata_extract.py", "coredata_extract_under_test")

    def test_cm_는_열_배로_들어간다(self):
        self.assertEqual(self.mod._to_mm(36.2, "cm"), 362)
        self.assertEqual(self.mod._to_mm(3609, "mm"), 3609)

    def test_글자_칸은_안_읽는다(self):
        """`TYPE`(`gM`)·`Munsell C Hue`(`0.6Y`)가 이 갈래로 걸린다."""
        self.assertIsNone(self.mod._num("gM"))
        self.assertIsNone(self.mod._num("0.6Y"))
        self.assertIsNone(self.mod._num(None))
        self.assertEqual(self.mod._num("48.5"), 48.5)

    def test_값이_없는_깊이는_점을_안_만든다(self):
        ws = _FakeSheet([("깊이", "값"), (0, 1.0), (1, None), (2, 3.0)])
        got = self.mod.read_block(ws, {
            "sheet": "T", "header_row": 1, "depth_col": 1, "depth_unit": "cm",
            "columns": [[2, "v", "V", ""]]})
        self.assertEqual(got["v"], {0: 1.0, 20: 3.0})

    def test_깊이_접두사는_적힌_것만_뗀다(self):
        """KPDC 의 `GC03-C1` xlsx 가 깊이 칸에 `GC03-C1 14` 를 든다 (197). `LOD`
        같은 머리 줄은 접두사가 아니라 숫자로 안 읽힌다."""
        ws = _FakeSheet([("Core & Depth", "v"), (None, 20), ("LOD", 5),
                         ("GC03-C1 0", 1.0), ("GC03-C1 14", 2.0), ("X 30", 3.0)])
        got = self.mod.read_block(ws, {
            "sheet": "S", "header_row": 1, "depth_col": 1, "depth_unit": "cm",
            "depth_prefix": "GC03-C1 ", "columns": [[2, "v", "V", ""]]})
        self.assertEqual(got["v"], {0: 1.0, 140: 2.0})

    def test_같은_깊이_같은_값은_한_번만_들어간다(self):
        """`RS14-GC04` 의 `MS` 가 221~260 cm 40점을 값까지 똑같이 겹쳐 들고 있다."""
        ws = _FakeSheet([("깊이", "값"), (0, 1.0), (1, 2.0), (0, 1.0)])
        got = self.mod.read_block(ws, {
            "sheet": "MS", "header_row": 1, "depth_col": 1, "depth_unit": "cm",
            "columns": [[2, "v", "V", ""]]})
        self.assertEqual(got["v"], {0: 1.0, 10: 2.0})

    def test_같은_깊이에_다른_값이면_멈춘다(self):
        """**어느 쪽이 맞는지 스크립트가 고를 수 없다.** 사람이 정할 일이다."""
        ws = _FakeSheet([("깊이", "값"), (0, 1.0), (0, 9.0)])
        with self.assertRaises(ValueError):
            self.mod.read_block(ws, {
                "sheet": "MS", "header_row": 1, "depth_col": 1,
                "depth_unit": "cm", "columns": [[2, "v", "V", ""]]})

    # --- pptx 차트 (206) — `read_pptx_charts` 가 낸 모양을 손으로 만든다 ---

    def _charts(self, xs, ys, slide=3, title="opal  final"):
        return {slide: {self.mod._norm_title(title): (
            dict(enumerate(xs)), dict(enumerate(ys)))}}

    def test_깊이_축은_매핑표가_말한다(self):
        """같은 파일에서 Opal 만 깊이가 x 축이다. 뒤집으면 값이 깊이 자리에 앉는다."""
        charts = self._charts([0, 2, 4], [23.5, 24.6, 22.5])
        got = self.mod.read_chart(charts, {
            "slide": 3, "title": "opal final", "depth_axis": "x", "depth_unit": "cm"})
        self.assertEqual(got, {0: 23.5, 20: 24.6, 40: 22.5})
        with self.assertRaises(ValueError):
            self.mod.read_chart(charts, {
                "slide": 3, "title": "opal final", "depth_axis": "y",
                "depth_unit": "cm"})

    def test_제목은_띄어쓰기_대소문자를_안_가린다(self):
        """`opal  final`(공백 둘)·`Density(g/cm3)` 가 한 파일 안에 섞여 있다."""
        charts = self._charts([0], [1.0], title="Opal  Final")
        got = self.mod.read_chart(charts, {
            "slide": 3, "title": "opal final", "depth_axis": "x", "depth_unit": "cm"})
        self.assertEqual(got, {0: 1.0})

    def test_없는_차트는_있는_것을_들어_말한다(self):
        charts = self._charts([0], [1.0])
        with self.assertRaisesRegex(ValueError, "opal final"):
            self.mod.read_chart(charts, {
                "slide": 3, "title": "toc", "depth_axis": "x", "depth_unit": "cm"})

    def test_점은_idx_로_짝짓는다(self):
        """빈 셀은 그 축의 캐시에서만 빠진다 — 차례로 zip 하면 뒤가 다 어긋난다."""
        charts = {3: {"toc": ({0: 0.5, 2: 0.7}, {0: 0.0, 1: 2.0, 2: 4.0})}}
        got = self.mod.read_chart(charts, {
            "slide": 3, "title": "toc", "depth_axis": "y", "depth_unit": "cm"})
        self.assertEqual(got, {0: 0.5, 40: 0.7})


class MappingTableTest(DiaRUGATestCase):
    """매핑표 자체를 검사한다.

    **머리글이 틀려 있는 자리를 사람이 확인해서 적어 둔 것이 이 표다** (P17 1.1).
    누가 "머리글대로 고치자" 며 되돌리면 프로파일이 조용히 어긋난다 — 예외도
    경고도 없다. 그래서 **확인해 둔 사례를 검사로 박는다.**
    """

    def setUp(self):
        super().setUp()
        with _MAPPING.open("rb") as f:
            self.conf = tomllib.load(f)
        self.cores = {f"{c['site']}-{c['locality']}": c for c in self.conf["core"]}

    @staticmethod
    def _keys(core):
        """블록(xlsx)이든 차트(pptx)든 항목 key 를 편다 — 추출기의 `_entries` 와 같다."""
        if "chart" in core:
            return [ch["key"] for ch in core["chart"]]
        return [c[1] for b in core["block"] for c in b["columns"]]

    def _block(self, core, sheet, depth_col=None):
        for b in self.cores[core]["block"]:
            if b["sheet"] == sheet and (depth_col is None
                                        or b["depth_col"] == depth_col):
                return b
        self.fail(f"{core} 에 {sheet} 블록이 없다")

    def test_RS14_의_MS_는_머리글이_mm_라도_cm_다(self):
        """값이 1~362 이고 코어가 362 cm 다. mm 로 읽으면 맨 위 36 cm 에 뭉친다."""
        self.assertEqual(self._block("RS14-GC04", "MS", 1)["depth_unit"], "cm")
        self.assertEqual(self._block("RS14-GC04", "MS", 4)["depth_unit"], "cm")

    def test_RS14_의_Opal_은_머리글이_m_라도_cm_다(self):
        self.assertEqual(self._block("RS14-GC04", "Opal")["depth_unit"], "cm")

    def test_XRF_만_진짜_mm_다(self):
        """값이 1~3609 이고 그것이 360.9 cm 다."""
        self.assertEqual(self._block("RS14-GC04", "XRF")["depth_unit"], "mm")

    def test_코어_길이가_적혀_있다(self):
        """단위를 잘못 읽으면 열 배로 어긋난다 — 반입기가 이 값으로 자기를 본다."""
        self.assertEqual(self.cores["RS14-GC04"]["expect_max_cm"], 362)
        self.assertEqual(self.cores["RS19-GC17"]["expect_max_cm"], 599)

    def test_켤_항목이_실제로_있는_key_다(self):
        """오타면 화면이 아무것도 안 켠 채 뜬다 — 예외가 안 난다."""
        for name, core in self.cores.items():
            keys = set(self._keys(core))
            missing = set(core.get("default_on", [])) - keys
            self.assertFalse(missing, f"{name}: default_on 에 없는 key {missing}")

    def test_규조_자료와_함께_보는_넷이_켜져_있다(self):
        """사용자 방침 2026-08-19 — MS · 함수율 · Opal · TOC."""
        on = set(self.cores["RS14-GC04"]["default_on"])
        self.assertEqual(on, {"ms_whole", "wc", "opal", "toc"})
        # RS19 에는 Opal 시트가 없다. 없는 것을 켤 수는 없다.
        self.assertEqual(set(self.cores["RS19-GC17"]["default_on"]),
                         {"ms_whole", "wc", "toc"})

    def test_RS21_은_Opal_만_깊이가_x_축이다(self):
        """pptx 산점도 스무 개 중 Opal 다섯만 축이 뒤집혀 있다 (206). 누가 "다
        같게 맞추자" 며 고치면 Opal 이 값을 깊이로 읽는다."""
        for name in ("RS21-GC02", "RS21-GC03B", "RS21-GC04", "RS21-GC05", "RS21-GC06"):
            axes = {ch["key"]: ch["depth_axis"] for ch in self.cores[name]["chart"]}
            self.assertEqual(axes, {"wc": "y", "toc": "y", "density": "y",
                                    "opal": "x"}, name)

    def test_RS21_의_코어_길이는_KPDC_값이다(self):
        """`Locality.kpdc_meta.core_length_m` 에서 옮겨 적었다 (197). GC06 은 KPDC
        에 없어 자료의 끝이다."""
        self.assertEqual(self.cores["RS21-GC02"]["expect_max_cm"], 217)
        self.assertEqual(self.cores["RS21-GC03B"]["expect_max_cm"], 288)
        self.assertEqual(self.cores["RS21-GC04"]["expect_max_cm"], 208)
        self.assertEqual(self.cores["RS21-GC05"]["expect_max_cm"], 279)

    def test_key_가_코어_안에서_안_겹친다(self):
        for name, core in self.cores.items():
            keys = self._keys(core)
            self.assertEqual(len(keys), len(set(keys)), f"{name}: key 중복")


class ProfileChartTest(DiaRUGATestCase):
    """꺾은선 (P17 4단계). **줄이기·끊기·고르기가 잡히는 자리다.**"""

    def setUp(self):
        super().setUp()
        self.loc = _bare_locality()

    def test_고른_것만_점을_읽는다(self):
        """42개 항목을 다 당기면 코어 하나에 9만 점이다."""
        _series(self.loc, "opal", default_on=True, points=[(0, 1.0), (100, 2.0)])
        _series(self.loc, "toc", points=[(0, 0.5), (100, 0.6)])
        ctx = data.locality_detail("RS14", "GC04")
        self.assertEqual([p["key"] for p in ctx["profiles"]], ["opal"])

    def test_주소가_없으면_기본이_켜진다(self):
        _series(self.loc, "opal", default_on=True, points=[(0, 1.0), (100, 2.0)])
        _series(self.loc, "tn", points=[(0, 0.5)])
        ctx = data.locality_detail("RS14", "GC04", series_keys=None)
        self.assertEqual([p["key"] for p in ctx["profiles"]], ["opal"])

    def test_빈_주소는_다_끈다(self):
        """`?series=` 와 주소 없음이 같아지면 **전부 끌 방법이 없어진다.**"""
        _series(self.loc, "opal", default_on=True, points=[(0, 1.0), (100, 2.0)])
        ctx = data.locality_detail("RS14", "GC04", series_keys=[])
        self.assertEqual(ctx["profiles"], [])
        self.assertFalse(any(cs["on"] for cs in ctx["series"]))

    def test_없는_key_는_버리고_화면은_선다(self):
        """링크가 낡았다는 이유로 화면이 죽으면 안 된다."""
        _series(self.loc, "opal", points=[(0, 1.0), (100, 2.0)])
        ctx = data.locality_detail("RS14", "GC04", series_keys=["nosuch", "opal"])
        self.assertEqual([p["key"] for p in ctx["profiles"]], ["opal"])

    def test_x_는_항목마다_따로_편다(self):
        """함수율(%)과 자기감수율(SI)을 한 축에 얹을 수 없다."""
        _series(self.loc, "opal", points=[(0, 10.0), (100, 20.0), (200, 30.0)])
        (pr,) = data.core_profiles(self.loc, ["opal"])
        xs = [pt["x"] for seg in pr["segments"] for pt in seg]
        self.assertEqual((pr["lo"], pr["hi"]), (10.0, 30.0))
        self.assertEqual(xs, [0, 50, 100])

    def test_빈_구간을_가로지르지_않는다(self):
        """이으면 **안 잰 구간이 잰 것처럼 뜬다.**"""
        pts = [(0, 1.0), (10, 1.0), (20, 1.0), (5000, 2.0), (5010, 2.0)]
        _series(self.loc, "opal", points=pts)
        (pr,) = data.core_profiles(self.loc, ["opal"])
        self.assertEqual(len(pr["segments"]), 2)
        self.assertEqual([len(s) for s in pr["segments"]], [3, 2])

    def test_고르게_잰_것은_안_끊는다(self):
        pts = [(i * 20, float(i)) for i in range(30)]
        _series(self.loc, "opal", points=pts)
        (pr,) = data.core_profiles(self.loc, ["opal"])
        self.assertEqual(len(pr["segments"]), 1)

    def test_점이_많으면_줄이고_줄였다고_말한다(self):
        """XRF 가 한 원소에 3,575점이다. **조용히 줄이면 안 잰 구간과 같아진다.**"""
        pts = [(i, float(i % 7)) for i in range(3000)]
        _series(self.loc, "xrf_fe", points=pts)
        (pr,) = data.core_profiles(self.loc, ["xrf_fe"], cap=200)
        self.assertEqual(pr["n"], 3000)
        self.assertTrue(pr["thinned"])
        self.assertLessEqual(pr["shown"], 200)
        self.assertGreater(pr["shown"], 0)

    def test_줄여도_봉우리와_골이_남는다(self):
        """**평균을 내지 않는다** — 없던 값이 생기고 뾰족한 곳이 사라진다."""
        pts = [(i, 1.0) for i in range(1000)]
        pts[500] = (500, 99.0)                       # 봉우리 하나
        pts[700] = (700, -50.0)                      # 골 하나
        _series(self.loc, "xrf_fe", points=pts)
        (pr,) = data.core_profiles(self.loc, ["xrf_fe"], cap=100)
        vals = [pt["v"] for seg in pr["segments"] for pt in seg]
        self.assertIn(99.0, vals)
        self.assertIn(-50.0, vals)
        # 남은 값이 전부 실제로 잰 값인가 (지어낸 값이 없는가)
        real = {v for _, v in pts}
        self.assertTrue(set(vals) <= real)

    def test_안_줄여도_되면_그대로_둔다(self):
        _series(self.loc, "opal", points=[(0, 1.0), (100, 2.0)])
        (pr,) = data.core_profiles(self.loc, ["opal"], cap=800)
        self.assertFalse(pr["thinned"])
        self.assertEqual(pr["shown"], 2)

    def test_XRF_는_접어_둔다(self):
        _series(self.loc, "opal", default_on=True, points=[(0, 1.0)])
        _series(self.loc, "xrf_fe", points=[(0, 1.0)])
        ctx = data.locality_detail("RS14", "GC04")
        by = {cs["key"]: cs for cs in ctx["series"]}
        self.assertTrue(by["xrf_fe"]["collapsed"])
        self.assertFalse(by["opal"]["collapsed"])
        self.assertEqual(ctx["n_collapsed"], 1)
        self.assertEqual(ctx["collapsed_on"], 0)

    def test_접어_둔_것이_켜져_있으면_센다(self):
        """그림에는 있는데 끄는 자리를 못 찾는 상태가 되면 안 된다."""
        _series(self.loc, "xrf_fe", points=[(0, 1.0)])
        ctx = data.locality_detail("RS14", "GC04", series_keys=["xrf_fe"])
        self.assertEqual(ctx["collapsed_on"], 1)


class ProfileChartPageTest(DiaRUGATestCase):
    """화면. 자료가 어느 갈래로 가는지를 본다 (086)."""

    def setUp(self):
        super().setUp()
        self.loc = _bare_locality()
        self.url = reverse("core", args=["RS14", "GC04"])

    def test_켜진_항목이_그려진다(self):
        _series(self.loc, "opal", default_on=True,
                points=[(0, 10.0), (1000, 20.0), (3620, 30.0)])
        html = self.client.get(self.url).content.decode()
        # **코어 로그 안이다** — 시료 표식 옆에서 읽어야 하는 그림이다
        # (사용자 요청 2026-08-19). 아래에 따로 그리던 것을 옮겼다.
        self.assertIn('class="cslane"', html)
        self.assertIn("<polyline", html)
        # 깊이를 그대로 y 좌표로 쓴다 — 축 계산이 한 군데로 모인다
        self.assertIn('viewBox="0 0 100 400"', html)

    def test_다_끄면_그림이_없고_그렇게_적는다(self):
        _series(self.loc, "opal", default_on=True, points=[(0, 10.0), (3620, 20.0)])
        html = self.client.get(self.url, {"series": ""}).content.decode()
        self.assertNotIn('class="cslane"', html)
        self.assertIn("켜 둔 항목이 없습니다", html)

    def test_줄인_것을_화면이_말한다(self):
        pts = [(i, float(i % 7)) for i in range(3000)]
        _series(self.loc, "xrf_fe", points=pts)
        html = self.client.get(self.url, {"series": "xrf_fe"}).content.decode()
        self.assertIn("3000점 중", html)

    def test_점이_없는_항목은_켤_수_없다(self):
        """켜 봐야 빈 칸이 그려진다. 누를 수 있으면 고장으로 읽힌다."""
        _series(self.loc, "opal")
        html = self.client.get(self.url).content.decode()
        self.assertIn("disabled", html)

    def test_노두에는_그림이_없다(self):
        fx.make_world(slug="bp09", site_code="BP", loc_code="BP09",
                      kind="outcrop", area="kr", sample_code="0901")
        html = self.client.get(reverse("core", args=["BP", "BP09"])).content.decode()
        self.assertNotIn('class="cslane"', html)


class LaneLayoutTest(DiaRUGATestCase):
    """칸이 코어 로그 안에 있으면 **시료 표식이 그만큼 밀려야 한다** (P17 5단계).

    예전 `.mark` 는 `left:146px` 에 못 박혀 있었다. 거기가 곧 첫 칸 자리라,
    안 밀면 표식이 그림 위에 겹쳐 앉는다 — 관찰이 있는 코어에서만 나는 고장이고
    **새 코어 둘은 관찰이 0개라 안 겹친다.** 그래서 여기서 관찰이 있는 코어로
    본다(086: 자료가 어느 갈래로 가는지).
    """

    def test_칸_수가_화면에_실린다(self):
        w = fx.make_world(slug="rs23", depth_cm=71.0)
        _series(w.locality, "opal", default_on=True, points=[(0, 1.0), (1000, 2.0)])
        _series(w.locality, "wc", default_on=True, points=[(0, 1.0), (1000, 2.0)])
        html = self.client.get(reverse("core", args=["RS23", "GC03"])).content.decode()
        # 머리줄·그림·표식·발치가 전부 이 값으로 자리를 잡는다
        self.assertIn("--lanes:2", html)
        self.assertIn('style="--i:0"', html)
        self.assertIn('style="--i:1"', html)
        # 표식도 함께 있어야 이 시험이 뜻을 갖는다
        self.assertIn('class="mark', html)

    def test_다_끄면_칸이_0_이라_표식이_제자리다(self):
        w = fx.make_world(slug="rs23", depth_cm=71.0)
        _series(w.locality, "opal", default_on=True, points=[(0, 1.0), (1000, 2.0)])
        html = self.client.get(reverse("core", args=["RS23", "GC03"]),
                               {"series": ""}).content.decode()
        self.assertIn("--lanes:0", html)
        self.assertNotIn('class="cslane"', html)
