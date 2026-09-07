"""오프라인 파일을 **진짜로 연다** (P25 3단계).

이 겹이 아니면 볼 수 없는 것들이다 — 3겹 시험은 글자만 본다.

- **사진이 붙는가.** base64 → Blob → 주소로 가는 길이 브라우저 안에만 있다.
  안 붙으면 화면은 뜨는데 백지다
- **저장이 기록으로 가는가.** `env` 를 갈아 끼우는 자리라 순서가 뒤집히면
  온라인용 `fetch` 가 앉고, 있지도 않은 서버로 나가 조용히 실패한다
- **결과 파일이 실제로 떨어지는가.** 그것이 이 프로그램의 유일한 산출물이다
- **시야를 넘나드는가.** 주소가 아니라 `#g<번호>` 이고, 판을 처음 열 때
  배선을 부른다(`defer_init`)

**`file://` 로 연다.** 서버 주소로 열면 없는 것을 부르고도 통과한다 —
현장에는 서버가 없다.
"""
import json
from pathlib import Path

from django.test import Client
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class OfflineReviewFileTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}",
                               n_viewpoints=2, n_candidates=3)

    def bake(self, kind="review", gids=""):
        """번들을 구워 **파일로 놓는다.** 여는 것은 `file://` 이다."""
        r = Client().post(reverse("offline_export"),
                          {"slug": self.w.slug, "kind": kind, "gids": gids})
        self.assertEqual(r.status_code, 200, r.content[:400])
        path = Path(self._tmp) / f"off-{kind}-{self.uniq}.html"
        path.write_bytes(r.content)
        return path

    def open_file(self, path):
        self.page.goto(f"file://{path}", wait_until="load")
        self.page.wait_for_timeout(300)
        return self.page

    # --- 사진과 마스크 -----------------------------------------------------

    def test_사진이_붙고_마스크가_그려진다(self):
        page = self.open_file(self.bake())
        src = page.eval_on_selector("#img-vp0", "el => el.src")
        self.assertTrue(src.startswith("blob:"), f"사진 주소가 이상하다: {src[:40]}")
        loaded = page.eval_on_selector(
            "#img-vp0", "el => el.complete && el.naturalWidth > 0")
        self.assertTrue(loaded, "사진이 안 실렸다 — 파일 안의 base64 를 못 읽는다")
        self.assertGreater(
            len(page.query_selector_all("#masks-vp0 polygon")), 0,
            "마스크가 하나도 안 그려졌다")

    # --- 저장이 기록으로 간다 ----------------------------------------------

    def test_지우면_기록으로_남는다(self):
        page = self.open_file(self.bake())
        self.click_image(70, 70, uid="vp0")          # 첫 개체 (40,50,60,40)
        page.keyboard.press("Space")
        page.wait_for_timeout(900)                   # 지연 저장이 나갈 때까지
        self.assertIn("바뀐 것", page.text_content("#off-state"))
        # **저장 실패 띠가 뜨면 안 된다** — 온라인용 `fetch` 가 앉았다는 뜻이다
        self.assertNotIn("저장하지 못했습니다",
                         page.text_content("#savestate-vp0") or "")

    def test_결과를_내려받는다(self):
        page = self.open_file(self.bake())
        self.click_image(70, 70, uid="vp0")
        page.keyboard.press("Space")
        page.wait_for_timeout(900)
        with page.expect_download() as got:
            page.click("#off-get")
        out = json.loads(Path(got.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(out["diaruga_offline"], 1)
        self.assertEqual(out["kind"], "review")
        self.assertEqual(out["bundle"]["slug"], self.w.slug)
        self.assertEqual(len(out["review"]), 1, out["review"])
        row = out["review"][0]
        self.assertEqual(row["gid"], 0)
        self.assertEqual(len(row["removed"]), 1, "지운 것이 안 실렸다")
        # **지문은 머리에 있다** — 반입이 그것으로 충돌을 본다
        self.assertTrue(out["bundle"]["views"][0]["state"])

    # --- 시야 넘나들기 ------------------------------------------------------

    def test_시야를_넘기면_그때_그린다(self):
        page = self.open_file(self.bake())
        # 처음에는 첫 시야만 그려져 있다 (`defer_init`)
        self.assertEqual(len(page.query_selector_all("#masks-vp1 polygon")), 0,
                         "안 연 시야를 미리 그렸다")
        page.click('#off-list button[data-gid="1"]')
        page.wait_for_timeout(400)
        self.assertFalse(page.eval_on_selector("#sec-vp1", "el => el.hidden"))
        self.assertTrue(page.eval_on_selector("#sec-vp0", "el => el.hidden"))
        self.assertGreater(len(page.query_selector_all("#masks-vp1 polygon")), 0,
                           "넘긴 시야에 마스크가 안 그려졌다")
        self.assertTrue(page.eval_on_selector(
            "#img-vp1", "el => el.complete && el.naturalWidth > 0"),
            "넘긴 시야의 사진이 안 실렸다")

    # --- 없어야 하는 것 -----------------------------------------------------

    def test_판을_건너다니는_도구가_없다(self):
        """`/spread`·`/link` 는 판이 여럿일 때의 일이라 이 파일에 뜻이 없다.

        **저장을 막는 것으로 끝내지 않는다** — 화면에 있으면 사람이 누르고,
        누르면 된 줄 안다 (051).
        """
        page = self.open_file(self.bake())
        self.click_image(70, 70, uid="vp0")
        menu = self.context_menu_at(70, 70, uid="vp0")
        self.assertIsNotNone(menu, "우클릭 메뉴가 안 뜬다")
        text = menu.text_content()
        self.assertNotIn("앉히기", text)
        self.assertNotIn("카드로", text)
