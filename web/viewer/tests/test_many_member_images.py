"""멤버가 가리키는 이미지가 1,000 장을 넘어도 묶음을 읽는다 (228).

`prefetch_related("members__image")` 는 Django 5.2 에서 둘째 질의를
`"viewer_image"."id" = ? OR "viewer_image"."id" = ? …` 로 이어 붙인다. 이미지가
1,000 장을 넘으면 SQLite 의 식 깊이 한도에 걸려 `OperationalError: Expression
tree is too large (maximum depth 1000)` 로 죽는다. 10-21 v0.33.3 배포 뒤
`check_db` 8번이 운영에서 그렇게 죽었다 — 묶음 2,483 개의 멤버가 이미지 1,002 장을
가리킨 날이다. 17:00 사본에서는 1,000 장 아래라 안 났다.

**한도 바로 위를 세운다** — 이미지 1,002 장 · 개체 501 개 × 멤버 둘. 개체를 하나씩
세우는 문(`fx.new_review`)으로는 너무 느려서 `bulk_create` 로 만든다. 운영의 모양
(개체마다 대표 하나 · `(이미지, 묶음, 마스크 키)` 유일)은 지킨다.
"""
import importlib.util
import sys
from pathlib import Path

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data
from ..models import DiatomObject, Image, ObjectReview

N_OBJ = 501                      # × 2 멤버 = 이미지 1,002 장

_PATH = Path(__file__).resolve().parents[3] / "ops" / "check_db.py"


def _load_check_db():
    spec = importlib.util.spec_from_file_location("check_db_many_imgs", _PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class ManyMemberImagesTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_candidates=1)
        vp, batch = cls.w.vp, cls.w.detection().batch
        imgs = Image.objects.bulk_create([
            Image(viewpoint=vp, kind="frame", path=f"t228/f{i:04d}.jpg")
            for i in range(N_OBJ * 2)])
        objs = DiatomObject.objects.bulk_create([
            DiatomObject(viewpoint=vp, batch=batch) for _ in range(N_OBJ)])
        geom = {"bbox": [10, 10, 20, 20],
                "polygon": [10, 10, 30, 10, 30, 30, 10, 30]}
        ObjectReview.objects.bulk_create([
            ObjectReview(viewpoint=vp, image=imgs[2 * i + j], batch=batch,
                         mask_key=f"k{i}", geom=geom, diatom_object=o,
                         is_rep=(j == 0), source="engine", bind_method="exact")
            for i, o in enumerate(objs) for j in range(2)])

    def test_check_db_8번이_끝까지_돈다(self):
        mod = _load_check_db()
        mod.problems = []
        mod.check_links()                # 예외가 나면 실패다

    def test_카탈로그의_개체_사실(self):
        facts = data.object_facts(self.w.slide)
        self.assertGreaterEqual(len(facts), N_OBJ)

    def test_묶음의_대표_판(self):
        data.link_mains(self.w.slide)
