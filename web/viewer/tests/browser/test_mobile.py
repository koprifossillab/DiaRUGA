"""폰·태블릿에서 검토와 동정을 한다 (192).

**데스크탑에만 있는 것으로 만들어져 있었다** — 휠 확대, 우클릭 드래그 이동,
우클릭 메뉴, hover 말풍선, 그리고 사진 옆의 250px 짜리 칸. 손가락에는 그중
아무것도 없고, 폰에서는 사진이 반으로 준다.

## 무엇을 되살려서 잡나

- **핀치 확대**를 빼면 손가락으로는 확대할 길이 아예 없다 — areolae 를 보려면
  확대가 필요하고, 그것이 동정의 전부다
- **길게 누르기**를 빼면 삭제·유형 지정 메뉴에 닿을 수 없다. Chrome 은
  `contextmenu` 를 내주는데 화면이 그것을 **막기만 하고 있었다**
- **탭이 선택으로 가는 길**을 우리가 가로채면(손가락 이벤트를 통째로 먹으면)
  개체를 고를 수가 없다 — 그래서 이동·확대로 판정한 다음에만 막는다
- 오른쪽 칸이 **아래로 안 내려오면** 폰에서 사진이 반이 된다
"""
from pathlib import Path

from django.test import Client
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx

# 픽스처 첫 개체 (40,50,60,40) 의 한가운데
OBJ = (70, 70)


class MobileTestCase(BrowserTestCase):
    """**폰 크기 · 손가락 있는 화면**으로 연다.

    바닥이 세워 준 창을 닫고 다시 연다 — `has_touch` 는 컨텍스트를 만들 때만
    정할 수 있고, 그것이 없으면 `touchstart` 도 `pointerType: 'touch'` 도
    아예 안 난다(즉 **시험이 아무것도 안 보고 통과한다**).
    """

    def setUp(self):
        super().setUp()
        self.ctx.close()
        self.ctx = self._browser.new_context(
            viewport={"width": 412, "height": 915}, has_touch=True,
            is_mobile=True, device_scale_factor=2)
        self.page = self.ctx.new_page()
        self.page.on("pageerror",
                     lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: (
            self.errors.append(f"console.error: {m.text}")
            if m.type == "error" else None))

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=3)

    def review(self):
        return self.open(reverse("group", args=[self.w.slug, self.w.vp.idx]))


class MobileLayoutTest(MobileTestCase):

    def test_오른쪽_칸이_사진_아래로_내려온다(self):
        page = self.review()
        view = page.query_selector("#dv-stack").bounding_box()
        notes = page.query_selector("#notes-stack").bounding_box()
        self.assertGreater(notes["y"], view["y"],
                           "오른쪽 칸이 아직 사진 옆에 있다 — 폰에서 사진이 반이 된다")
        self.assertGreater(notes["width"], view["width"] * 0.8,
                           "아래로 내려왔는데 폭이 안 늘었다")

    def test_카탈로그_카드가_한_줄에_하나다(self):
        fx.review_done(self.w.vp)
        page = self.open(reverse("catalog", args=[self.w.slug]))
        cards = page.query_selector_all(".catcard")
        self.assertGreater(len(cards), 1, "카드가 하나면 열이 안 갈린다")
        xs = {round(c.bounding_box()["x"]) for c in cards}
        self.assertEqual(len(xs), 1, f"폰인데 카드가 여러 열이다: {xs}")

    # **가로로 밀리면 안 된다.** 세로로만 넘기는 화면에서 가로 스크롤이 생기면
    # 사진이 화면 밖으로 나가고, 그것을 되돌릴 손잡이가 없다. 폭을 안 다스린
    # 요소 하나가 화면 전체를 그렇게 만든다.
    def assert_no_sideways(self, page, where):
        over = page.evaluate(
            "() => document.documentElement.scrollWidth - window.innerWidth")
        self.assertLessEqual(over, 1, f"{where} 가 가로로 {over}px 밀린다")

    def test_화면이_가로로_안_밀린다(self):
        page = self.review()
        self.assert_no_sideways(page, "검토 화면")
        fx.review_done(self.w.vp)
        page = self.open(reverse("catalog", args=[self.w.slug]))
        self.assert_no_sideways(page, "카탈로그 화면")

    def test_꺼내기_패널을_펴도_안_밀린다(self):
        """패널은 검토·동정을 시작하는 자리다 — 거기서 밀리면 범위 칸에
        닿을 수가 없다."""
        page = self.review()
        page.click("#offpick-review > summary")
        page.wait_for_timeout(200)
        self.assert_no_sideways(page, "꺼내기 패널을 편 검토 화면")
        self.assertTrue(page.is_visible('#offpick-review input[name="gids"]'))


class MobileTouchTest(MobileTestCase):

    def tap(self, img_x, img_y):
        x, y = self.image_point(img_x, img_y)
        self.page.touchscreen.tap(x, y)
        self.page.wait_for_timeout(200)

    def test_탭이_개체를_고른다(self):
        """**탭은 가로채지 않는다** — 브라우저가 마우스 이벤트로 바꿔 주는 길을
        그대로 쓴다. 우리가 먹으면 선택·되살리기·펼침을 전부 다시 적어야 하고,
        두 벌이 되면 조용히 어긋난다."""
        page = self.review()
        self.tap(*OBJ)
        self.assertIn("선택", page.text_content("#selinfo-stack"))
        self.assertNotIn("선택 없음", page.text_content("#selinfo-stack"))

    # **조작 안내가 거짓말을 하면 안 된다.** 휠도 우클릭도 없는 자리에서
    # "휠 = 확대" 를 읽으면, 사람은 자기 손가락이 아니라 화면을 의심하지
    # 않는다 — 되는 방법을 안 찾고 안 되는 방법을 계속 시도한다.
    def test_손가락_화면에는_손가락_안내가_뜬다(self):
        page = self.review()
        self.assertTrue(page.is_visible(".touchhint"), "손가락 안내가 안 뜬다")
        self.assertFalse(page.is_visible(".mousehint"),
                         "손가락 화면에 마우스 안내가 떠 있다")
        self.assertIn("길게 누르기", page.text_content(".touchhint"))
        # 단축키 줄도 안 낸다 — 키보드가 없는 자리에서 가리킬 것이 없다
        self.assertFalse(page.is_visible("#keyhint-stack"))

    def test_두_손가락으로_확대한다(self):
        page = self.review()
        was = page.text_content("#zoom-stack")
        page.evaluate("""() => {
          const el = document.getElementById('dv-stack');
          const t = (x, y, id) => new Touch(
            {identifier: id, target: el, clientX: x, clientY: y});
          const fire = (name, a, b) => el.dispatchEvent(new TouchEvent(name, {
            touches: b ? [a, b] : [], targetTouches: b ? [a, b] : [],
            changedTouches: b ? [a, b] : [a],
            bubbles: true, cancelable: true}));
          const r = el.getBoundingClientRect();
          const cy = r.top + r.height / 2;
          fire('touchstart', t(r.left + 120, cy, 1), t(r.left + 200, cy, 2));
          fire('touchmove',  t(r.left + 40,  cy, 1), t(r.left + 280, cy, 2));
          fire('touchend',   t(r.left + 40,  cy, 1));
        }""")
        page.wait_for_timeout(200)
        self.assertNotEqual(was, page.text_content("#zoom-stack"),
                            "두 손가락을 벌렸는데 배율이 그대로다")

    def test_길게_누르면_메뉴가_뜬다(self):
        """Chrome 은 길게 누르면 `contextmenu` 를 내준다 — 화면이 그것을
        **막기만 하고 있었다.** 이 길이 없으면 손가락으로는 삭제도 유형
        지정도 할 수 없다."""
        page = self.review()
        self.tap(*OBJ)                       # 먼저 고른다 (손가락으로 눌렀다는 표시도 여기서)
        x, y = self.image_point(*OBJ)
        page.evaluate("""([x, y]) => {
          document.getElementById('dv-stack').dispatchEvent(
            new MouseEvent('contextmenu',
              {clientX: x, clientY: y, bubbles: true, cancelable: true}));
        }""", [x, y])
        page.wait_for_timeout(250)
        menu = page.query_selector(".ctxmenu")
        self.assertIsNotNone(menu, "길게 눌러도 메뉴가 안 뜬다")
        self.assertIn("오검출로 삭제", menu.text_content())


class MobileOfflineFileTest(MobileTestCase):
    """오프라인 파일도 폰에서 열린다 (P25 · 192).

    **여기가 진짜 자리다** — 현장에 들고 나가는 것이 이 파일이고, 그때 손에
    있는 것은 폰이다. 파일은 `base.html` 을 그대로 쓰므로 화면 폭 규칙도
    함께 따라온다.
    """

    def bake(self, kind="review"):
        r = Client().post(reverse("offline_export"),
                          {"slug": self.w.slug, "kind": kind, "gids": "",
                           "px": "1600"})
        self.assertEqual(r.status_code, 200, r.content[:300])
        path = Path(self._tmp) / f"m-{kind}-{self.uniq}.html"
        path.write_bytes(r.content)
        self.page.goto(f"file://{path}", wait_until="load")
        self.page.wait_for_timeout(400)
        return self.page

    def over(self):
        return self.page.evaluate(
            "() => document.documentElement.scrollWidth - window.innerWidth")

    def test_오프라인_검토기가_폰에서_선다(self):
        page = self.bake("review")
        self.assertTrue(page.eval_on_selector(
            "#img-vp0", "el => el.complete && el.naturalWidth > 0"),
            "사진이 안 실렸다")
        self.assertLessEqual(self.over(), 1, "가로로 밀린다")
        view = page.query_selector("#dv-vp0").bounding_box()
        notes = page.query_selector("#notes-vp0").bounding_box()
        self.assertGreater(notes["y"], view["y"], "오른쪽 칸이 아직 옆에 있다")

    def test_크롭을_옆으로_그어_초점을_넘긴다(self):
        """단추는 작고, 초점을 훑는 일은 손이 자주 가는 자리다.

        **세로는 안 가로챈다** — 그것은 화면 넘기기다. 카드 위에서 화면이
        안 움직이면 아래 카드로 갈 수가 없다.
        """
        fx.review_done(self.w.vp)
        page = self.bake("catalog")
        was = page.text_content(".ocard .olabel")
        box = page.query_selector(".ocard .ocrop").bounding_box()
        y = box["y"] + box["height"] / 2
        page.touchscreen.tap(box["x"] + box["width"] * 0.8, y)   # 손가락 화면임을 알린다
        page.evaluate("""([x0, x1, y]) => {
          const el = document.querySelector('.ocard .ocrop');
          const t = (x) => new Touch({identifier: 7, target: el,
                                      clientX: x, clientY: y});
          el.dispatchEvent(new TouchEvent('touchstart',
            {touches: [t(x0)], targetTouches: [t(x0)], changedTouches: [t(x0)],
             bubbles: true, cancelable: true}));
          el.dispatchEvent(new TouchEvent('touchend',
            {touches: [], changedTouches: [t(x1)], bubbles: true,
             cancelable: true}));
        }""", [box["x"] + box["width"] * 0.8, box["x"] + box["width"] * 0.1, y])
        page.wait_for_timeout(250)
        self.assertNotEqual(was, page.text_content(".ocard .olabel"),
                            "옆으로 그었는데 초점이 안 넘어갔다")

    def test_오프라인_동정기가_폰에서_선다(self):
        fx.review_done(self.w.vp)
        page = self.bake("catalog")
        self.assertGreater(len(page.query_selector_all(".ocard")), 0)
        self.assertLessEqual(self.over(), 1, "가로로 밀린다")
        self.assertTrue(page.eval_on_selector(
            ".ocard .ocrop img", "el => el.complete && el.naturalWidth > 0"),
            "크롭이 안 실렸다")
