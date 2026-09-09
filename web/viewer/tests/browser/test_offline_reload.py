"""**새로고침해도 적어 둔 것이 화면에 있다** (195).

편집은 `localStorage` 에 남는데 **그것을 화면에 되살리는 코드가 없었다.**
목록의 ✓ 와 테두리만 바뀌고, 마스크·분류·종명은 구울 때 박아 둔 값 그대로였다.

**폰에서 훨씬 잘 터진다** — 큰 문서를 문 탭을 브라우저가 수시로 버린다.
돌아오면 지운 마스크가 살아 있고 적어 둔 종명이 빈 칸으로 보이는데, 그
자리에서 다시 검토해 저장하면 **아까 한 것이 그 판에서 밀려난다**(기록은 한
표적에 한 줄이라 마지막 것이 곧 상태다).

**이 겹이 아니면 볼 수 없다.** 3겹 시험은 구워 낸 글자를 보는데, 여기서 깨지는
것은 *두 번째로 열었을 때* 화면이 무엇을 그리는가다 — 파일은 한 글자도 안
바뀐다.
"""
import json
from pathlib import Path

from django.test import Client
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx

# 픽스처 개체(40,50 / 160,130 / 280,210)와 안 겹치는 빈 자리
PTS = [(420, 300), (500, 300), (500, 360), (420, 360)]


class OfflineReloadTest(BrowserTestCase):
    """검토기 — 지우기·그리기·분류가 새로고침을 넘어 산다."""

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)

    def open_bundle(self, kind="review"):
        r = Client().post(reverse("offline_export"),
                          {"slug": self.w.slug, "kind": kind, "gids": ""})
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.path = Path(self._tmp) / f"off-{kind}-{self.uniq}.html"
        self.path.write_bytes(r.content)
        self.page.goto(f"file://{self.path}", wait_until="load")
        self.page.wait_for_timeout(300)
        return self.page

    def reload(self):
        """**같은 파일을 다시 연다.** 폰이 탭을 버렸다 돌아오는 그 자리다."""
        self.page.reload(wait_until="load")
        self.page.wait_for_timeout(400)
        return self.page

    # --- 기억하는가 (이 자리가 서야 나머지가 뜻이 있다) ----------------------

    def test_브라우저가_기억한다(self):
        """`file://` 의 `localStorage` 가 막혀 있으면 아래 시험들이 전부
        **못 잡는 시험**이 된다 — 아무것도 안 남은 것을 "복원 안 됨" 으로 읽는다.
        껍데기가 그때 화면에 그렇게 적는데(`stored`), 그 글자로 가른다."""
        page = self.open_bundle()
        self.assertNotIn("기억하지 못합니다", page.text_content("#off-state"))

    # --- 지우기 ------------------------------------------------------------

    def test_지운_것이_새로고침해도_지워져_있다(self):
        page = self.open_bundle()
        self.click_image(70, 70, uid="vp0")          # 첫 개체 (40,50,60,40)
        page.keyboard.press("Space")
        page.wait_for_timeout(900)
        self.assertIn("삭제 1", page.text_content("#savestate-vp0"))

        self.reload()
        self.assertIn("바뀐 것 1건", page.text_content("#off-state"),
                      "기록 자체가 안 남았다")
        self.assertIn("삭제 1", page.text_content("#savestate-vp0") or "",
                      "지운 것이 새로고침에 되살아났다")
        self.assertEqual(len(page.query_selector_all("#sec-vp0 .box.gone")), 1,
                         "지운 표시가 화면에 안 얹혔다")

    def test_되살린_것은_되살아난_채로_돌아온다(self):
        """둘을 지우고 하나만 Ctrl+Z 로 되돌린다 — **기록에 없는 것도 상태다.**

        하나만 지우고 되돌리면 기록이 빈 목록이 되어, 되살리기가 고장 나 있어도
        통과한다(구운 자료에 지운 것이 원래 없다). **가르려면 둘이어야 한다.**
        """
        page = self.open_bundle()
        self.click_image(70, 70, uid="vp0")          # 첫 개체
        page.keyboard.press("Space")
        page.wait_for_timeout(500)
        self.click_image(190, 150, uid="vp0")        # 둘째 개체
        page.keyboard.press("Space")
        page.wait_for_timeout(500)
        page.keyboard.press("Control+z")             # 둘째만 되돌린다
        page.wait_for_timeout(900)

        self.reload()
        self.assertEqual(len(page.query_selector_all("#sec-vp0 .box.gone")), 1,
                         "되살린 것과 지운 것이 새로고침에 어긋났다")

    # --- 분류 --------------------------------------------------------------

    def test_지정한_분류가_새로고침해도_있다(self):
        page = self.open_bundle()
        self.click_image(70, 70, uid="vp0")
        page.keyboard.press("w")                     # 봉상 (`make_classes`)
        page.wait_for_timeout(900)
        self.assertTrue(page.query_selector("#sec-vp0 .box.rod.userset"),
                        "분류가 애초에 안 붙었다")

        self.reload()
        self.assertTrue(page.query_selector("#sec-vp0 .box.rod.userset"),
                        "지정한 분류가 새로고침에 사라졌다")

    # --- 그린 개체 ----------------------------------------------------------

    def test_그린_개체가_새로고침해도_있다(self):
        page = self.open_bundle()
        page.click('#dv-vp0 button[data-act="draw"]')
        page.wait_for_timeout(150)
        for x, y in PTS:
            self.click_image(x, y, uid="vp0")
        self.click_image(*PTS[0], uid="vp0")         # 첫 점을 다시 눌러 닫는다
        page.wait_for_timeout(900)
        self.assertTrue(page.query_selector("#sec-vp0 .box.orphan"))

        self.reload()
        self.assertTrue(page.query_selector("#sec-vp0 .box.orphan"),
                        "그린 개체가 새로고침에 사라졌다")

    # --- 되돌려 넣는 것이 여전히 맞는가 --------------------------------------

    def test_새로고침_뒤에_이어_해도_앞의_것이_안_밀린다(self):
        """**이것이 실제로 났던 고장이다.** 화면이 옛 상태로 서면, 그 자리에서
        한 다음 저장이 앞서 한 판단을 안 실어 보낸다 — 기록은 한 표적에 한
        줄이라 **마지막 것이 곧 상태**이기 때문이다.
        """
        page = self.open_bundle()
        self.click_image(70, 70, uid="vp0")          # 첫 개체를 지운다
        page.keyboard.press("Space")
        page.wait_for_timeout(900)

        self.reload()
        self.click_image(190, 150, uid="vp0")        # 둘째 개체 (160,130,60,40)
        page.keyboard.press("Space")
        page.wait_for_timeout(900)

        with page.expect_download() as got:
            page.click("#off-get")
        out = json.loads(Path(got.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(len(out["review"]), 1, out["review"])
        self.assertEqual(len(out["review"][0]["removed"]), 2,
                         "새로고침 앞에 지운 것이 결과에서 빠졌다")


class OfflineCatalogReloadTest(BrowserTestCase):
    """동정기 — 카드의 값이 새로고침을 넘어 산다."""

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)
        fx.review_done(self.w.vp)          # 개체가 있어야 카드가 있다 (P18)

    def open_cards(self):
        r = Client().post(reverse("offline_export"),
                          {"slug": self.w.slug, "kind": "catalog", "gids": ""})
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.path = Path(self._tmp) / f"off-cat-{self.uniq}.html"
        self.path.write_bytes(r.content)
        self.page.goto(f"file://{self.path}", wait_until="load")
        self.page.wait_for_timeout(300)
        return self.page

    def test_적어_둔_종명이_새로고침해도_카드에_있다(self):
        page = self.open_cards()
        page.fill(".ocard .sp", "Eucampia antarctica")
        page.wait_for_timeout(700)

        page.reload(wait_until="load")
        page.wait_for_timeout(400)
        self.assertEqual(
            page.eval_on_selector(".ocard .sp", "el => el.value"),
            "Eucampia antarctica",
            "적어 둔 종명이 새로고침에 빈 칸이 됐다")
        self.assertTrue(page.query_selector(".ocard.named"),
                        "종명이 있는데 카드 표시가 안 붙었다")

    def test_고른_유형이_새로고침해도_카드에_있다(self):
        """**유형은 `dataset` 으로 되돌린다** — 목록을 짜면서 그 값을 읽는다.
        칸에 직접 넣으면 짜는 자리에서 지워진다."""
        page = self.open_cards()
        # **구울 때 박힌 값과 다른 것을 고른다** — 같은 값을 고르면 되살리기가
        # 없어도 통과한다(카드가 원래 그 값을 들고 있다).
        was = page.eval_on_selector(".ocard", "el => el.dataset.cls || ''")
        pick = "rod" if was != "rod" else "round"
        page.select_option(".ocard .cls", pick)
        page.wait_for_timeout(700)

        page.reload(wait_until="load")
        page.wait_for_timeout(400)
        self.assertEqual(
            page.eval_on_selector(".ocard .cls", "el => el.value"), pick,
            "고른 유형이 새로고침에 사라졌다")
