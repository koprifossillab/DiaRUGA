"""얼린 묶음의 정답 시야 — 검토 화면이 **되는 것처럼 보이지 않는가** (P32 ②).

서버는 저장 문마다 거절한다(`tests/test_frozen_batch.py`). 여기서 보는 것은 화면이
그 거절과 같은 말을 하는가다 — 저장만 막고 화면이 반응하면 사람이 한 시야를
헛검토한다(051).

얼린 시야는 읽기 전용 갈래(`?batch=`)와 **한 가지가 다르다**: 오른쪽 카탈로그 칸의
동정 다섯(유형·종명·등급·자세·코멘트)이 산다. 그래서 둘을 함께 본다 — 마스크 쪽이
잠기는가, 동정 칸은 열려 있고 **실제로 저장되는가**.

픽스처의 첫 통과분은 (40,50)에 60×40 이다.
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import ObjectReview, RunBatch, Viewpoint


class FrozenReviewScreenTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)
        rb = RunBatch.objects.get(for_review=True)
        RunBatch.objects.filter(pk=rb.pk).update(code="S1")
        fx.review_done(self.w.vp, rb)
        Viewpoint.objects.filter(pk=self.w.vp.pk).update(batch=rb)
        RunBatch.objects.filter(pk=rb.pk).update(frozen=True)
        self.key = self.w.keys()[0]

    def open_frozen(self):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]))
        page.wait_for_selector(".detview .box")
        return page

    def pick_first(self):
        self.click_image(40 + 30, 50 + 20)
        self.page.wait_for_timeout(200)

    def review_posts(self):
        posts = []
        self.page.on("request", lambda r: (
            posts.append(r.url)
            if r.method == "POST" and r.url.rstrip("/").endswith("/review")
            else None))
        return posts

    # --- 마스크 쪽은 잠긴다 --------------------------------------------------

    def test_얼림_표식과_까닭이_뜬다(self):
        page = self.open_frozen()
        self.assertIsNotNone(page.query_selector("#fz-stack"))
        self.assertTrue(page.is_visible("#roflag-stack"), "'Read only' 안내가 안 보인다")
        self.assertIn("정답 · 얼림", page.inner_text("#roflag-stack"))

    def test_도구와_완료줄이_안_보인다(self):
        """`getComputedStyle` 로 — 요소가 있느냐가 아니라 그려지느냐를 본다(051)."""
        page = self.open_frozen()
        for sel in (".tools", ".drawtool", ".donebar"):
            els = page.query_selector_all(sel)
            self.assertTrue(els, f"{sel} 가 화면에 없다 — 아무것도 안 보는 시험이 된다")
            for el in els:
                with self.subTest(sel=sel):
                    self.assertFalse(el.is_visible(), f"얼린 시야인데 {sel} 이 보인다")

    def test_키보드가_저장을_안_보낸다(self):
        """분류 단축키와 스페이스(오검출 삭제). 대조군은 `test_readonly` 의 보통
        화면이 이미 같은 조작으로 저장이 나가는 것을 보인다."""
        posts = self.review_posts()
        self.open_frozen()
        self.pick_first()
        for key in ("q", "w", "Space"):
            self.page.keyboard.press(key)
            self.page.wait_for_timeout(120)
        self.page.wait_for_timeout(1200)
        self.assertEqual(posts, [], f"얼린 시야인데 판 저장이 나갔다: {posts}")
        self.assertFalse(ObjectReview.objects.filter(
            viewpoint=self.w.vp, removed=True).exists())

    def test_우클릭에_고치는_항목이_없다(self):
        self.open_frozen()
        menu = self.context_menu_at(40 + 30, 50 + 20)
        self.assertIsNotNone(menu, "개체 위 우클릭인데 메뉴가 안 떴다")
        text = menu.inner_text()
        for word in ("오검출로 삭제", "되살리기", "실행취소"):
            self.assertNotIn(word, text, f"얼린 시야 메뉴에 '{word}' 가 있다:\n{text}")

    # --- 동정 칸은 산다 ------------------------------------------------------

    def test_동정_칸이_열려_있다(self):
        self.open_frozen()
        self.pick_first()
        self.assertTrue(self.page.query_selector("#catbox-stack").is_visible())
        for sel in ("#catsp-stack", "#catcls-stack", "#catnote-stack"):
            self.assertFalse(self.page.query_selector(sel).is_disabled(),
                             f"얼린 시야의 동정 칸이 잠겨 있다: {sel}")

    def test_종명이_저장된다(self):
        self.open_frozen()
        self.pick_first()
        self.page.fill("#catsp-stack", "Eucampia antarctica")
        self.page.wait_for_timeout(900)
        row = ObjectReview.objects.get(viewpoint=self.w.vp, mask_key=self.key)
        self.assertEqual(row.diatom_object.species, "Eucampia antarctica")

    def test_유형이_카탈로그_문으로_저장된다(self):
        """판 저장(`/review`)은 서버가 거절하므로 유형도 카탈로그 문으로 가야 한다.
        마스크 색까지 따라오는지 함께 본다."""
        posts = self.review_posts()
        self.open_frozen()
        self.pick_first()
        self.page.select_option("#catcls-stack", "rod")
        self.page.wait_for_timeout(900)
        obj = ObjectReview.objects.get(viewpoint=self.w.vp,
                                       mask_key=self.key).diatom_object
        self.assertEqual(obj.label, "rod")
        self.assertEqual(posts, [], "유형이 판 저장 문으로 갔다 — 서버가 거절한다")
        self.assertEqual(
            len(self.masks_svg().query_selector_all("polygon.rod")), 1,
            "유형을 지정했는데 마스크 색이 안 따라왔다")
