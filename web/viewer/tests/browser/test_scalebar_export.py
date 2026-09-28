"""스케일바 모양 고르기와 사진 내보내기 (214).

## 스케일바

모양이 다섯이고(상자·도판식·끝 눈금·눈금자·흑백 칸) 색·자리·크기·숫자를
고른다. **사진 위 스케일바를 두 번 누르면** 고르는 창이 열린다. 설정은
브라우저에만 남는다(`diaruga.scalebar`).

**두 번 누르는 것이 사진 조작으로 새면 안 된다.** 스케일바는 사진 위에 떠
있어서, 누름이 캔버스로 내려가면 그 아래 개체가 골라지거나 범위선택이 된다.

**창이 떠 있는 동안 검토 단축키가 돌면 안 된다.** 창의 단추에 초점이 있어도
키가 문서까지 올라가 D(그리기)·Space(되살리기)를 부른다 — 창 너머 사진에
보이지 않는 교정이 쌓인다.

## 내보내기

원본 판을 다시 받아 원본 해상도로 그리고 PNG 로 내린다. 여기서 보는 것:

- 파일이 **정말 PNG** 이고 크기가 창에 적은 것과 같다
- 스케일바를 빼면 **그 자리만** 달라진다 (나머지 사진은 같다)
- **고른 표시(노란 선택)는 파일에 안 들어간다** — 골라 두고 내보낸 것과
  안 골라 두고 내보낸 것이 같은 파일이어야 한다
- 내보낸 뒤에도 화면의 선택·레이어가 그대로다 (잠시 바꿔 읽고 되돌린다)
"""
import io
import json

from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx


class ScaleBarExportTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=2)

    def open_view(self):
        page = self.open(reverse("group", args=[self.w.slide.slug,
                                                self.w.vp.idx]))
        page.wait_for_selector(".detview .box")
        page.wait_for_function(
            "() => document.querySelector('#sb-stack canvas').width > 1")
        return page

    # --- 스케일바 ----------------------------------------------------------

    def test_스케일바가_캔버스에_그려진다(self):
        page = self.open_view()
        box = page.query_selector("#sb-stack").bounding_box()
        self.assertGreater(box["width"], 20)
        self.assertGreater(box["height"], 8)
        # 캔버스가 비어 있지 않다 — 크기만 잡히고 아무것도 안 그려진 적이 있다
        # (속성에 값이 있는 것과 그 값이 유효한 것은 다르다)
        painted = page.evaluate("""() => {
            const c = document.querySelector('#sb-stack canvas');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
            return n; }""")
        self.assertGreater(painted, 50, "스케일바 캔버스가 비어 있다")

    def test_두_번_누르면_창이_열리고_고른_것이_기억된다(self):
        page = self.open_view()
        page.dblclick("#sb-stack")
        page.wait_for_selector("#sbpicker:not([hidden])")
        # 다섯 모양의 미리보기가 다 그려진다
        self.assertEqual(len(page.query_selector_all("#sbpicker button[data-style]")), 5)

        page.click('#sbpicker button[data-style="ticks"]')
        page.click('#sbpicker button[data-color="yellow"]')
        page.click('#sbpicker button[data-pos="tl"]')
        page.click('#sbpicker button[data-size="l"]')
        page.uncheck('#sbpicker input[data-k="label"]')
        saved = json.loads(page.evaluate(
            "() => localStorage.getItem('diaruga.scalebar')"))
        self.assertEqual(saved, {"style": "ticks", "color": "yellow", "pos": "tl",
                                 "size": "l", "label": False})
        # 화면의 스케일바가 곧바로 자리를 옮긴다
        self.assertIn("pos-tl", page.get_attribute("#sb-stack", "class"))

        page.keyboard.press("Escape")
        page.wait_for_selector("#sbpicker", state="hidden")

        # 다시 열어도 그대로다
        page.reload()
        page.wait_for_selector(".detview .box")
        self.assertIn("pos-tl", page.get_attribute("#sb-stack", "class"))

    def test_두_번_누름이_사진_조작으로_새지_않는다(self):
        """스케일바 밑에 개체를 깔고 두 번 누른다 — 골라지면 안 된다."""
        page = self.open_view()
        # 전제: 스케일바 아래 자리를 누르면 **정말** 무언가가 일어나는 자리인가.
        # 스케일바를 감춰 두고 같은 자리를 끌면 범위선택 띠가 생긴다.
        # 사진이 길어 스케일바가 첫 화면 밖에 있다 — 끌기 전에 끌어다 놓는다
        # (안 그러면 누름이 화면 밖에 떨어져 아무 일도 안 일어나고 헛통과한다)
        page.query_selector("#sb-stack").scroll_into_view_if_needed()
        box = page.query_selector("#sb-stack").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.dblclick("#sb-stack")
        page.wait_for_selector("#sbpicker:not([hidden])")
        page.keyboard.press("Escape")
        self.assertEqual(page.query_selector_all(".detview .box.sel"), [])
        self.assertEqual(page.evaluate(
            "() => getComputedStyle(document.querySelector('#band-stack')).display"),
            "none")
        # 스케일바 자리를 끌어도 범위선택이 시작되지 않는다
        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx - 60, cy - 60)
        self.assertEqual(page.evaluate(
            "() => getComputedStyle(document.querySelector('#band-stack')).display"),
            "none", "스케일바를 끌었는데 사진의 범위선택이 시작됐다")
        page.mouse.up()

    def test_창이_떠_있으면_단축키가_안_먹는다(self):
        page = self.open_view()
        view = page.query_selector("#dv-stack")
        view.hover()
        # **전제 — D 가 평소에는 그리기를 켠다.** 이것이 안 되면 아래 확인이
        # 헛통과한다.
        page.keyboard.press("d")
        self.assertTrue(page.evaluate(
            "() => document.querySelector('#dv-stack').classList.contains('drawing')"),
            "전제가 틀렸다 — D 가 그리기를 안 켠다")
        page.keyboard.press("Escape")
        self.assertFalse(page.evaluate(
            "() => document.querySelector('#dv-stack').classList.contains('drawing')"))

        page.dblclick("#sb-stack")
        page.wait_for_selector("#sbpicker:not([hidden])")
        page.keyboard.press("d")
        self.assertFalse(page.evaluate(
            "() => document.querySelector('#dv-stack').classList.contains('drawing')"),
            "창이 떠 있는데 D 가 그리기를 켰다")

    # --- 내보내기 ----------------------------------------------------------

    def export(self, page, **opts):
        """내보내기 창에서 `opts` 대로 고르고 받은 PNG 를 PIL 로 연다."""
        from PIL import Image as PILImage

        page.click("#export-stack")
        page.wait_for_selector("#exdlg-stack:not([hidden])")
        if "region" in opts:
            page.check(f'#exdlg-stack input[type=radio][value="{opts.pop("region")}"]')
        for k, v in opts.items():
            sel = f'#exdlg-stack input[data-o="{k}"]'
            page.check(sel) if v else page.uncheck(sel)
        # 원본을 받은 뒤에야 크기가 적힌다
        page.wait_for_function(
            "() => /px/.test(document.querySelector('#exdlg-stack [data-k=\"size\"]').textContent)")
        said = page.text_content('#exdlg-stack [data-k="size"]')
        with page.expect_download() as dl:
            page.click('#exdlg-stack button[data-act="go"]')
        path = dl.value.path()
        page.wait_for_function(
            "() => /내려받음/.test(document.querySelector('#exdlg-stack [data-k=\"say\"]').textContent)")
        page.click('#exdlg-stack button[data-act="cancel"]')
        with open(path, "rb") as f:
            raw = f.read()
        self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n", "PNG 가 아니다")
        im = PILImage.open(io.BytesIO(raw)).convert("RGB")
        # 창에 적은 크기가 받은 크기다
        self.assertIn(f"{im.width} × {im.height}", said)
        return im, dl.value.suggested_filename

    def test_원본_해상도_PNG_로_내려받는다(self):
        page = self.open_view()
        im, name = self.export(page, region="full", scalebar=True, mask=True, box=True)
        # 원본(640×480)보다 작지 않고 비율이 같다
        self.assertGreaterEqual(im.width, fx.IMG_W)
        self.assertAlmostEqual(im.width / im.height, fx.IMG_W / fx.IMG_H, places=2)
        self.assertTrue(name.endswith(".png"))
        self.assertIn(self.w.slide.slug, name)

    def test_축소본이_아니라_원본으로_그린다(self):
        """화면은 1600 px 축소본을 띄운다. 그것을 찍으면 원본보다 작은 파일이
        된다 — **원본 판을 다시 받아 그려야** 한다.

        픽스처 사진(640 px)은 축소본보다 작아서 둘이 같은 그림이 된다 — 그대로
        두면 이 확인이 헛통과한다. 합성본 파일만 축소본보다 크게 갈아 끼운다."""
        from ..base import write_image
        big = (2000, 1500)
        write_image(self.w.vp.stack.focused_path, size=big)
        page = self.open_view()
        im, _ = self.export(page, region="full", scalebar=True, mask=True, box=True)
        self.assertEqual((im.width, im.height), big)

    def test_스케일바를_빼면_그_자리만_달라진다(self):
        from PIL import ImageChops
        page = self.open_view()
        with_bar, _ = self.export(page, region="full", scalebar=True, mask=False,
                                  box=False, reject=False)
        no_bar, name = self.export(page, region="full", scalebar=False, mask=False,
                                   box=False, reject=False)
        self.assertIn("nobar", name)
        diff = ImageChops.difference(with_bar, no_bar).getbbox()
        self.assertIsNotNone(diff, "스케일바를 넣었는데 파일이 같다")
        # 달라진 자리는 오른쪽 아래 귀퉁이뿐이다 (기본 자리)
        x0, y0, x1, y1 = diff
        self.assertGreater(x0, with_bar.width / 2)
        self.assertGreater(y0, with_bar.height / 2)
        # 스케일바 없는 쪽은 원본 회색 그대로다 — 도구·체크박스가 안 들어갔다
        self.assertEqual(no_bar.getextrema(), ((128, 128),) * 3)

    def test_고른_표시는_파일에_안_들어간다(self):
        from PIL import ImageChops
        page = self.open_view()
        plain, _ = self.export(page, region="full", scalebar=False, mask=True, box=True)
        # 마스크·bbox 가 정말 들어갔다 — 안 들어갔으면 아래 비교가 헛통과한다
        self.assertNotEqual(plain.getextrema(), ((128, 128),) * 3)

        # 개체 하나를 고른다
        pts = page.evaluate("""() => document.querySelector(
            '#masks-stack polygon:not(.reject)').getAttribute('points')""")
        xy = [float(v) for v in pts.replace(",", " ").split()]
        xs, ys = xy[0::2], xy[1::2]
        self.click_image(sum(xs) / len(xs), sum(ys) / len(ys))
        page.wait_for_selector(".detview .box.sel")
        picked, _ = self.export(page, region="full", scalebar=False, mask=True, box=True)
        self.assertIsNone(ImageChops.difference(plain, picked).getbbox(),
                          "골라 둔 개체의 노란 표시가 파일에 들어갔다")
        # 화면과 **다르게** 골라 내보낸다(마스크·bbox 끄고 탈락 켜고) — 잠시
        # 바꿔 읽은 레이어가 화면에 남으면 사람은 마스크가 사라진 줄 안다
        before = page.get_attribute("#dv-stack", "class")
        self.export(page, region="full", scalebar=False, mask=False, box=False,
                    reject=True)
        self.assertEqual(page.get_attribute("#dv-stack", "class"), before)
        self.assertEqual(len(page.query_selector_all(".detview .box.sel")), 1,
                         "내보낸 뒤 화면의 선택이 풀렸다")

    def test_확대한_자리만_내보낸다(self):
        page = self.open_view()
        view = page.query_selector("#dv-stack")
        view.scroll_into_view_if_needed()
        b = view.bounding_box()
        page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        for _ in range(6):
            page.mouse.wheel(0, -100)
            page.wait_for_timeout(30)
        full, _ = self.export(page, region="full", scalebar=True)
        part, name = self.export(page, region="view", scalebar=True)
        self.assertIn("zoom", name)
        # 보이는 자리는 사진의 일부다 — 화면 선명도로 늘려도 비율이 화면 상자를 따른다
        ratio = b["width"] / b["height"]
        self.assertAlmostEqual(part.width / part.height, ratio, delta=0.05)
        self.assertNotEqual((part.width, part.height), (full.width, full.height))
