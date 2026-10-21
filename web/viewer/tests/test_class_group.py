"""분류 묶음 — 원통상 (224 · 사용자 2026-10-21).

Rhizosolenia·Dactyliosolen 은 가르는 분류로 두고, 묶음(`ClassGroup`)이 화면에서
합쳐 센다. **밟기 쉬운 자리가 둘이다.**

- **묶음 칸이 합계에 다시 들어가면** 원통상이 두 번 세어진다 — "검출" 칸은
  분류만 더해야 한다
- **세지 않는 분류(원통상 파편)가 묶음 수에 들면** 파편이 개체로 세어진다 —
  원형 파편이 원형 수에 안 드는 것과 같아야 한다

후보는 픽스처 표의 차례로 돈다(`make_world`) — 아홉이면 분류마다 하나다.
"""
import importlib

from django.apps import apps as django_apps
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data
from ..models import ClassDef, DiatomObject


def _row(ctx, key):
    return next(r for r in ctx["rows"] + ctx["extra_rows"] if r["key"] == key)


class CylinderRowsTest(DiaRUGATestCase):
    """마이그레이션 `0049` 가 넣은 행 — 픽스처가 아니라 마이그레이션이 만든 것이다."""

    def test_두_분류가_원통상에_든다(self):
        for key in ("rhizosolenia", "dactyliosolen", "cylinder_frag"):
            with self.subTest(key=key):
                row = ClassDef.objects.get(key=key)
                self.assertEqual(row.group.key, "cylinder")
                self.assertEqual(row.group.label, "원통상")
                self.assertEqual(row.hotkey, "t")

    def test_Dactyliosolen_은_Rhizosolenia_와_같은_색이다(self):
        """사용자가 정한 것이다 — 갈리면 배지 글자로만 구분된다."""
        self.assertEqual(ClassDef.objects.get(key="dactyliosolen").color,
                         ClassDef.objects.get(key="rhizosolenia").color)

    def test_파편은_세지_않는다(self):
        row = ClassDef.objects.get(key="cylinder_frag")
        self.assertFalse(row.counted)
        self.assertFalse(row.is_taxon)

    def test_순환은_RHZ_DAC_파편_차례다(self):
        keys = list(ClassDef.objects.filter(hotkey="t", active=True)
                    .order_by("sort_order").values_list("key", flat=True))
        self.assertEqual(keys, ["rhizosolenia", "dactyliosolen", "cylinder_frag"])

    def test_픽스처_표와_같은_값이다(self):
        """옮겨 적은 표와 마이그레이션이 어긋나면 시험이 한쪽만 보고 통과한다."""
        for key in ("dactyliosolen", "cylinder_frag"):
            with self.subTest(key=key):
                row = ClassDef.objects.get(key=key)
                mirror = next(c for c in fx.CLASSES if c[0] == key)
                _, label, short, badge, color, hot, counted, taxon = mirror
                self.assertEqual(
                    (row.label, row.short, row.badge, row.color, row.hotkey,
                     row.counted, row.is_taxon),
                    (label, short, badge, color, hot, counted, taxon))


class MoveRoundDactyliosolenTest(DiaRUGATestCase):
    """원형으로 적어 둔 Dactyliosolen 을 옮긴다 — **종명으로 사람이 정한 것만.**"""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="m", n_candidates=4)
        k = cls.w.keys()
        fx.add_review(cls.w.vp, k[0], label="round",
                      species="Dactyliosolen antarcticus")
        fx.add_review(cls.w.vp, k[1], label="round",
                      species="Thalassiosira lentiginosa")
        fx.add_review(cls.w.vp, k[2], label="rod",
                      species="Dactyliosolen antarcticus")

    def _run(self, fn):
        """마이그레이션의 함수를 지금 모델에 대고 부른다 — 옮기는 규칙만 본다."""
        mod = importlib.import_module("viewer.migrations.0049_classdef_cylinder")
        getattr(mod, fn)(django_apps, None)

    def test_원형_Dactyliosolen_만_옮긴다(self):
        self._run("add")
        got = sorted(DiatomObject.objects.exclude(species="")
                     .values_list("species", "label"))
        self.assertEqual(got, [
            ("Dactyliosolen antarcticus", "dactyliosolen"),
            ("Dactyliosolen antarcticus", "rod"),       # 원형이 아니면 안 옮긴다
            ("Thalassiosira lentiginosa", "round"),     # 종명이 다르면 안 옮긴다
        ])

    def test_되돌리면_원형으로_돌아간다(self):
        self._run("add")
        self._run("remove")
        self.assertEqual(
            DiatomObject.objects.filter(
                species="Dactyliosolen antarcticus").order_by("label")
            .values_list("label", flat=True).first(), "rod")
        self.assertTrue(DiatomObject.objects.filter(
            species="Dactyliosolen antarcticus", label="round").exists())
        # 다음 시험이 쓰는 표를 되살린다
        self._run("add")


class GroupCountTest(DiaRUGATestCase):
    """목록 표·개수 줄·카탈로그·산출 비교가 원통상을 합쳐 센다."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 분류마다 하나 + rhizosolenia·dactyliosolen 이 한 번 더(열넷째까지)
        cls.w = fx.make_world(slug="g", n_candidates=len(fx.CLASSES) + 8)
        # 카탈로그 카드는 개체 단위다 — 검토 완료가 개체를 세운다 (P18)
        for vp in cls.w.viewpoints:
            fx.review_done(vp)

    def summary(self):
        sl = self.w.slide
        return data._slide_summary(sl)

    def test_묶음_칸이_첫_분류_앞에_놓인다(self):
        cols = self.summary()["counted_cols"]
        keys = [c["key"] for c in cols]
        at = keys.index("group:cylinder")
        self.assertEqual(keys[at + 1:at + 3], ["rhizosolenia", "dactyliosolen"])
        self.assertTrue(cols[at]["is_group"])
        self.assertTrue(cols[at + 1]["in_group"])

    def test_묶음_수는_안의_세는_분류만_더한다(self):
        s = self.summary()
        per = {c["key"]: c["n"] for c in s["counted"]}
        grp = next(c for c in s["counted_cols"] if c["key"] == "group:cylinder")
        self.assertEqual(grp["n"], per["rhizosolenia"] + per["dactyliosolen"])
        self.assertNotIn("cylinder_frag", per, "파편이 세는 분류에 들었다")

    def test_검출_칸에_묶음이_두_번_안_든다(self):
        s = self.summary()
        self.assertEqual(s["n_counted"], sum(c["n"] for c in s["counted"]))
        self.assertNotIn("group:cylinder", [c["key"] for c in s["counted"]])

    def test_목록_표의_머리와_줄의_칸_수가_같다(self):
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn('class="grpcol">원통</th>', html)
        n_head = len(data.with_groups(data.counted_classes()))
        self.assertEqual(n_head, len(self.summary()["counted_cols"]))

    def test_개수_줄은_묶음을_한_토막으로_접는다(self):
        det = data.detection_for_viewpoint(self.w.vp)
        items = {c["key"]: c for c in det["counts_list"]}
        self.assertIn("group:cylinder", items)
        g = items["group:cylinder"]
        self.assertEqual(g["label"], "원통")
        self.assertIn("RHZ", g["parts"])
        self.assertIn("DAC", g["parts"])
        self.assertNotIn("rhizosolenia", items, "안의 분류가 따로 또 나왔다")
        # 세지 않는 파편은 제 토막으로 남는다
        self.assertIn("cylinder_frag", items)

    def test_카탈로그_원통상_칩은_두_속을_함께_낸다(self):
        url = reverse("catalog", args=["g"])
        html = self.client.get(url).content.decode()
        self.assertIn("?cls=group:cylinder", html)
        rows = self.client.get(url + "?cls=group:cylinder").context["rows"]
        got = {r["cls"] for r in rows}
        self.assertEqual(got, {"rhizosolenia", "dactyliosolen"})

    def test_카탈로그_원통상에_파편을_켜면_파편도_나온다(self):
        url = reverse("catalog", args=["g"]) + "?cls=group:cylinder&frag=1"
        got = {r["cls"] for r in self.client.get(url).context["rows"]}
        self.assertIn("cylinder_frag", got)

    def test_산출_비교에_묶음_줄이_선다(self):
        ctx = data.compare_slides(["g"])
        keys = [r["key"] for r in ctx["rows"]]
        at = keys.index("group:cylinder")
        self.assertEqual(keys[at + 1], "rhizosolenia")
        g = _row(ctx, "group:cylinder")
        self.assertEqual(g["cells"][0]["n"],
                         _row(ctx, "rhizosolenia")["cells"][0]["n"]
                         + _row(ctx, "dactyliosolen")["cells"][0]["n"])
        # 검출 줄은 그대로 — 묶음이 분모에 다시 안 든다
        n = sum(r["cells"][0]["n"] for r in ctx["rows"] if not r.get("is_group"))
        self.assertEqual(ctx["cols"][0]["n_counted"], n)
