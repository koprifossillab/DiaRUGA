"""시야마다의 주 묶음과 얼린 묶음 (P31 · P32 · 0052).

**주 묶음** — 시야 하나를 보고 고치는 자리는 전부 `data.primary_batch_id` 로
묶음을 얻는다. 칸(`Viewpoint.batch`)이 차 있으면 그것, 비면 전역 검토 대상이 그
시야의 권역을 다룰 때 그것, 아니면 검출이 있는 가장 최근 묶음.

**얼린 묶음** — 회차의 정답이다. 그 시야에서는 모양·지우기·그리기·완료가 잠기고
카탈로그의 동정만 열린다. **잠그는 것은 서버다**(063) — 화면이 감추는 것과 별개로
저장 문마다 거절하는지를 여기서 본다.

세우는 모양:

| 시야 | 칸 | 보는 묶음 | 얼었나 |
|---|---|---|---|
| g0 | 검토 대상(`sam2-시험`) | 그것 · 완료 | 예 — 정답 |
| g1 | 비어 있음 | 검토 대상을 따라간다 | 예 — 따라간 묶음이 얼었다 |
| g2 | `yolo-열림` | 그것 | 아니오 |
"""
import json

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from .. import data, regroup
from ..models import (Detection, ObjectReview, RunBatch, Viewpoint,
                      ViewpointReview)


class FrozenBatchTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=3, n_candidates=3)
        cls.answer_vp, cls.loose_vp, cls.open_vp = cls.w.viewpoints
        cls.rb = RunBatch.objects.get(for_review=True)
        RunBatch.objects.filter(pk=cls.rb.pk).update(code="S1")

        # g2 는 얼지 않은 다른 묶음을 주 묶음으로 갖는다
        cls.other = fx.add_other_engine(cls.open_vp, label="yolo-열림",
                                        current=True, code="Y4")
        Viewpoint.objects.filter(pk=cls.open_vp.pk).update(batch=cls.other.batch)

        # g0 은 정답 — 완료하고 칸을 채운 뒤 묶음을 얼린다(0052 가 하는 그대로)
        fx.review_done(cls.answer_vp, cls.rb)
        Viewpoint.objects.filter(pk=cls.answer_vp.pk).update(batch=cls.rb)
        RunBatch.objects.filter(pk=cls.rb.pk).update(frozen=True)

    def setUp(self):
        self.c = Client()
        for vp in self.w.viewpoints:
            vp.refresh_from_db()

    # --- 거들 --------------------------------------------------------------

    def review(self, vp, expect, **extra):
        det = data.representative_detection(vp)
        p = {"stem": det.image_path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
             "slug": self.w.slug, "gid": vp.idx, "image": det.image_id,
             "removed": [], "accepted": [], "labels": {}, **extra}
        r = self.c.post(reverse("save_review"), data=json.dumps(p),
                        content_type="application/json")
        self.assertEqual(r.status_code, expect, r.content[:300])
        return r

    def catalog(self, vp, expect, **p):
        det = data.representative_detection(vp)
        body = {"gid": vp.idx, "image": det.image_id,
                "key": det.candidates.first().mask_key, **p}
        r = self.c.post(reverse("save_catalog", args=[self.w.slug]),
                        data=json.dumps(body), content_type="application/json")
        self.assertEqual(r.status_code, expect, r.content[:300])
        return r

    # --- 주 묶음 ------------------------------------------------------------

    def test_칸이_차_있으면_그것이다(self):
        self.assertEqual(data.primary_batch_id(self.answer_vp), self.rb.pk)
        self.assertEqual(data.primary_batch_id(self.open_vp), self.other.batch_id)

    def test_칸이_비면_검토_대상을_따른다(self):
        self.assertEqual(data.primary_batch_id(self.loose_vp), self.rb.pk)

    def test_한_번에_푸는_것도_같다(self):
        m = data.primary_batch_map(slide=self.w.slide)
        for vp in self.w.viewpoints:
            self.assertEqual(m[vp.pk], data.primary_batch_id(vp), vp)

    def test_검토_대상이_권역을_안_다루면_검출이_있는_묶음으로(self):
        """4차로 옮긴 뒤 한국의 새 슬라이드 — 4차 조리법이 거른다(`areas`)."""
        fx.add_other_engine(self.loose_vp, label="sam-한국", current=True)
        RunBatch.objects.filter(pk=self.rb.pk).update(recipe={"areas": ["kr"]})
        sam = RunBatch.objects.get(label="sam-한국")
        self.assertEqual(data.primary_batch_id(self.loose_vp), sam.pk)
        self.assertEqual(data.primary_batch_map(slide=self.w.slide)[self.loose_vp.pk],
                         sam.pk)

    def test_검토_대상이_권역을_다루면_검출이_없어도_따른다(self):
        """4차를 기다리는 남극 시야가 SAM 편집 화면으로 열리면 안 된다(RS14-GC04)."""
        # 다른 묶음을 먼저 쌓는다 — 쌓는 거들이 검토 대상의 검출에서 이미지를 얻는다
        fx.add_other_engine(self.loose_vp, label="sam-옛", current=True)
        Detection.objects.filter(viewpoint=self.loose_vp,
                                 run__batch=self.rb).delete()
        self.assertEqual(data.primary_batch_id(self.loose_vp), self.rb.pk)

    def test_화면과_저장이_같은_묶음을_본다(self):
        """g2 의 검토 화면은 `yolo-열림` 의 검출이다 — 저장도 거기 간다."""
        dets = data.current_detections(self.open_vp)
        self.assertTrue(dets)
        self.assertEqual({d.run.batch_id for d in dets}, {self.other.batch_id})
        self.review(self.open_vp, 200, removed=[dets[0].candidates.first().mask_key])
        self.assertTrue(ObjectReview.objects.filter(
            viewpoint=self.open_vp, batch=self.other.batch, removed=True).exists())

    def test_검토_화면이_주_묶음의_검출을_그린다(self):
        """전역 검토 대상으로 거른 채 시야를 당겨 오면 주 묶음의 검출이 안 남아
        빈 화면이 된다 — 한국·Smear 시야가 그렇게 열렸다(10-28 사본)."""
        d = data.group_detail(self.w.slug, self.open_vp.idx)
        self.assertEqual(d["base_det"]["batch_id"], self.other.batch_id)
        self.assertTrue(d["base_det"]["candidates"])
        self.assertFalse(d["base_det"].get("preview_only"))
        self.assertEqual(d["review_batch"], "yolo-열림")

    def test_시야_목록의_표지가_주_묶음의_판이다(self):
        g = {x["id"]: x for x in data.dataset_detail(self.w.slug)["groups"]}
        self.assertEqual(g[self.open_vp.idx]["n_detected"], 2)  # yolo-열림 은 둘
        self.assertFalse(g[self.open_vp.idx]["missing"])

    def test_카탈로그가_시야마다_자기_묶음을_낸다(self):
        rows = data.candidate_rows(self.w.slug)
        by_vp = {(r["group_id"], r["batch_id"]) for r in rows}
        self.assertIn((self.answer_vp.idx, self.rb.pk), by_vp)
        self.assertIn((self.open_vp.idx, self.other.batch_id), by_vp)
        self.assertNotIn((self.open_vp.idx, self.rb.pk), by_vp)

    def test_완료_수도_주_묶음으로_센다(self):
        self.assertEqual(data.done_viewpoints(slide=self.w.slide),
                         {self.answer_vp.pk})

    # --- 얼린 시야: 막는 것 -------------------------------------------------

    def test_교정_저장을_거절한다(self):
        before = ObjectReview.objects.filter(viewpoint=self.answer_vp).count()
        key = data.representative_detection(self.answer_vp).candidates.first().mask_key
        r = self.review(self.answer_vp, 409, removed=[key])
        self.assertIn("얼린", json.loads(r.content)["error"])
        self.assertEqual(
            ObjectReview.objects.filter(viewpoint=self.answer_vp).count(), before)
        self.assertFalse(ObjectReview.objects.filter(
            viewpoint=self.answer_vp, removed=True).exists())

    def test_따라간_묶음이_얼었어도_막는다(self):
        """칸이 빈 시야도 얼린 검토 대상을 보고 있으면 잠긴다 — 4차 검출 위에서 검토한다."""
        self.review(self.loose_vp, 409)

    def test_완료를_못_끈다(self):
        self.review(self.answer_vp, 409, only="done", done=False)
        self.assertTrue(ViewpointReview.objects.get(
            viewpoint=self.answer_vp, batch=self.rb).done)

    def test_시야_코멘트는_적힌다(self):
        self.review(self.answer_vp, 200, only="note", note="정답 시야 메모")
        self.assertEqual(data.review_state(self.answer_vp)[1], "정답 시야 메모")

    def test_카탈로그_지우기를_거절한다(self):
        self.catalog(self.answer_vp, 409, act="remove")
        self.assertFalse(ObjectReview.objects.filter(
            viewpoint=self.answer_vp, removed=True).exists())

    def test_카탈로그_동정은_받는다(self):
        self.catalog(self.answer_vp, 200, species="Eucampia antarctica")
        self.assertTrue(ObjectReview.objects.filter(
            viewpoint=self.answer_vp,
            diatom_object__species="Eucampia antarctica").exists())

    def test_카드가_지우기를_안_낸다(self):
        rows = [r for r in data.catalog_rows(self.w.slug)
                if r["group_id"] == self.answer_vp.idx]
        self.assertTrue(rows)
        self.assertTrue(all(r["frozen"] for r in rows))
        html = self.c.get(reverse("catalog", args=[self.w.slug])).content.decode()
        self.assertIn("정답 · 얼림", html)

    def test_번지기를_거절한다(self):
        det = data.representative_detection(self.answer_vp)
        r = self.c.post(
            reverse("spread_detection", args=[self.w.slug, self.answer_vp.idx]),
            data=json.dumps({"image": det.image_id,
                             "mask_key": det.candidates.first().mask_key}),
            content_type="application/json")
        self.assertEqual(r.status_code, 409, r.content[:300])

    def test_묶기를_거절한다(self):
        r = self.c.post(
            reverse("save_link", args=[self.w.slug, self.answer_vp.idx]),
            data=json.dumps({"act": "save", "members": []}),
            content_type="application/json")
        self.assertEqual(r.status_code, 409, r.content[:300])

    def test_정답_시야는_가르거나_지울_수_없다(self):
        _vp, bad = regroup.resolve_delete(self.w.slide, self.answer_vp.idx)
        self.assertTrue(any("얼린" in b for b in bad), bad)
        _vps, bad = regroup.resolve_merge(
            self.w.slide, [self.answer_vp.idx, self.loose_vp.idx])
        self.assertTrue(any("얼린" in b for b in bad), bad)

    def test_칸이_빈_시야는_가를_수_있다(self):
        """RS14-GC04 처럼 다시 갈라야 하는 시야 — 지킬 정답이 없다(215)."""
        _vp, bad = regroup.resolve_delete(self.w.slide, self.loose_vp.idx)
        self.assertEqual(bad, [])

    def test_한꺼번에_완료가_정답을_건너뛴다(self):
        out = data.mark_all_reviewed(self.w.slug, done=False)
        self.assertEqual(out["frozen"], 2)          # g0 정답 · g1 따라간 얼린 묶음
        self.assertTrue(ViewpointReview.objects.get(
            viewpoint=self.answer_vp, batch=self.rb).done)

    def test_문턱_적용을_거절한다(self):
        r = self.c.post(reverse("threshold_apply"), data=json.dumps({"values": {}}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 409, r.content[:300])

    # --- 검토 화면 ------------------------------------------------------------

    def page(self, vp):
        r = self.c.get(reverse("group", args=[self.w.slug, vp.idx]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_정답_시야는_얼림_표식으로_열린다(self):
        html = self.page(self.answer_vp)
        self.assertIn('id="fz-stack"', html)
        self.assertIn("얼린 묶음(sam2-시험)", html)
        self.assertNotIn('id="ro-stack"', html)      # 읽기 전용 갈래와 다른 자리다

    def test_정답_시야에는_가르기_칸이_없다(self):
        """서버가 거절하는 일을 화면이 되는 것처럼 보이면 안 된다(051)."""
        self.assertNotIn('name="after"', self.page(self.answer_vp))

    def test_칸이_빈_시야는_잠겨도_가르기_칸이_있다(self):
        html = self.page(self.loose_vp)
        self.assertIn('id="fz-stack"', html)
        self.assertIn('name="after"', html)

    def test_칸이_빈_시야를_정답이라_부르지_않는다(self):
        """다음 회차를 기다리는 시야다 — "정답" 이라 적으면 실제와 어긋난다."""
        html = self.page(self.loose_vp)
        self.assertIn("다음 회차의 검출을 기다립니다", html)
        self.assertNotIn("의 정답이라", html)

    def test_얼지_않은_시야에는_표식이_없다(self):
        self.assertNotIn('id="fz-stack"', self.page(self.open_vp))

    def test_다음_미검토가_얼린_시야를_건너뛴다(self):
        d = data.group_detail(self.w.slug, self.answer_vp.idx)
        self.assertEqual(d["todo_id"], self.open_vp.idx)

    # --- 얼지 않은 시야: 그대로 돈다 ----------------------------------------

    def test_얼지_않은_시야는_완료할_수_있다(self):
        self.review(self.open_vp, 200, only="done", done=True)
        self.assertTrue(ViewpointReview.objects.get(
            viewpoint=self.open_vp, batch=self.other.batch).done)


class CountReviewedOnlyTest(DiaRUGATestCase):
    """산출은 **검토를 마친 시야만, 시야마다 마지막으로 완료한 묶음의 기록으로** 센다
    (P31 ⑥ · P32 ③).

    검토 대상을 4차로 옮기는 순간을 그대로 세운다 — 3차에서 끝낸 g0 은 정답으로
    남고(칸 = 3차), g1 은 4차로 덮인다(칸이 비어 따라간다). 옮기기 전의 규칙(검토
    대상 묶음의 검출을 검토 여부와 상관없이 센다)이면 산출이 그 순간 엔진 숫자로
    뒤집힌다 — 369cm 가 검토분 8.2 · 미검토분 25.4 /시야였다(10-27).

    3차 검출은 시야마다 셋, 4차는 둘이다(`add_other_engine` 기본).
    """

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=3)
        cls.answer_vp, cls.covered_vp = cls.w.viewpoints
        cls.third = RunBatch.objects.get(for_review=True)
        fx.review_done(cls.answer_vp, cls.third)
        Viewpoint.objects.filter(pk=cls.answer_vp.pk).update(batch=cls.third)
        cls.fourth = None
        for vp in cls.w.viewpoints:
            run = fx.add_other_engine(vp, label="yolo-4차", current=True)
            cls.fourth = run.batch
        # 검토 대상을 4차로 옮긴다
        RunBatch.objects.update(for_review=False)
        RunBatch.objects.filter(pk=cls.fourth.pk).update(for_review=True)

    def setUp(self):
        for vp in self.w.viewpoints:                 # 칸을 DB 로만 바꿨다
            vp.refresh_from_db()

    def summary(self):
        return data._summary_by_sql(self.w.slide)

    def test_미검토_시야는_안_센다(self):
        s = self.summary()
        self.assertEqual(s["detected_groups"], 1)
        self.assertEqual(s["n_auto"], 3, "4차로 덮인 미검토 시야의 엔진 출력이 섞였다")

    def test_옮겨도_정답_시야는_3차_기록으로_센다(self):
        self.assertEqual(data.primary_batch_id(self.answer_vp), self.third.pk)
        self.assertEqual(self.summary()["n_auto"], 3)

    def test_4차에서_끝내면_4차_기록으로_들어온다(self):
        self.assertEqual(data.primary_batch_id(self.covered_vp), self.fourth.pk)
        fx.review_done(self.covered_vp, self.fourth)
        s = self.summary()
        self.assertEqual(s["detected_groups"], 2)
        self.assertEqual(s["n_auto"], 3 + 2)

    def test_더_최근_묶음의_완료가_이긴다(self):
        """같은 시야를 두 회차에서 다 끝냈으면 나중 회차다(묶음이 생긴 때)."""
        fx.review_done(self.answer_vp, self.fourth)
        self.assertEqual(self.summary()["n_auto"], 2)

    def test_비교_화면도_같은_규칙이다(self):
        col = data.compare_slides([self.w.slug])["cols"][0]
        self.assertEqual(col["detected_groups"], 1)

    def test_표지는_주_묶음의_판이다(self):
        """시야 목록의 표지 — 누르면 열리는 검토 화면과 같은 판이어야 한다."""
        _masks, n_kept = data._kept_masks(self.w.slide)
        self.assertEqual(n_kept.get(self.answer_vp.pk), 3)     # 3차 정답
        self.assertEqual(n_kept.get(self.covered_vp.pk), 2)    # 4차
