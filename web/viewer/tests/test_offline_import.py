"""오프라인 결과를 되돌려 넣는다 (P25 4·5단계).

`/review` 는 **그 판의 교정을 통째로 갈아치운다**(017·027). 오프라인 파일은
꺼낸 시점의 상태 위에서 만든 것이라, 그 사이 누가 온라인에서 같은 시야를
검토했으면 그 판단이 통째로 사라진다. 이 겹이 보는 것이 그 자리다.

## 무엇을 되살려서 잡나

- **지문 검사를 빼면** 남의 교정이 조용히 사라진다 (`test_그_사이_만졌으면_건너뛴다`)
- **키 지문 검사를 빼면** 재검출 뒤에도 옛 키를 넣으려 들고, `save_review` 가
  409 로 물린다 — 사람은 "왜 안 들어가는지" 를 모른다
- **두 걸음을 한 걸음으로 줄이면** 파일을 올리는 것만으로 DB 가 바뀐다
- **묶음 검사를 빼면** 다른 엔진의 판 위에서 한 교정이 들어간다 (051)
- 빈 `removed` 는 **"지운 것이 없다"** 는 말이다 — 되살림이 그렇게 간다(017)
"""
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data, offline
from ..models import Candidate, ObjectReview, RunBatch, ViewpointReview


class OfflineImportTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=3)

    def setUp(self):
        super().setUp()
        self.c = Client()
        self.gid = self.w.vp.idx

    # --- 재료 --------------------------------------------------------------

    def bundle(self):
        return offline.review_bundle("rs23", [v.idx for v in self.w.viewpoints])

    def keys(self, gid=None):
        det = data.group_detail("rs23", self.gid if gid is None else gid)["base_det"]
        return [data.cand_key(c) for c in det["candidates"]]

    def result(self, head=None, **parts):
        return {"diaruga_offline": 1, "kind": "review",
                "bundle": head or self.bundle()["head"],
                "saved_at": "2026-09-07T10:00:00Z", "by": "시험",
                "review": [], "done": [], "note": [], "catalog": [], **parts}

    def review_edit(self, removed=(), head=None, gid=None):
        b = self.bundle()
        gid = self.gid if gid is None else gid
        v = next(x for x in b["views"] if x["gid"] == gid)
        return b, {"gid": gid, "image": v["image"], "stem": v["det"]["stem"],
                   "slug": "rs23", "removed": list(removed), "accepted": [],
                   "labels": {}, "drawn": [], "edits": {}}

    def preview(self, res):
        up = SimpleUploadedFile("r.json",
                                json.dumps(res).encode("utf-8"),
                                content_type="application/json")
        r = self.c.post(reverse("offline_import"), {"file": up})
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r

    def apply(self, res, picks):
        r = self.c.post(reverse("offline_import"),
                        {"payload": json.dumps(res), "apply": "1",
                         "pick": list(picks)})
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r

    # --- 왕복 --------------------------------------------------------------

    def test_지운_것이_들어간다(self):
        key = self.keys()[0]
        b, e = self.review_edit(removed=[key])
        res = self.result(head=b["head"], review=[e])

        # 첫 걸음 — **보여 주기만 한다**
        html = self.preview(res).content.decode()
        self.assertIn("지우기 +1", html)
        self.assertFalse(ObjectReview.objects.filter(removed=True).exists(),
                         "미리보기가 DB 를 고쳤다")

        # 두 번째 걸음
        self.apply(res, [f"review:{self.gid}"])
        self.assertTrue(
            ObjectReview.objects.filter(mask_key=key, removed=True).exists(),
            "지운 것이 안 들어갔다")

    def test_안_고른_줄은_안_들어간다(self):
        key = self.keys()[0]
        b, e = self.review_edit(removed=[key])
        self.apply(self.result(head=b["head"], review=[e]), [])
        self.assertFalse(ObjectReview.objects.filter(removed=True).exists())

    # **빈 목록은 "지운 것이 없다" 는 말이다** (017). 되살림이 그 길로 간다 —
    # 여기가 통째로 갈아치우는 자리라, 지문이 같을 때만 그것이 옳다.
    def test_빈_목록이_되살린다(self):
        key = self.keys()[0]
        fx.add_review(self.w.vp, key, image=self.bundle()["views"][0]["image"],
                      removed=True)
        b, e = self.review_edit(removed=[])
        self.apply(self.result(head=b["head"], review=[e]),
                   [f"review:{self.gid}"])
        self.assertFalse(
            ObjectReview.objects.filter(mask_key=key, removed=True).exists(),
            "되살림이 안 들어갔다")

    def test_검토_완료가_들어간다(self):
        b = self.bundle()
        res = self.result(head=b["head"], done=[{"gid": self.gid, "done": True}])
        self.apply(res, [f"done:{self.gid}"])
        self.assertTrue(ViewpointReview.objects
                        .filter(viewpoint=self.w.vp, done=True).exists())

    # --- 막는 자리 셋 -------------------------------------------------------

    def test_그_사이_만졌으면_건너뛴다(self):
        """꺼낸 뒤에 **온라인에서 그 시야를 검토**했다."""
        key0, key1 = self.keys()[0], self.keys()[1]
        b, e = self.review_edit(removed=[key0])
        # 번들을 꺼낸 뒤에 다른 사람이 온라인에서 key1 을 지웠다
        fx.add_review(self.w.vp, key1, image=b["views"][0]["image"],
                      removed=True)

        html = self.preview(self.result(head=b["head"], review=[e])).content.decode()
        self.assertIn("만졌습니다", html)

        # **골라야 덮어쓴다** — 기본으로는 안 들어간다
        res = self.result(head=b["head"], review=[e])
        self.apply(res, [])
        self.assertTrue(
            ObjectReview.objects.filter(mask_key=key1, removed=True).exists(),
            "안 골랐는데 남의 교정이 사라졌다")

        # 골라서 넣으면 그때는 들어간다 (덮어쓴다)
        self.apply(res, [f"review:{self.gid}"])
        self.assertFalse(
            ObjectReview.objects.filter(mask_key=key1, removed=True).exists())

    def test_재검출이_돌았으면_거절한다(self):
        key = self.keys()[0]
        b, e = self.review_edit(removed=[key])
        # 후보 하나가 사라졌다 — 짚을 자리가 달라진 것이다
        Candidate.objects.filter(
            mask_key=self.keys()[2],
            detection__viewpoint=self.w.vp).delete()

        html = self.preview(self.result(head=b["head"], review=[e])).content.decode()
        self.assertIn("검출이 다시 돌았습니다", html)

        # **골라도 안 들어간다** — 사람이 고를 수 있는 일이 아니다
        self.apply(self.result(head=b["head"], review=[e]),
                   [f"review:{self.gid}"])
        self.assertFalse(ObjectReview.objects.filter(removed=True).exists())

    def test_묶음이_다르면_통째로_멈춘다(self):
        b, e = self.review_edit(removed=[self.keys()[0]])
        head = dict(b["head"], batch=(b["head"]["batch"] or 0) + 999)
        html = self.preview(self.result(head=head, review=[e])).content.decode()
        self.assertIn("넣을 수 없습니다", html)
        self.assertIn("묶음", html)

    def test_모르는_파일은_거절한다(self):
        up = SimpleUploadedFile("r.json", b"{}",
                                content_type="application/json")
        r = self.c.post(reverse("offline_import"), {"file": up})
        self.assertEqual(r.status_code, 400)
        self.assertIn("오프라인 결과 파일이 아닙니다", r.content.decode())

    # --- 동정 --------------------------------------------------------------

    def test_동정이_들어간다(self):
        """카드 하나는 **개체 단위로** 짚는다 — 저장 문이 좁다(`/catalog/save`)."""
        # 개체가 있어야 카드가 있다 — 검토 완료가 그것을 세운다
        fx.review_done(self.w.vp)
        b = offline.catalog_bundle("rs23", [self.gid])
        self.assertTrue(b["cards"], "카드가 하나도 없다")
        card = b["cards"][0]
        res = {"diaruga_offline": 1, "kind": "catalog", "bundle": b["head"],
               "saved_at": "2026-09-07T10:00:00Z", "by": "시험",
               "catalog": [{"gid": card["gid"], "image": card["image"],
                            "key": card["key"], "species": "Eucampia antarctica",
                            "grade": "A"}]}
        html = self.preview(res).content.decode()
        self.assertIn("Eucampia antarctica", html)
        self.apply(res, [f'cat:{card["gid"]}:{card["key"]}'])
        row = ObjectReview.objects.get(mask_key=card["key"],
                                       image_id=card["image"])
        self.assertEqual(row.species, "Eucampia antarctica")
        self.assertEqual(row.diatom_object.grade, "A")
