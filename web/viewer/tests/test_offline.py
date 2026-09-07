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
from unittest.mock import patch

from django.test import Client
from django.urls import reverse

from . import factories as fx
from .base import DiaRUGATestCase
from .. import data
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
            # **판마다 하나씩** — 교정이 `(이미지, 묶음)` 에 붙기 때문이다
            self.assertTrue(v["fps"], "판별 지문이 없다")
            for f in v["fps"]:
                self.assertTrue(f["image"])
                self.assertTrue(f["state"], "state 지문이 없다")
                self.assertTrue(f["keys"], "keys 지문이 없다")

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


class OfflinePickPanelTest(DiaRUGATestCase):
    """**꺼내는 자리는 일하는 화면 안이다** (사용자 2026-09-07).

    검토 화면에는 검토기를, 카탈로그 화면에는 동정기를 — 범위를 고르는 일은
    그 슬라이드를 보면서 하는 일이라, 목록에서 다시 고르게 하면 **방금 보던
    것과 다른 것을 꺼내는 자리**가 생긴다.
    """

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=3, n_candidates=2)
        # **카탈로그는 묶음 코드가 있어야 선다** — 번호의 꼬리가 그 코드다.
        # 없으면 그 화면이 통째로 잠기고(`blocked`), 잠긴 화면에서는 도구도
        # 안 꺼낸다(번호 없는 카드를 들고 나가게 된다).
        RunBatch.objects.filter(for_review=True).update(code="S1")
        for vp in cls.w.viewpoints:
            fx.review_done(vp)

    def setUp(self):
        super().setUp()
        self.c = Client()

    def get(self, url):
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.content.decode()

    def test_검토_화면에_검토기_꺼내기가_있다(self):
        gid = self.w.viewpoints[1].idx
        html = self.get(reverse("group", args=["rs23", gid]))
        self.assertIn('id="offpick-review"', html)
        self.assertIn('name="kind" value="review"', html)
        # **지금 보고 있는 시야가 기본 범위다** — 어디를 꺼낼지는 대개 지금
        # 보는 자리에서 정한다
        self.assertIn(f'value="{gid}"', html)
        self.assertIn('name="gids"', html)
        # 해상도는 검토기에만 있다 (동정기는 크롭이라 고를 것이 없다)
        self.assertIn('type="radio" name="px"', html)

    def test_카탈로그_화면에_동정기_꺼내기가_있다(self):
        html = self.get(reverse("catalog", args=["rs23"]))
        self.assertIn('id="offpick-catalog"', html)
        self.assertIn('name="kind" value="catalog"', html)
        # **고를 수 없는 것을 내보이지 않는다** — 크롭은 원본에서 잘라 내므로
        # 해상도를 고를 자리가 없다. 내보이면 눌러 놓고 아무 일도 안 일어난다.
        self.assertNotIn('type="radio" name="px"', html)

    # **자동 처리 중에는 안 놓는다** — 그때 꺼낸 파일로 검토해 봐야 반입이
    # 막힌다(`save_review` 가 409 로 물린다). 헛수고를 만들지 않는다.
    def test_처리_중에는_꺼내기가_없다(self):
        with patch.object(data, "review_blocked", return_value="처리 중입니다"):
            html = self.get(reverse("group", args=["rs23", self.w.vp.idx]))
            self.assertNotIn("offpick-review", html)
            html = self.get(reverse("catalog", args=["rs23"]))
            self.assertNotIn("offpick-catalog", html)

    # **다른 엔진을 보는 화면에도 안 놓는다** — 파일은 늘 검토 대상 묶음으로
    # 구워지므로 지금 보고 있는 것과 다른 것이 나온다(051 이 난 자리다).
    def test_다른_엔진_화면에는_꺼내기가_없다(self):
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        html = self.get(reverse("group", args=["rs23", self.w.vp.idx])
                        + f"?batch={run.id}")
        self.assertIn("읽기 전용", html)
        self.assertNotIn("offpick-review", html)

    # 되돌려 넣는 것만 한 자리로 온다 — 파일이 제가 어디서 왔는지를 들고 있다
    def test_올리는_화면에는_꺼내기_폼이_없다(self):
        html = self.get(reverse("offline"))
        self.assertIn("결과 올리기", html)
        self.assertNotIn('name="kind"', html)
        self.assertNotIn('name="gids"', html)
        self.assertNotIn("offpick-", html)


class OfflineFramesAndSizeTest(DiaRUGATestCase):
    """프레임을 다 담는가, 그리고 **크기를 미리 아는가** (사용자 2026-09-07)."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_frames=4,
                              n_candidates=2)

    def setUp(self):
        super().setUp()
        self.c = Client()

    def test_시야마다_합성본과_프레임이_다_담긴다(self):
        from .. import offline
        b = offline.review_bundle("rs23", [0, 1])
        for v in b["views"]:
            self.assertEqual(v["n_shots"], 5,
                             "합성본 하나 + 프레임 넷이 아니다")
            self.assertEqual(len(v["frames"]), 4)
            rels = {i["rel"] for i in v["imgs"]}
            self.assertEqual(len(rels), 5, "같은 사진을 두 번 담았다")

    def test_해상도를_고르면_담기는_사진이_달라진다(self):
        from .. import offline
        big = offline.review_bundle("rs23", [0], px="full")["n_bytes"]
        small = offline.review_bundle("rs23", [0], px="1600")["n_bytes"]
        # 픽스처 사진은 640px 이라 줄일 것이 없다 — **바이트가 아니라 폭이
        # 갈리는지**를 본다(실물에서 갈리는 것은 3겹이 볼 수 있는 자리가 아니다).
        self.assertEqual(offline.VIEW_PX["1600"]["w"], 1600)
        self.assertGreater(offline.VIEW_PX["full"]["w"], 2752)
        self.assertGreaterEqual(big, small)

    def test_크기를_굽기_전에_잰다(self):
        from .. import offline
        from ..models import Slide
        slide = Slide.objects.get(slug="rs23")
        est = offline.estimate(slide, [0, 1], "review", "full")
        self.assertEqual(est["n_views"], 2)
        self.assertEqual(est["n_shots"], 10, "판 수를 잘못 셌다")
        self.assertEqual(est["bytes"], 10 * offline.VIEW_PX["full"]["bytes"])

    def test_너무_크면_굽기_전에_막는다(self):
        """**다 굽고 나서 막지 않는다** — 그 시간이 통째로 버려진다."""
        from .. import offline
        with patch.object(offline, "MAX_BYTES", 1000):
            r = self.c.post(reverse("offline_export"),
                            {"slug": "rs23", "kind": "review", "gids": ""})
        self.assertEqual(r.status_code, 400)
        html = r.content.decode()
        self.assertIn("MB", html)
        self.assertIn("시야", html)


class OfflineCatalogExportTest(DiaRUGATestCase):
    """동정기 — **개체마다 크롭 한 장.** 시야 사진은 안 싣는다."""

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=2)
        # **카드는 개체 단위다** (P18) — 판정이 없는 후보에는 카드가 없다.
        for vp in cls.w.viewpoints:
            fx.review_done(vp)

    def setUp(self):
        super().setUp()
        self.c = Client()

    def html(self, gids=""):
        r = self.c.post(reverse("offline_export"),
                        {"slug": "rs23", "kind": "catalog", "gids": gids})
        self.assertEqual(r.status_code, 200, r.content[:400])
        return r.content.decode()

    def test_카드가_실리고_바깥을_안_부른다(self):
        html = self.html()
        self.assertIn('class="ocard"', html)
        for bad in ('src="/', 'href="/', 'src="http', 'href="http'):
            self.assertNotIn(bad, html, f"동정기가 서버를 부른다: {bad}")
        self.assertIn('type="text/b64"', html)

    # **검토 화면의 배선을 안 들인다** — 마스크도 확대도 없는 화면에 3,900줄을
    # 실을 이유가 없다. 파일 크기가 그만큼 커지고, 안 쓰는 배선이 도는 것을
    # 아무도 안 본다.
    def test_검토_배선을_안_싣는다(self):
        self.assertNotIn("window.initDetView", self.html())

    def test_카드마다_지문이_실린다(self):
        html = self.html()
        head = json.loads(re.search(r'id="off-head">(.*?)</script>',
                                    html, re.S).group(1))
        self.assertEqual(head["kind"], "catalog")
        self.assertTrue(head["cards"], "카드가 하나도 없다")
        for c in head["cards"]:
            self.assertTrue(c["fp"], "카드 지문이 없다")

    def test_고른_시야의_카드만_실린다(self):
        head = json.loads(re.search(r'id="off-head">(.*?)</script>',
                                    self.html(gids="0"), re.S).group(1))
        self.assertEqual({c["gid"] for c in head["cards"]}, {0})


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
