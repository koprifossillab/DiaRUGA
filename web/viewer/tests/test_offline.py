"""오프라인 검토기·동정기 — 꺼내기 (P25 2·3·4단계).

## 무엇을 되살려서 잡나

- **바깥을 부르는 자리** — 파일 안에 `/img?`·`/crop?` 로 나가는 주소가 하나라도
  남으면 현장에서 사진이 백지가 된다. 서버 옆에서 열어 보면 **멀쩡히 보여서**
  눈으로는 못 잡는다. `_detection.html`·`_shots.html` 의 오프라인 갈래를 되돌리면
  이 시험이 실패한다
- **범위** — 고른 것만 실렸는가. 다 실어 보내면 파일이 몇 배가 되고, 덜 실으면
  현장에서 볼 것이 없다
- **지문** — 판마다 실렸는가. 없으면 반입이 충돌을 못 본다(P25 4절)
- **상한** — 시야가 너무 많으면 **굽기 전에** 막는가. 열어 보고서야 알면 그때는
  이미 현장이다
"""
import json
import re

from django.test import Client
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from ..models import RunBatch


class OfflineExportTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=3, n_candidates=2)

    def setUp(self):
        super().setUp()
        self.c = Client()

    def bake(self, **post):
        body = {"slug": "rs23", "kind": "review", "gids": ""}
        body.update(post)
        return self.c.post(reverse("offline_export"), body)

    def html(self, **post):
        r = self.bake(**post)
        self.assertEqual(r.status_code, 200, r.content[:400])
        return r.content.decode()

    def test_파일로_떨어진다(self):
        r = self.bake()
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(".html", r["Content-Disposition"])

    # **바깥으로 나가는 자리가 하나도 없다.** 서버 옆에서 열면 멀쩡히 보여
    # 눈으로는 못 잡는 고장이라, 자료가 아니라 **글자**로 본다.
    #
    # 부르는 것은 브라우저가 **속성을 보고** 한다 — JS 안의 문자열은 부르는
    # 것이 아니다(온라인용 기본 `env` 가 그 안에 그대로 있고, 아래
    # `test_오프라인_환경이_먼저_선다` 가 그것이 안 쓰이는 것을 본다).
    def test_바깥을_안_부른다(self):
        html = self.html()
        for bad in ('src="/', 'href="/', 'src="http', 'href="http',
                    'src="{% ', 'data-view="/', 'data-full="/'):
            self.assertNotIn(bad, html, f"오프라인 파일이 서버를 부른다: {bad}")
        # 사진은 파일 안에 있다
        self.assertIn('type="text/b64"', html)

    # **환경을 먼저 세운다.** 순서가 뒤집히면 온라인용 기본값(fetch)이 앉고,
    # 저장이 있지도 않은 서버로 나가 조용히 실패한다 — 화면은 "저장했습니다"
    # 라고 적지 않지만, 사람은 그것을 눌러 보고서야 안다.
    def test_오프라인_환경이_먼저_선다(self):
        html = self.html()
        mine = html.index("window.DiaRUGA = { env:")
        default = html.index("if (!window.DiaRUGA.env)")
        self.assertLess(mine, default,
                        "온라인용 기본 env 가 먼저 서면 저장이 서버로 나간다")

    def test_고른_범위만_실린다(self):
        html = self.html(gids="0-1")
        self.assertIn('id="sec-vp0"', html)
        self.assertIn('id="sec-vp1"', html)
        self.assertNotIn('id="sec-vp2"', html)

    def test_없는_시야는_거절한다(self):
        r = self.bake(gids="0,99")
        self.assertEqual(r.status_code, 400)
        self.assertIn("g99", r.content.decode())

    def test_너무_많으면_굽기_전에_막는다(self):
        from .. import offline
        r = self.bake(gids=f"0-{offline.MAX_VIEWPOINTS + 5}")
        self.assertEqual(r.status_code, 400)
        self.assertIn("나눠", r.content.decode())

    # 지문 둘이 판마다 실린다 — 반입이 이것으로 충돌을 본다 (P25 4절)
    def test_지문이_실린다(self):
        html = self.html()
        m = re.search(r'id="off-head">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m, "번들 머리가 없다")
        head = json.loads(m.group(1))
        self.assertEqual(head["slug"], "rs23")
        self.assertEqual(head["batch"],
                         RunBatch.objects.get(for_review=True).id)
        self.assertEqual(len(head["views"]), 3)
        for v in head["views"]:
            self.assertTrue(v["state"], "state 지문이 없다")
            self.assertTrue(v["keys"], "keys 지문이 없다")

    # **검토 화면 그대로를 쓴다** (P25 1절) — 배선이 실려 있고, 그리기는
    # 껍데기가 판을 열 때 부른다(`defer_init`).
    def test_검토_화면의_배선을_그대로_싣는다(self):
        html = self.html()
        self.assertIn("window.initDetView = function (uid)", html)
        self.assertNotIn('<script>initDetView(', html,
                         "오프라인은 열 때 부른다 — 파싱 시점에 부르면 안 된다")
        self.assertIn("window.OFFLINE", html)

    # 오프라인에는 갈 화면이 없다 — 그 길을 아예 안 놓는다 (P25 3.3)
    def test_카탈로그로_가는_길을_안_놓는다(self):
        html = self.html()
        self.assertNotIn("data-catalog-url", html)


class OfflineFingerprintTest(DiaRUGATestCase):
    """지문이 **무엇에 반응하나.** 너무 둔하면 남의 교정을 덮어쓰고,
    너무 예민하면 아무것도 반입이 안 된다."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_candidates=2)

    def fp(self):
        from .. import data, offline
        det = data.group_detail("rs23", self.w.vp.idx)["base_det"]
        return offline.state_fp(det), offline.keys_fp(det)

    def test_아무것도_안_바뀌면_같다(self):
        self.assertEqual(self.fp(), self.fp())

    def test_교정이_들어오면_state_가_바뀐다(self):
        was = self.fp()
        from .. import data
        rows = data.candidate_rows("rs23")
        fx.add_review(self.w.vp, rows[0]["key"], image=rows[0]["image_id"],
                      removed=True)
        now = self.fp()
        self.assertNotEqual(was[0], now[0], "지운 것이 지문에 안 잡힌다")
        self.assertEqual(was[1], now[1], "엔진 후보는 그대로인데 keys 가 바뀌었다")
