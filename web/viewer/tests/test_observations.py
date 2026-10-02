"""관찰 합치기·가르기 (216).

같은 시료를 같은 조건으로 이틀에 나눠 찍으면 폴더가 둘이라 관찰이 둘로
생긴다(`260928_rs14-gc04_6cm` · `260930_rs14-gc04_6cm`). 그것을 하나로 본다.

지키는 것:

1. **교정이 안 사라진다** — 시야를 지우지 않고 옮긴다. 시야 합치기(215)와
   다른 점이 이것이다
2. **합쳐진 관찰은 빈 행으로 남는다.** 폴러가 그 폴더를 새것으로 알고 다시
   반입하지 않게 — 기본 관리자에서 감추면 그것이 조용히 깨진다
3. **목록·집계에서는 빠지고, 옛 주소는 받은 관찰로 간다**
4. **받는 쪽의 시야 번호는 그대로다**, 들어온 것은 뒤에 붙는다
5. **같은 시료끼리만**, 거절하면 아무것도 안 바뀐다
6. **가르기로 되돌리면 합치기 전과 같아진다** · 새 관찰로 뗄 수도 있다
7. 화면: 편집 화면의 칸 → 미리보기 → 확인. 렌더한 화면에서 값을 집어 보낸다
"""
import re

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data, observations as obs
from ..models import Frame, ObjectReview, Sample, Slide, Viewpoint


def _rename_frames(slide, base):
    """두 관찰의 사진 이름이 안 겹치게 — 운영에서는 카메라 일련번호가 다르다."""
    for n, f in enumerate(Frame.objects.filter(slide=slide)
                          .order_by("viewpoint__idx", "seq")):
        f.name = f"Snap-{base + n}"
        f.seq = n
        f.save(update_fields=["name", "seq"])


class ObservationMergeTest(DiaRUGATestCase):

    def setUp(self):
        fx.make_classes()
        # 같은 지역·지점·시료(get_or_create)에 관찰 둘 — 폴더가 다르다
        self.a = fx.make_world(slug="260928_rs23", n_viewpoints=2, n_frames=2)
        self.b = fx.make_world(slug="260930_rs23", n_viewpoints=2, n_frames=2)
        _rename_frames(self.a.slide, 30000)
        _rename_frames(self.b.slide, 31000)
        self.rev = fx.add_review(self.b.viewpoints[1],
                                 self.b.keys(self.b.viewpoints[1])[0],
                                 removed=True)
        self.c = Client()

    def _merge(self):
        return obs.apply_merge(self.a.slide, self.b.slug)

    # 1 ------------------------------------------------------------------
    def test_합쳐도_교정과_검출이_시야를_따라간다(self):
        vp = self.b.viewpoints[1]
        n_det = vp.detections.count()
        self._merge()
        vp.refresh_from_db()
        self.rev.refresh_from_db()
        self.assertEqual(vp.slide_id, self.a.slide.pk)
        self.assertEqual(self.rev.viewpoint_id, vp.pk)
        self.assertTrue(self.rev.removed)
        self.assertEqual(vp.detections.count(), n_det)
        self.assertEqual(ObjectReview.objects.count(), 1)

    # 2 ------------------------------------------------------------------
    def test_합쳐진_관찰은_폴더를_든_빈_행으로_남는다(self):
        self._merge()
        b = Slide.objects.get(slug=self.b.slug)
        self.assertEqual(b.merged_into_id, self.a.slide.pk)
        self.assertFalse(b.viewpoints.exists())
        self.assertFalse(b.frames.exists())
        # scan_nas 가 보는 그대로 — 기본 관리자가 이 행을 감추면 폴더가 다시 반입된다
        self.assertIn(b.image_dir,
                      set(Slide.objects.values_list("image_dir", flat=True)))

    # 3 ------------------------------------------------------------------
    def test_목록과_집계에서_빠지고_옛_주소는_받은_관찰로_간다(self):
        self._merge()
        slugs = [r["slug"] for r in data.datasets()]
        self.assertEqual(slugs, [self.a.slug])
        self.assertEqual(data.area_tabs()["tabs"][-1]["n"], 1)
        self.assertEqual([s.slug for s in self.a.slide.sibling_observations()], [])

        r = self.c.get(reverse("dataset", args=[self.b.slug]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(
            reverse("dataset", args=[self.a.slug])))
        r = self.c.get(reverse("group", args=[self.b.slug, 0]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(
            reverse("dataset", args=[self.a.slug])))
        r = self.c.get(reverse("dataset_edit", args=[self.b.slug]))
        self.assertEqual(r.status_code, 302)

    # 4 ------------------------------------------------------------------
    def test_받는_쪽_번호는_그대로이고_들어온_것은_뒤에_붙는다(self):
        a_pks = [vp.pk for vp in self.a.viewpoints]
        b_pks = [vp.pk for vp in self.b.viewpoints]
        self._merge()
        got = list(self.a.slide.viewpoints.order_by("idx")
                   .values_list("pk", "idx"))
        self.assertEqual(got, [(a_pks[0], 0), (a_pks[1], 1),
                               (b_pks[0], 2), (b_pks[1], 3)])
        names = list(Frame.objects.filter(slide=self.a.slide).order_by("seq")
                     .values_list("name", flat=True))
        self.assertEqual(names, ["Snap-30000", "Snap-30001", "Snap-30002",
                                 "Snap-30003", "Snap-31000", "Snap-31001",
                                 "Snap-31002", "Snap-31003"])
        # 들어온 시야가 검토 화면에서 열린다
        r = self.c.get(reverse("group", args=[self.a.slug, 3]))
        self.assertEqual(r.status_code, 200)

    # 5 ------------------------------------------------------------------
    def test_시료가_다르면_거절하고_아무것도_안_바꾼다(self):
        self.b.slide.sample = Sample.objects.create(
            locality=self.a.locality, code="72cm", depth_cm=72.0)
        self.b.slide.save(update_fields=["sample"])
        p = obs.merge_preview(self.a.slide, self.b.slug)
        self.assertFalse(p["ok"])
        with self.assertRaises(ValueError):
            self._merge()
        self.assertEqual(self.b.slide.viewpoints.count(), 2)
        self.assertIsNone(Slide.objects.get(slug=self.b.slug).merged_into_id)

    def test_사진_이름이_겹치면_거절한다(self):
        f = Frame.objects.filter(slide=self.b.slide).first()
        f.name = "Snap-30000"
        f.save(update_fields=["name"])
        p = obs.merge_preview(self.a.slide, self.b.slug)
        self.assertFalse(p["ok"])
        self.assertIn("겹칩니다", " ".join(p["errors"]))

    def test_처리_중인_관찰은_합치지_않는다(self):
        Slide.objects.filter(pk=self.b.slide.pk).update(state="processing")
        self.assertFalse(obs.merge_preview(self.a.slide, self.b.slug)["ok"])

    # 6 ------------------------------------------------------------------
    def test_합쳐진_관찰로_되돌리면_합치기_전과_같다(self):
        before = {vp.pk: vp.idx for vp in self.b.viewpoints}
        self._merge()
        self.assertEqual([t["value"] for t in obs.split_targets(self.a.slide)],
                         [obs.NEW, self.b.slug])
        r = obs.apply_split(self.a.slide, [2, 3], self.b.slug)
        self.assertFalse(r["created"])
        b = Slide.objects.get(slug=self.b.slug)
        self.assertIsNone(b.merged_into_id)
        self.assertEqual(dict(b.viewpoints.values_list("pk", "idx")), before)
        self.assertEqual(b.frames.count(), 4)
        self.assertEqual(self.a.slide.viewpoints.count(), 2)
        self.rev.refresh_from_db()
        self.assertEqual(self.rev.viewpoint.slide_id, b.pk)
        self.assertEqual(sorted(r["slug"] for r in data.datasets()),
                         sorted([self.a.slug, self.b.slug]))

    def test_새_관찰로_떼면_다음_번호로_생기고_남는_번호는_메운다(self):
        moved = self.a.viewpoints[0].pk
        kept = self.a.viewpoints[1].pk
        r = obs.apply_split(self.a.slide, [0], obs.NEW)
        self.assertTrue(r["created"])
        new = Slide.objects.get(slug=r["to"])
        self.assertEqual(new.sample_id, self.a.slide.sample_id)
        self.assertEqual(new.obs_no, 1)
        self.assertEqual(new.image_dir, self.a.slide.image_dir)
        self.assertEqual(list(new.viewpoints.values_list("pk", "idx")),
                         [(moved, 0)])
        self.assertEqual(list(self.a.slide.viewpoints.values_list("pk", "idx")),
                         [(kept, 0)])

    def test_시야를_전부_옮기는_가르기는_거절한다(self):
        p = obs.split_preview(self.a.slide, [0, 1], obs.NEW)
        self.assertFalse(p["ok"])

    # 7 ------------------------------------------------------------------
    def test_편집_화면의_칸으로_미리보고_합친다(self):
        url = reverse("dataset_edit", args=[self.a.slug])
        html = self.c.get(url).content.decode()
        form = html[html.index('id="obsops"'):]
        values = re.findall(r'name="other" value="([^"]+)"', form)
        self.assertEqual(values, [self.b.slug])

        go = reverse("merge_observation", args=[self.a.slug])
        r = self.c.post(go, {"other": values[0]})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "합친다")
        # 미리보기만으로는 안 바뀐다
        self.assertEqual(self.b.slide.viewpoints.count(), 2)

        r = self.c.post(go, {"other": values[0], "confirm": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.a.slide.viewpoints.count(), 4)

    def test_편집_화면의_칸으로_가른다(self):
        url = reverse("dataset_edit", args=[self.a.slug])
        html = self.c.get(url).content.decode()
        form = html[html.index('action="%s"' % reverse(
            "split_observation", args=[self.a.slug])):]
        idx = re.findall(r'name="idx" value="(\d+)"', form)
        self.assertEqual(idx, ["0", "1"])
        go = reverse("split_observation", args=[self.a.slug])
        r = self.c.post(go, {"idx": ["1"], "target": obs.NEW})
        self.assertEqual(r.status_code, 200)
        r = self.c.post(go, {"idx": ["1"], "target": obs.NEW, "confirm": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Viewpoint.objects.filter(slide=self.a.slide).count(), 1)
        self.assertEqual(self.c.get(r["Location"]).status_code, 200)

    def test_GET_으로는_안_움직인다(self):
        r = self.c.get(reverse("merge_observation", args=[self.a.slug]))
        self.assertEqual(r.status_code, 405)
