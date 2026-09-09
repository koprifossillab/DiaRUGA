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


class MobileChromeTest(MobileTestCase):
    """**껍데기**가 폰에서 자리를 안 뺏는가 (194).

    192 가 손댄 것은 화면의 *몸통*이었다. 그 둘레의 띠·단추·섬네일은 데스크탑
    값 그대로여서, 폰 한 화면(412×915)에서 사진이 294px 밖에 안 됐다.

    여기서 되살려서 잡는 것은 **자리를 도로 뺏는 갈래**다 — 붙박이 띠가
    돌아오거나, 접기로 한 판이 펴진 채로 서거나, 섬네일이 다시 커지는 것.
    """

    def test_화면_조정이_폰에서는_접혀_있다(self):
        page = self.review()
        box = page.query_selector("#adjbox-stack")
        self.assertIsNotNone(box, "화면 조정 판이 없다")
        self.assertFalse(box.get_property("open").json_value(),
                         "폰인데 밝기·대비 판이 펴진 채로 선다")
        # 접혀 있어도 **다시 펼 수 있어야 한다** — 접는 것과 감추는 것은 다르다
        summary = page.query_selector("#adjbox-stack > summary")
        self.assertTrue(summary.is_visible(), "접었는데 펼 자리가 없다")
        summary.click()
        page.wait_for_timeout(150)
        self.assertTrue(page.query_selector("#bri-stack").is_visible(),
                        "펴도 슬라이더가 안 나온다")

    def test_켜져_있으면_접혀_있어도_적힌다(self):
        """조정이 걸린 채로 접히면 **사진이 왜 어두운지 화면 어디에도 안
        적힌다** — 그러면 사람은 사진을 의심한다."""
        page = self.review()
        page.eval_on_selector(
            "#bri-stack",
            "el => { el.value = 60; el.dispatchEvent(new Event('input')); }")
        page.wait_for_timeout(150)
        self.assertIn("60%", page.text_content("#adjnow-stack"),
                      "접힌 요약에 켜진 값이 안 적힌다")

    def test_판_섬네일이_폰에서_작아진다(self):
        """사용자: *"시야 섬네일이 너무 커"*. 128px 은 데스크탑 값이다."""
        page = self.review()
        shot = page.query_selector(".strip .shot")
        if shot is None:
            self.skipTest("이 픽스처에는 캐러셀이 없다")
        self.assertLess(shot.bounding_box()["width"], 100,
                        "폰인데 판 섬네일이 데스크탑 크기 그대로다")

    def test_접은_도구가_눌러야_나오고_실제로_돈다(self):
        """**감추는 것이 아니라 접는 것이다** — 눌러서 나온 단추가 돌아야
        한다. `<details>` 안으로 들어가면서 배선(`#tools-` 위임)이 끊기면
        예외도 경고도 없이 아무 일도 안 일어난다."""
        page = self.review()
        more = page.query_selector("#tools-stack .moretools")
        self.assertIsNotNone(more, "접은 도구 판이 없다")
        allbtn = page.query_selector('#tools-stack button[data-act="all"]')
        self.assertFalse(allbtn.is_visible(), "접기로 한 도구가 그냥 보인다")
        page.click("#tools-stack .moretools > summary")
        page.wait_for_timeout(150)
        self.assertTrue(allbtn.is_visible(), "펴도 도구가 안 나온다")
        allbtn.click()
        page.wait_for_timeout(200)
        self.assertGreater(len(page.query_selector_all("#masks-stack .sel")), 0,
                           "「전체 선택」이 눌렸는데 아무것도 안 골라졌다")


class MobileOfflineChromeTest(MobileOfflineFileTest):
    """오프라인 파일의 띠 — **알리는 곳과 하는 곳이 갈렸다** (194)."""

    def test_내려받기가_맨_위에_없다(self):
        """사용자: *"결과 내려 받는 버튼은 검토를 다 마치고 단 한번만 쓰게
        될텐데, 맨 위에 두는 것은 나쁜 ui 구성이야."*

        붙박이 띠가 폰에서 117px 을 늘 먹고 있었다 — 192 가 머리줄을 내려
        사진에 내준 자리를 그대로 도로 가져갔다.
        """
        page = self.bake()
        bar = page.query_selector(".offbar")
        self.assertIsNotNone(bar, "알리는 줄이 없다")
        self.assertNotEqual(
            page.eval_on_selector(".offbar", "el => getComputedStyle(el).position"),
            "sticky", "맨 위 띠가 다시 붙박이가 됐다")
        self.assertLess(bar.bounding_box()["height"], 60,
                        "알리는 줄이 한 줄이 아니다")
        self.assertEqual(
            page.eval_on_selector(
                "#off-get", "el => !!el.closest('.offbar')"),
            False, "내려받기 단추가 아직 맨 위 띠 안에 있다")
        self.assertTrue(
            page.eval_on_selector("#off-get", "el => !!el.closest('#off-done')"),
            "내려받기 단추가 마침 상자 안에 없다")

    def test_바꾸면_아래로_데려가는_길이_뜬다(self):
        """단추를 아래로 내렸으면 **길을 놓아야 한다** — 끝내고 나서 못 찾는
        자리를 남기지 않는다. 그리고 그 길이 **주소의 시야 번호를 지우면 안
        된다**(새로고침하면 첫 시야로 돌아간다)."""
        page = self.bake()
        jump = page.query_selector("#off-jump")
        self.assertFalse(jump.is_visible(), "바꾼 것이 없는데 길이 떠 있다")
        page.evaluate("location.hash = 'g0'")
        page.wait_for_timeout(200)
        self.click_image(70, 70, uid="vp0")
        page.keyboard.press("Space")
        page.wait_for_timeout(900)
        self.assertTrue(jump.is_visible(), "안 내려받았는데 길이 안 뜬다")
        jump.click()
        page.wait_for_timeout(400)
        self.assertTrue(page.query_selector("#off-done").is_visible(),
                        "눌렀는데 마침 상자로 안 갔다")
        self.assertIn("g0", page.evaluate("location.hash"),
                      "아래로 가면서 보던 시야가 주소에서 지워졌다")

    def test_시야_목록이_한_줄로_구른다(self):
        """60개가 격자로 서면 화면의 절반이다. **가로로 미는 것은 이 상자
        안이지 페이지가 아니다.**"""
        page = self.bake()
        self.assertEqual(
            page.eval_on_selector(".vplist", "el => getComputedStyle(el).flexWrap"),
            "nowrap", "시야 목록이 아직 격자다")
        btn = page.query_selector(".vplist button")
        self.assertGreaterEqual(btn.bounding_box()["height"], 30,
                                "시야 단추가 손끝보다 작다")
        self.assertLessEqual(self.over(), 1, "페이지가 가로로 밀린다")
