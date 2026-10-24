"""첫 화면 로고 (235) — 로고 파일이 나가고, 덮개가 화면에 있고, 오프라인 꾸러미에는
없는가. 뜨고 걷히는 것은 `browser/test_splash.py` 가 본다."""
from django.urls import reverse

from .base import DiaRUGATestCase
from .. import context


class SplashAssetTest(DiaRUGATestCase):

    def test_로고_둘이_나가고_다른_이름은_404(self):
        for name, ctype in (("logo.gif", "image/gif"), ("logo.png", "image/png")):
            r = self.client.get(reverse("splash_asset", args=[name]))
            self.assertEqual(r.status_code, 200, name)
            self.assertEqual(r["Content-Type"], ctype)
            self.assertGreater(len(b"".join(r.streaming_content)), 1000)
        for bad in ("logo.json", "..%2Fsettings.py", "x.gif"):
            self.assertEqual(self.client.get(f"/splash/{bad}").status_code, 404, bad)

    def test_끝_장면_시각을_읽는다(self):
        # 0 이면 화면이 GIF 를 건너뛴다 — logo.json 을 못 읽은 것이다
        self.assertGreater(context.SPLASH_MS, 1000)

    def test_목록에_덮개가_있다(self):
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn('<div id="splash"', html)
        self.assertIn("diaruga.splash", html)
        self.assertIn(f"ms = {context.SPLASH_MS}", html)
