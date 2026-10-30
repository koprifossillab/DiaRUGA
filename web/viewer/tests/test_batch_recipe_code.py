"""묶음 코드를 정하는 문 — `ops/batch_recipe.py --code` (249).

묶음 코드는 카탈로그 번호의 꼬리다. **이미 정한 코드를 조용히 바꾸면 논문·표에 적힌
번호가 바뀐다** — 그래서 덮어쓰기는 `--force` 로만 되고, 다른 묶음과 겹치거나 손그림
자리(`M`)이면 거절한다.
"""
import importlib.util
import sys
from pathlib import Path

from .base import DiaRUGATestCase
from ..models import RunBatch

_PATH = Path(__file__).resolve().parents[3] / "ops" / "batch_recipe.py"


def _load():
    spec = importlib.util.spec_from_file_location("batch_recipe_under_test", _PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class SetCodeTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        cls.y3 = RunBatch.objects.create(kind="detect", label="yolo-3차", code="Y3")
        cls.y41 = RunBatch.objects.create(kind="detect", label="yolo-4.1차")

    def setUp(self):
        self.m = _load()

    def code(self, b):
        b.refresh_from_db()
        return b.code

    def test_빈_코드를_정한다(self):
        self.m.set_code(self.y41, " y41 ")
        self.assertEqual(self.code(self.y41), "Y41")

    def test_이미_정한_코드는_안_바꾼다(self):
        with self.assertRaises(SystemExit):
            self.m.set_code(self.y3, "Y30")
        self.assertEqual(self.code(self.y3), "Y3")
        self.m.set_code(self.y3, "Y30", force=True)
        self.assertEqual(self.code(self.y3), "Y30")

    def test_다른_묶음과_겹치면_거절한다(self):
        with self.assertRaises(SystemExit):
            self.m.set_code(self.y41, "Y3")
        self.assertEqual(self.code(self.y41), "")

    def test_손그림_자리는_못_쓴다(self):
        with self.assertRaises(SystemExit):
            self.m.set_code(self.y41, "m")
        self.assertEqual(self.code(self.y41), "")

    def test_영숫자가_아니면_거절한다(self):
        for bad in ["", "Y-41", "Y41Y41Y41"]:
            with self.assertRaises(SystemExit):
                self.m.set_code(self.y41, bad)
        self.assertEqual(self.code(self.y41), "")
