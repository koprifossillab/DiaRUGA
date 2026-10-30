"""슬라이드를 보는 화면 셋이 **지금 검토 중인 묶음**을 말하는가 (088).

목록 · 검출 갤러리 · 계측 표. 셋의 숫자는 전부 검토 대상 묶음에서 나온다(`reviewing()`). 묶음을 갈면
같은 슬라이드의 "검출" 칸이 통째로 달라지는데, 화면에 표시가 없으면 **자료가
변한 것인지 묶음이 바뀐 것인지 가릴 수가 없다.**

여기서 지키는 것 셋.

1. **셋 다 이름을 낸다** — 한 화면만 고치기 쉬운 자리다
2. **묶음이 안 켜져 있으면 그렇게 말한다** — 그 상태에서 뷰어는 검출을 하나도
   안 그린다(P10 3.6). 아무 표시가 없으면 "자료가 없다" 로 읽혀 사람이 파이프라인을
   돌리러 간다
3. **묶음을 갈면 표시도 따라간다** — 굳은 문구를 박아 두면 시험은 통과하고
   화면은 거짓말을 한다

**CSS 가 실제로 먹는지는 여기서 못 본다** — `browser/test_batch_tag.py` 가 본다.
"""
import re

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from . import factories as fx
from ..models import RunBatch


class BatchTagTest(DiaRUGATestCase):

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=3)

    def setUp(self):
        self.c = Client()

    def urls(self):
        """표시가 있어야 하는 화면 **셋**.

        **시야 목록은 뺐다**(2026-10-30) — 묶음이 시야마다 정해져 머리줄 대신
        표지마다 단다(아래 `VpBatchBadgeTest`).

        셋 다 검토 대상 묶음의 개체를 센다 — 목록의 "검출" 칸,
        갤러리에 늘어놓는 조각, 계측 표의 분포. **한 화면만 고치기 쉬운 자리라
        목록을 여기 한 곳에 둔다.**
        """
        slug = self.w.slide.slug
        return [("데이터셋 목록", reverse("index")),
                ("검출 갤러리", reverse("crops", args=[slug])),
                ("계측 표", reverse("detections", args=[slug]))]

    def tag(self, url):
        """그 화면의 **표시 하나만** 뽑는다.

        페이지 전체를 문자열로 뒤지면 엉뚱한 데가 걸린다 — `base.html` 의 CSS
        주석에도 `batchtag` 가 있고, 썸네일 배지의 `title` 에는 **다른 묶음의
        이름**이 들어간다("… 에는 검출이 있습니다", P10 4단계). 둘 다 이 표시와
        무관하다. 실제로 그것에 걸려 시험을 한 번 고쳤다.
        """
        html = self.c.get(url).content.decode()
        m = re.search(r'<a class="batchtag[^"]*"[^>]*>.*?</a>', html, re.S)
        self.assertIsNotNone(m, f"{url} 에 검토 묶음 표시가 없다")
        return m.group(0)

    def test_세_화면이_검토_중인_묶음_이름을_낸다(self):
        want = RunBatch.objects.get(for_review=True).label
        for name, url in self.urls():
            with self.subTest(화면=name):
                tag = self.tag(url)
                self.assertIn(want, tag, f"{name} 이 묶음 이름을 안 낸다")
                self.assertIn("검토 중", tag)

    def test_묶음을_갈면_표시도_따라간다(self):
        """굳은 문구를 박아 두면 시험은 통과하고 화면은 거짓말을 한다."""
        other = RunBatch.objects.create(kind="detect", label="yolo-딴것")
        RunBatch.objects.filter(for_review=True).update(for_review=False)
        RunBatch.objects.filter(pk=other.pk).update(for_review=True)

        for name, url in self.urls():
            with self.subTest(화면=name):
                tag = self.tag(url)
                self.assertIn("yolo-딴것", tag, f"{name} 이 새 묶음을 안 낸다")
                self.assertNotIn("sam2-시험", tag, f"{name} 의 표시가 옛 묶음이다")

    def test_검토할_묶음이_없으면_그렇게_말한다(self):
        """**"없음" 은 "자료가 없음" 과 다른 말이다.** 검출은 있는데 볼 묶음이
        안 정해진 상태이고, 그때 화면은 검출을 하나도 안 그린다."""
        RunBatch.objects.filter(for_review=True).update(for_review=False)
        for name, url in self.urls():
            with self.subTest(화면=name):
                tag = self.tag(url)
                self.assertIn("batchtag none", tag,
                              f"{name} 이 경고 모양으로 안 나온다")
                self.assertIn("검토할 묶음", tag)
                self.assertIn("없음", tag)

    def test_표시를_누르면_고치는_자리로_간다(self):
        """읽는 표시이지 고르는 자리가 아니다 — 대신 갈 곳을 준다."""
        for name, url in self.urls():
            with self.subTest(화면=name):
                self.assertIn(f'href="{reverse("system_settings_ops")}"', self.tag(url),
                              f"{name} 의 표시가 운영 화면으로 안 간다")


class VpBatchBadgeTest(DiaRUGATestCase):
    """시야 목록이 **표지마다 그 시야의 주 묶음**을 다는가 (2026-10-30).

    P32 부터 묶음은 시야마다 정해진다 — 3차 정답 시야는 `yolo-3차` 에 못 박히고
    칸이 빈 시야는 검토 대상을 따라간다. 머리줄에 전역 검토 대상 하나를 적으면
    **못 박힌 시야의 표지와 이름이 안 맞는다.** 그래서 머리줄 표시를 걷고 표지에
    단다.
    """

    @classmethod
    def setUpTestData(cls):
        fx.make_classes()
        cls.w = fx.make_world(slug="rs23", n_viewpoints=2, n_candidates=3)
        cls.other = RunBatch.objects.create(kind="detect", label="yolo-못박음")
        vp = cls.w.viewpoints[0]
        vp.batch = cls.other
        vp.save(update_fields=["batch"])
        cls.pinned, cls.free = cls.w.viewpoints[0].idx, cls.w.viewpoints[1].idx

    def badges(self):
        """표지 번호 → 그 표지의 주 묶음 배지 글자."""
        html = Client().get(reverse("dataset", args=["rs23"])).content.decode()
        out = {}
        for tile in re.findall(r'<a class="tile".*?</a>', html, re.S):
            idx = int(re.search(r'>g(\d+) · ', tile).group(1))
            m = re.search(r'<span class="badge vpbatch"[^>]*>(.*?)</span>', tile, re.S)
            out[idx] = m.group(1) if m else None
        return html, out

    def test_표지마다_그_시야의_주_묶음을_단다(self):
        _, b = self.badges()
        self.assertEqual(b[self.pinned], "yolo-못박음")
        self.assertEqual(b[self.free], RunBatch.objects.get(for_review=True).label)

    def test_칸이_빈_시야는_검토_대상을_따라간다(self):
        """굳은 문구를 박아 두면 시험은 통과하고 화면은 거짓말을 한다."""
        new = RunBatch.objects.create(kind="detect", label="yolo-딴것")
        RunBatch.objects.filter(for_review=True).update(for_review=False)
        RunBatch.objects.filter(pk=new.pk).update(for_review=True)
        _, b = self.badges()
        self.assertEqual(b[self.free], "yolo-딴것")
        self.assertEqual(b[self.pinned], "yolo-못박음")

    def test_머리줄에_전역_묶음을_안_적는다(self):
        html, _ = self.badges()
        self.assertNotIn('class="batchtag', html)
