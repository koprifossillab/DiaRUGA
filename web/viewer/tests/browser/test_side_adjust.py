"""검토 화면 왼쪽 칸 — 화면 조정 줄 · 칸 구르기 · 분류 막대의 파편 빼기 (2026-10-30).

사용자가 고친 것.

- 화면 조정은 **한 줄에 기호 · 이름 · 슬라이더 · 값**. 채도를 더했고, 되돌리기는
  머리줄 오른쪽이다 — 접혀도 남아 켜진 것을 알린다
- **왼쪽 칸이 구른다.** 화면 조정과 조작법을 둘 다 펴면 아래가 잘려 안 보였다
  (`overflow: hidden`)
- 분류 막대에서 **파편을 빼고** 볼 수 있다 — 빼면 남은 막대끼리 길이를 다시 잰다

여기서 되살려서 잡는 것: 되돌리기가 `<summary>` 안이라 누를 때 판까지 접히는 것,
채도가 사진에 안 걸리는 것, 칸이 다시 잘리는 것, `[hidden]` 이 `.cbar` 의
`display: grid` 에 지는 것(063).
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class SideAdjustTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        # 후보 넷 = round · round_frag · rod · rod_frag — 파편 둘, 완형 둘
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=4)
        fx.review_done(self.w.vp)

    def review(self):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]))
        page.evaluate("() => { localStorage.removeItem('diaruga.imgadjust');"
                      " localStorage.removeItem('diaruga.cbnofrag'); }")
        page.reload()
        return page

    def test_한_줄에_기호_이름_슬라이더_값(self):
        page = self.review()
        rows = page.query_selector_all("#adj-stack .adjrow")
        self.assertEqual(len(rows), 3, "밝기·대비·채도 세 줄이어야 한다")
        for r in rows:
            name = r.query_selector(".an").bounding_box()
            rng = r.query_selector("input[type=range]").bounding_box()
            self.assertIsNotNone(r.query_selector("svg.ai"), "기호가 없다")
            self.assertLess(abs((name["y"] + name["height"] / 2)
                                - (rng["y"] + rng["height"] / 2)), 6,
                            "슬라이더가 이름 아래로 내려가 있다")
        self.assertEqual(page.query_selector_all(".adjnow"), [],
                         "머리줄에 값을 다시 적고 있다")

    def test_채도가_사진에_걸리고_되돌리기가_판을_안_접는다(self):
        page = self.review()
        page.eval_on_selector(
            "#sat-stack",
            "el => { el.value = 0; el.dispatchEvent(new Event('input')); }")
        f = page.eval_on_selector("#img-stack",
                                  "e => e.style.filter")
        self.assertIn("saturate(0%)", f)
        self.assertIn("0%", page.text_content("#satval-stack"))

        rst = page.query_selector("#adjreset-stack")
        self.assertIn("on", rst.get_attribute("class"))
        rst.click()
        page.wait_for_timeout(100)
        self.assertTrue(page.query_selector("#adjbox-stack").get_property("open").json_value(),
                        "되돌리기를 누르니 판이 접혔다")
        self.assertEqual(page.eval_on_selector("#sat-stack", "e => e.value"), "100")
        self.assertNotIn("on", rst.get_attribute("class") or "")

    def test_조작법을_다_펴도_칸이_구른다(self):
        page = self.review()
        page.set_viewport_size({"width": 1400, "height": 640})
        page.evaluate("() => document.querySelectorAll('#dvside-stack details')"
                      ".forEach(d => d.open = true)")
        side = page.query_selector("#dvside-stack")
        over = side.evaluate("e => [e.scrollHeight, e.clientHeight,"
                             " getComputedStyle(e).overflowY]")
        if over[0] <= over[1]:
            self.skipTest("이 화면 높이에서는 넘치지 않는다")
        self.assertEqual(over[2], "auto", "칸이 넘치는데 안 구른다")
        side.evaluate("e => e.scrollTop = e.scrollHeight")
        last = page.query_selector("#dvside-stack .sidefoot details:last-of-type")
        box, sb = last.bounding_box(), side.bounding_box()
        self.assertLessEqual(box["y"] + box["height"], sb["y"] + sb["height"] + 1,
                             "끝까지 굴려도 안내 끝이 안 보인다")

    def test_파편을_빼면_남은_막대끼리_다시_잰다(self):
        page = self.review()
        bars = page.query_selector_all("#cbars-stack .cbar")
        frag = [b for b in bars if b.get_attribute("data-frag")]
        whole = [b for b in bars if not b.get_attribute("data-frag")]
        self.assertTrue(frag and whole, "픽스처에 파편·완형이 다 있어야 한다")

        page.check("#cbnofrag-stack")
        for b in frag:
            self.assertFalse(b.is_visible(), "파편 막대가 그대로 보인다")
        widths = [b.eval_on_selector(".tr i", "e => e.style.width") for b in whole]
        self.assertIn("100%", widths, "남은 막대 중 가장 긴 것이 끝까지 안 찬다")

        page.reload()
        self.assertTrue(page.is_checked("#cbnofrag-stack"), "다시 열면 풀린다")
        page.uncheck("#cbnofrag-stack")
        # 다시 연 뒤라 앞에서 쥔 요소는 낡았다 — 새로 집는다
        self.assertTrue(all(b.is_visible() for b in
                            page.query_selector_all("#cbars-stack .cbar[data-frag]")),
                        "풀었는데 파편 막대가 안 돌아온다")
