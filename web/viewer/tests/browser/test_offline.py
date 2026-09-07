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

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import ObjectReview


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
        self.assertTrue(out["bundle"]["views"][0]["fps"][0]["state"])

    # --- 왕복 --------------------------------------------------------------

    def test_내려받은_것을_그대로_되돌려_넣는다(self):
        """**여기까지가 한 흐름이다.** 굽기·검토·내려받기·반입 넷 중 어느 하나만
        어긋나도 사람이 하루 검토한 것이 안 들어간다 — 조각마다 시험이 있어도
        **이어 붙인 자리**는 여기서만 본다.
        """
        page = self.open_file(self.bake())
        self.click_image(70, 70, uid="vp0")
        page.keyboard.press("Space")
        page.wait_for_timeout(900)
        with page.expect_download() as got:
            page.click("#off-get")
        raw = Path(got.value.path()).read_bytes()

        c = Client()
        up = SimpleUploadedFile("r.json", raw, content_type="application/json")
        r = c.post(reverse("offline_import"), {"file": up})
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIn("지우기 +1", r.content.decode())
        self.assertFalse(ObjectReview.objects.filter(removed=True).exists(),
                         "미리보기가 DB 를 고쳤다")

        row = json.loads(raw.decode("utf-8"))["review"][0]
        r = c.post(reverse("offline_import"),
                   {"payload": raw.decode("utf-8"), "apply": "1",
                    "pick": [f'review:{row["gid"]}:{row["image"]}']})
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(ObjectReview.objects.filter(removed=True).count(), 1,
                         "오프라인에서 지운 것이 DB 로 안 들어왔다")

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

    # --- 프레임 (사용자 2026-09-07) -----------------------------------------

    def test_프레임이_다_실리고_넘길_수_있다(self):
        """**초점 시리즈를 못 넘기면 개체를 동정할 수 없다.**

        한 판에서 흐린 것이 다른 판에서 드러난다 — 그것이 이 화면에 캐러셀이
        있는 이유이고, 오프라인이라고 달라지지 않는다.
        """
        page = self.open_file(self.bake())
        shots = page.query_selector_all("#sec-vp0 .strip .shot")
        # 합성본 하나 + 프레임 셋 (`make_world` 의 기본)
        self.assertEqual(len(shots), 4, "캐러셀에 판이 다 안 실렸다")
        srcs = [s.get_attribute("data-view") for s in shots]
        self.assertTrue(all(u and u.startswith("blob:") for u in srcs),
                        f"판마다 그림이 안 붙었다: {srcs}")
        self.assertEqual(len(set(srcs)), 4, "판들이 같은 그림을 가리킨다")

        was = page.eval_on_selector("#img-vp0", "el => el.src")
        page.click('#sec-vp0 .striprow button[data-nav="nshot"]')
        page.wait_for_timeout(400)
        now = page.eval_on_selector("#img-vp0", "el => el.src")
        self.assertNotEqual(was, now, "다음 판으로 안 넘어갔다")
        self.assertTrue(page.eval_on_selector(
            "#img-vp0", "el => el.complete && el.naturalWidth > 0"),
            "넘긴 판의 사진이 안 실렸다")

    def test_판마다_교정이_따로_기록된다(self):
        """**판이 여럿이면 교정도 판마다다** (P09 1단계).

        시야로만 짚어 기록하면 프레임에서 한 교정이 합성본의 것을 밀어내고,
        마지막에 만진 판 하나만 살아남는다 — 화면은 아무 말도 안 한다.
        """
        fx.add_frame_detections(self.w.vp)      # 프레임마다 제 검출
        page = self.open_file(self.bake())
        self.click_image(70, 70, uid="vp0")
        page.keyboard.press("Space")
        page.wait_for_timeout(700)

        # 다음 판(프레임)으로 넘겨 거기서도 하나 지운다.
        # **넘긴 뒤에 사진을 화면 가운데로 되돌린다** — 캐러셀을 누르면 그쪽으로
        # 스크롤이 따라가서 사진이 화면 밖으로 밀리고, 그 자리를 누르면 아무
        # 일도 안 일어난다(시험만 그렇다 — 사람은 보이는 것을 누른다).
        frame = self.w.vp.frames.order_by("seq").first()
        page.click(f'#strip-vp0 .shot[data-detkey="{frame.name}"]')
        page.wait_for_timeout(250)
        self.masks_svg("vp0").scroll_into_view_if_needed()
        # **누른 단추에서 포커스를 뗀다.** 캐러셀 단추에 포커스가 남으면
        # `Space` 가 그 단추를 다시 누르고 삭제 단축키까지 못 간다 —
        # 시험만 겪는 자리다(사람은 사진을 눌러 고른 다음 누른다).
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.wait_for_timeout(150)
        self.assertIn("후보", page.text_content("#tabs-vp0 .tabmeta"))
        self.click_image(70, 70, uid="vp0")
        page.keyboard.press("Space")
        page.wait_for_timeout(900)

        with page.expect_download() as got:
            page.click("#off-get")
        out = json.loads(Path(got.value.path()).read_text(encoding="utf-8"))
        imgs = {r["image"] for r in out["review"]}
        self.assertEqual(len(out["review"]), 2,
                         f"판마다 한 줄이어야 한다: {out['review']}")
        self.assertEqual(len(imgs), 2, "두 줄이 같은 판을 가리킨다")
        for r in out["review"]:
            self.assertEqual(len(r["removed"]), 1, r)

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


class OfflineCatalogFileTest(BrowserTestCase):
    """동정기 — **크롭 카드에 종명을 적는다.**

    검토기와 배선이 다르다(마스크도 확대도 없다). 같아야 하는 것은 **기록의
    모양과 결과 파일**뿐이고, 그것을 `_offline_shell.html` 이 함께 들고 있다.
    """

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)
        fx.review_done(self.w.vp)          # 개체가 있어야 카드가 있다 (P18)

    def open_cards(self):
        r = Client().post(reverse("offline_export"),
                          {"slug": self.w.slug, "kind": "catalog", "gids": ""})
        self.assertEqual(r.status_code, 200, r.content[:400])
        path = Path(self._tmp) / f"off-cat-{self.uniq}.html"
        path.write_bytes(r.content)
        self.page.goto(f"file://{path}", wait_until="load")
        self.page.wait_for_timeout(300)
        return self.page

    def test_크롭이_붙는다(self):
        page = self.open_cards()
        n = len(page.query_selector_all(".ocard"))
        self.assertGreater(n, 0, "카드가 하나도 없다")
        self.assertTrue(page.eval_on_selector(
            ".ocard .ocrop img", "el => el.complete && el.naturalWidth > 0"),
            "크롭이 안 실렸다 — 파일 안의 base64 를 못 읽는다")

    def test_종명을_적으면_결과에_실린다(self):
        page = self.open_cards()
        page.fill(".ocard .sp", "Eucampia antarctica")
        page.wait_for_timeout(700)
        self.assertIn("바뀐 것", page.text_content("#off-state"))
        with page.expect_download() as got:
            page.click("#off-get")
        out = json.loads(Path(got.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(out["kind"], "catalog")
        self.assertEqual(len(out["catalog"]), 1, out["catalog"])
        self.assertEqual(out["catalog"][0]["species"], "Eucampia antarctica")

    # **등급·자세는 완형에만 매긴다** (`check_grade_pose`). 파편을 고르면 그
    # 줄이 화면에서 사라져야 한다 — 안 감추면 적어 놓고 반입에서 거절당한다.
    def test_초점을_넘기면_다른_크롭이_뜬다(self):
        """크롭도 판마다 한 장이다 — **초점 하나만 보고는 동정을 못 한다.**"""
        page = self.open_cards()
        was = page.eval_on_selector(".ocard .ocrop img", "el => el.src")
        label = page.text_content(".ocard .olabel")
        page.click('.ocard .ofocus button[data-d="1"]')
        page.wait_for_timeout(300)
        now = page.eval_on_selector(".ocard .ocrop img", "el => el.src")
        self.assertNotEqual(was, now, "초점을 넘겼는데 같은 그림이다")
        self.assertNotEqual(label, page.text_content(".ocard .olabel"),
                            "어느 판을 보고 있는지가 안 바뀐다")
        self.assertTrue(page.eval_on_selector(
            ".ocard .ocrop img", "el => el.complete && el.naturalWidth > 0"))

    def test_파편을_고르면_등급_자세가_사라진다(self):
        page = self.open_cards()
        frag = page.eval_on_selector(
            "#off-cls", "el => (JSON.parse(el.textContent)"
                        ".filter(c => !c.counted)[0] || {}).key")
        self.assertTrue(frag, "픽스처에 파편 분류가 없다 — 시험이 아무것도 안 본다")
        page.select_option(".ocard .cls", frag)
        page.wait_for_timeout(200)
        self.assertTrue(page.eval_on_selector(".ocard .gp", "el => el.hidden"))
