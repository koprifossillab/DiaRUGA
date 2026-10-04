"""시야 가르기·합치기 (2026-09-29).

**가르기 화면이 헷갈려 실제로 반대로 갈랐다.** `260928_rs14-gc04_6cm` 에서
30110 과 30111 사이(촬영 간격 26분)를 자르려고 30111 옆의 "여기서 가른다" 를
눌렀는데, 그 칸은 **그 사진 뒤**를 자르는 것이라 30111 이 앞 시야 끝에 붙었다.
다시 30110 에서 가르자 30111 이 혼자 떨어졌고, 되돌릴 합치기가 없었다.

그래서 지키는 것:

1. **자르는 칸은 사진 사이에 있고, 앞 사진의 이름을 싣는다.** 화면에서 "A 와 B
   사이" 칸을 켜면 B 가 새 시야의 첫 장이 된다 — 렌더한 화면에서 칸을 골라
   그대로 보내 본다(서버의 `after` 규칙과 화면의 배치가 어긋나면 여기서 잡힌다)
2. **한 장짜리 시야에도 합치기가 있다.** 떨어져 나온 한 장이 바로 합칠 대상이다
   — 옛 칸은 프레임이 하나면 통째로 감췄다
3. **이웃한 시야만 합친다**, 거절하면 아무것도 안 바뀐다
4. **갈랐다 합치면 프레임 묶음이 제자리로 온다**, 번호는 빈틈없이 다시 매긴다
5. **읽기 전용 화면에는 칸이 없다** (027·051)
6. **시야를 지우면 그 시야만 사라지고 사진 행은 남는다** (217). 번호는
   빈틈없이 다시 매기고, 검토를 잠그지 않는다. 마지막 시야는 못 지운다
"""
import re

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import regroup
from ..models import Frame, Image, Run, Stack


def _frame_sets(slide):
    return [[f.name for f in vp.frames.order_by("seq")]
            for vp in slide.viewpoints.order_by("idx")]


class RegroupTest(DiaRUGATestCase):

    def setUp(self):
        fx.make_classes()
        self.w = fx.make_world(slug="rs23", n_viewpoints=3, n_frames=4)
        self.slide = self.w.slide
        # 운영의 `seq` 는 **슬라이드 전체의 폴더 순서**다(group_focus_series).
        # 픽스처는 시야마다 0부터 매기므로 여기서 운영 모양으로 맞춘다
        for n, f in enumerate(Frame.objects.filter(slide=self.slide)
                              .order_by("viewpoint__idx", "seq")):
            f.seq = n
            f.save(update_fields=["seq"])
        self.c = Client()

    def _page(self, gid):
        r = self.c.get(reverse("group", args=[self.w.slug, gid]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    # 1 ------------------------------------------------------------------
    def test_사진_사이의_칸을_켜면_뒤_사진이_새_시야의_첫_장이_된다(self):
        html = self._page(0)
        strip = html[html.index('class="rg-strip"'):]
        strip = strip[:strip.index("</form>")]
        # 사진(alt)과 칸(value)을 화면에 놓인 순서대로
        toks = re.findall(r'name="after" value="([^"]+)"|alt="(\d+)"', strip)
        order = [("cut", v) if v else ("fr", a) for v, a in toks]
        self.assertEqual([k for k, _ in order],
                         ["fr", "cut", "fr", "cut", "fr", "cut", "fr"],
                         "칸이 사진 사이에 놓이지 않았다")
        # "21001 과 21002 사이" 칸 = 21002 바로 앞의 칸
        i = order.index(("fr", "21002"))
        kind, value = order[i - 1]
        self.assertEqual(kind, "cut")

        self.c.post(reverse("split_group", args=[self.w.slug, 0]),
                    {"after": [value], "confirm": "1"})
        self.assertEqual(_frame_sets(self.slide)[:2],
                         [["Snap-21000", "Snap-21001"],
                          ["Snap-21002", "Snap-21003"]])

    def test_칸에_촬영_간격을_적고_벌어진_자리를_표시한다(self):
        from datetime import datetime, timedelta, timezone
        t0 = datetime(2026, 9, 28, 16, 11, 40, tzinfo=timezone.utc)
        for f, dt in zip(self.w.vp.frames.order_by("seq"), (0, 3, 1550, 1554)):
            f.acquired_at = t0 + timedelta(seconds=dt)
            f.save(update_fields=["acquired_at"])
        html = self._page(0)
        cuts = re.findall(r'<label class="rg-cut( far)?".*?class="gap">([^<]*)<',
                          html, re.S)
        self.assertEqual(cuts, [("", "3초"), (" far", "25분 47초"), ("", "4초")])

    # 2 ------------------------------------------------------------------
    def test_한_장짜리_시야에도_합치기가_있다(self):
        regroup.apply_split(self.slide, ["Snap-21010", "Snap-21011"])
        self.slide.state = "done"
        self.slide.save(update_fields=["state"])
        solo = next(vp for vp in self.slide.viewpoints.all()
                    if vp.frames.count() == 1)
        html = self._page(solo.idx)
        self.assertIn(reverse("merge_group", args=[self.w.slug, solo.idx]), html)
        self.assertNotIn(reverse("split_group", args=[self.w.slug, solo.idx]),
                         html, "한 장은 가를 것이 없다")

    # 3 ------------------------------------------------------------------
    def test_떨어진_시야는_거절하고_아무것도_안_바꾼다(self):
        before = _frame_sets(self.slide)
        n_run = Run.objects.count()
        r = self.c.post(reverse("merge_group", args=[self.w.slug, 0]),
                        {"with": "2", "confirm": "1"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(_frame_sets(self.slide), before)
        self.assertEqual(Run.objects.count(), n_run)
        self.slide.refresh_from_db()
        self.assertEqual(self.slide.state, "done")

    def test_미리보기는_DB_를_안_건드린다(self):
        before = _frame_sets(self.slide)
        r = self.c.post(reverse("merge_group", args=[self.w.slug, 1]),
                        {"with": "0"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("합친 시야 · 사진 8장", r.content.decode())
        self.assertEqual(_frame_sets(self.slide), before)

    # 4 ------------------------------------------------------------------
    def test_합치면_하나가_되고_번호를_빈틈없이_다시_매긴다(self):
        r = self.c.post(reverse("merge_group", args=[self.w.slug, 1]),
                        {"with": "2", "confirm": "1"})
        self.assertRedirects(r, reverse("group", args=[self.w.slug, 1]),
                             fetch_redirect_response=False)
        self.assertEqual(_frame_sets(self.slide),
                         [[f"Snap-{21000 + s}" for s in range(4)],
                          [f"Snap-{21010 + s}" for s in range(4)]
                          + [f"Snap-{21020 + s}" for s in range(4)]])
        self.assertEqual(list(self.slide.viewpoints.order_by("idx")
                              .values_list("idx", flat=True)), [0, 1])
        merged = self.slide.viewpoints.get(idx=1)
        # 합성본은 묶음에서 나온 그림이라 새로 만든다 — 폴러가 채운다
        self.assertFalse(Stack.objects.filter(viewpoint=merged).exists())
        self.assertEqual(merged.n_frames, 8)
        # 이미지 행도 새 시야를 따라간다 (P06)
        self.assertEqual(Image.objects.filter(viewpoint=merged, kind="frame")
                         .count(), 8)
        self.slide.refresh_from_db()
        self.assertEqual(self.slide.state, "processing")

    def test_갈랐다_합치면_제자리로_온다(self):
        before = _frame_sets(self.slide)
        regroup.apply_split(self.slide, ["Snap-21011"])
        self.assertEqual(len(_frame_sets(self.slide)), 4)
        regroup.apply_merge(self.slide, [1, 2])
        self.assertEqual(_frame_sets(self.slide), before)

    # 5 ------------------------------------------------------------------
    def test_읽기_전용_화면에는_가르기도_합치기도_없다(self):
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        r = self.c.get(reverse("group", args=[self.w.slug, 0])
                       + f"?batch={run.pk}")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn("merge_group", html)
        self.assertNotIn(reverse("delete_group", args=[self.w.slug, 0]), html)
        self.assertNotIn(reverse("merge_group", args=[self.w.slug, 0]), html)
        self.assertNotIn(reverse("split_group", args=[self.w.slug, 0]), html)

    # 6 ------------------------------------------------------------------
    def test_화면의_지우기_단추로_미리보고_지운다(self):
        html = self._page(1)
        url = reverse("delete_group", args=[self.w.slug, 1])
        self.assertIn(url, html)
        before = _frame_sets(self.slide)
        r = self.c.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("사진 4장", r.content.decode())
        self.assertEqual(_frame_sets(self.slide), before, "미리보기가 DB 를 고쳤다")

        r = self.c.post(url, {"confirm": "1"})
        self.assertRedirects(r, reverse("group", args=[self.w.slug, 1]),
                             fetch_redirect_response=False)
        self.assertEqual(_frame_sets(self.slide), [before[0], before[2]])
        self.assertEqual(list(self.slide.viewpoints.order_by("idx")
                              .values_list("idx", flat=True)), [0, 1])
        # 사진 행은 남고 어느 시야에도 안 든다 — 이미지 행도 시야를 놓는다
        gone = Frame.objects.filter(slide=self.slide, name__in=before[1])
        self.assertEqual(gone.count(), 4)
        self.assertFalse(gone.filter(viewpoint__isnull=False).exists())
        self.assertFalse(Image.objects.filter(frame__in=gone,
                                              viewpoint__isnull=False).exists())
        # 새로 만들 시야가 없으니 검토를 잠그지 않는다
        self.slide.refresh_from_db()
        self.assertEqual(self.slide.state, "done")
        run = Run.objects.latest("pk")
        self.assertEqual(run.params["tool"], "regroup.apply_delete")
        self.assertEqual(run.params["frames"], before[1])

    def test_끝_시야를_지우면_앞_시야로_간다(self):
        r = self.c.post(reverse("delete_group", args=[self.w.slug, 2]),
                        {"confirm": "1"})
        self.assertRedirects(r, reverse("group", args=[self.w.slug, 1]),
                             fetch_redirect_response=False)

    def test_마지막_시야는_못_지운다(self):
        regroup.apply_delete(self.slide, 0)
        regroup.apply_delete(self.slide, 0)
        n_run = Run.objects.count()
        r = self.c.post(reverse("delete_group", args=[self.w.slug, 0]),
                        {"confirm": "1"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.slide.viewpoints.count(), 1)
        self.assertEqual(Run.objects.count(), n_run)

    def test_처리_중인_슬라이드는_거절한다(self):
        self.slide.state = "processing"
        self.slide.save(update_fields=["state"])
        r = self.c.post(reverse("delete_group", args=[self.w.slug, 1]),
                        {"confirm": "1"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.slide.viewpoints.count(), 3)
