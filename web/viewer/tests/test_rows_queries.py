"""시야를 전부 훑는 자리의 **질의 수가 시야 수를 안 따라간다** (253).

계측 표·크롭·카탈로그는 `candidate_rows` 로 슬라이드의 시야를 다 훑는다. 그
안에서 검출마다·시야마다 되묻는 것이 셋 있었다 — 문턱(`det.thresholds`),
완료 표시(`review_state`), 묶음(`batch_ids_of`). `369cm` 한 판에 995번이었고
(검출 418개), 값은 전부 미리 당겨 올 수 있는 것이다.

첫 화면은 슬라이드마다 `_SUMMARY_SQL` 을 따로 불렀다 — 그 질의의 CTE 가 부를
때마다 DB 전체의 시야를 훑으므로 슬라이드 수만큼 같은 일을 했다.

**수를 못 박지 않는다.** "몇 번" 을 적어 두면 질의 하나를 더할 때마다 시험을
고치게 되고, 그러다 보면 수를 올려 적는 것이 버릇이 된다. 지키려는 것은
**자료가 늘어도 안 는다**이다.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data


def n_queries(fn):
    """`fn` 이 내는 질의 수. **한 번 불러 두고 잰다** — 분류·묶음처럼 프로세스가
    기억해 두는 조회가 첫 호출에만 붙어, 안 그러면 먼저 잰 쪽이 손해를 본다."""
    fn()
    with CaptureQueriesContext(connection) as ctx:
        out = fn()
    return len(ctx.captured_queries), out


class CandidateRowsQueriesTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        # 시야 수만 다르고 나머지가 같은 슬라이드 둘. 프레임에도 검출을 얹는다 —
        # 시야 하나에 검출이 여럿이어야 "검출마다 되묻는" 갈래가 드러난다.
        cls.small = fx.make_world(slug="small", sample_code="10cm",
                                  depth_cm=10.0, n_viewpoints=2)
        cls.big = fx.make_world(slug="big", sample_code="20cm",
                                depth_cm=20.0, n_viewpoints=7)
        for w in (cls.small, cls.big):
            for vp in w.viewpoints:
                fx.add_frame_detections(vp)
                fx.review_done(vp)

    def test_계측_표와_크롭이_보는_줄(self):
        a, rows_a = n_queries(lambda: data.candidate_rows("small"))
        b, rows_b = n_queries(lambda: data.candidate_rows("big"))
        self.assertTrue(rows_a)
        self.assertGreater(len(rows_b), len(rows_a))
        self.assertEqual(a, b, f"시야 2개에 {a}번, 7개에 {b}번 물었다")

    def test_카탈로그가_보는_줄(self):
        a, rows_a = n_queries(lambda: data.candidate_rows("small", all_images=True))
        b, rows_b = n_queries(lambda: data.candidate_rows("big", all_images=True))
        self.assertGreater(len(rows_b), len(rows_a))
        self.assertEqual(a, b, f"시야 2개에 {a}번, 7개에 {b}번 물었다")


class DatasetsSummaryQueriesTest(DiaRUGATestCase):

    def test_집계_SQL_은_슬라이드가_늘어도_한_벌이다(self):
        fx.make_classes()
        for i in range(4):
            w = fx.make_world(slug=f"s{i}", sample_code=f"{i}cm",
                              depth_cm=float(i))
            fx.review_done(w.vp)
        with CaptureQueriesContext(connection) as ctx:
            rows = data.datasets()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["n_detected"] for r in rows))
        # `_summary_rows` 한 번이 CTE 질의 둘이다(분류별 수 · 세는 시야 수)
        n = sum(1 for q in ctx.captured_queries if "WITH cnt AS" in q["sql"])
        self.assertEqual(n, 2, f"집계 SQL 을 {n}번 불렀다")
