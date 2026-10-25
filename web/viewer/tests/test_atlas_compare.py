"""도감 바둑판 보기·종 비교 (238).

## 되살려서 잡히는가

- 1번 — `_row_figure` 가 도판 쪽을 크롭보다 먼저 집으면 실패한다. 논문
  도판은 크롭이 있어야 그 종만 보인다 — 쪽 전체를 띄우면 칸마다 같은 도판이
  서고 어느 종인지가 안 보인다
- 2번 — `atlas_compare` 가 찾은 차례(`seq`)로 놓으면 실패한다. **사람이 고른
  차례가 칸의 차례다**
- 3번 — 못 찾은 열쇠를 띠 없이 버리면 실패한다. 다섯을 골랐는데 넷이 뜨면
  까닭을 모른다
- 4번 — 다섯에서 안 자르면 실패한다. 화면이 고르기 칸을 잠그지만 주소는
  손으로 고칠 수 있다 — 화면에서 막는 것은 막는 것이 아니다
- 5번 — 칸을 빼는 링크가 자기를 들고 가면 실패한다
- 6번 — 다 빈 줄을 내거나, 값이 있는 줄에서 빈 칸을 비워 두면 실패한다
- 8번 — `_row_figure`·비교 그림이 주석 달린 자리(`Tafel 아님`)의 쪽을
  띄우면 실패한다. 그 쪽은 권 뒤 색인이라 글자뿐이다(운영 사본에서 봤다)
- 7번 — 열쇠를 `id`·`seq` 로 바꾸면 실패한다. 이 행은 반입마다 다시 생긴다
"""
import re
import shutil
import subprocess
import tempfile
import unittest

from django.test import Client
from django.urls import reverse

from .base import DiaRUGATestCase
from ..models import Atlas, AtlasEntry, AtlasPlacement


class AtlasCompareTests(DiaRUGATestCase):
    def setUp(self):
        super().setUp()
        self.c = Client()
        k = Atlas.objects.create(key="korean", title="한국 도감", short="한국 도감",
                                 sort_order=0)
        p = Atlas.objects.create(key="1996-lee-bransfield", title="1996",
                                 short="Lee 1996", sort_order=1)
        # 논문 도판 — 크롭과 도판 쪽이 둘 다 있다. 크롭이 먼저다
        self.a = AtlasEntry.objects.create(
            atlas=p, seq=1, name="Fragilariopsis kerguelensis", genus="Fragilariopsis",
            binomial="Fragilariopsis kerguelensis", rank="species")
        AtlasPlacement.objects.create(entry=self.a, seq=0, plate=2, pdf_page=5,
                                      pdf_plate_page=6)
        AtlasPlacement.objects.create(entry=self.a, seq=1, plate=3, figures="4",
                                      pdf_page=7, pdf_plate_page=8,
                                      crop_image="atlas/1996-lee-bransfield/crops/pl3_fig4.png")
        # 한국 도감 — 크롭이 없어 도판 쪽이 온다 · 생태가 있다
        self.b = AtlasEntry.objects.create(
            atlas=k, seq=5, name="Melosira ambigua (GRUN.) O. F. MÜLLER",
            genus="Melosira", binomial="Melosira ambigua", rank="species",
            extra={"ecology": "담수 부유"})
        AtlasPlacement.objects.create(entry=self.b, seq=0, plate=1, pdf_page=30,
                                      pdf_plate_page=31)
        # 한국 도감 — PDF 쪽이 없다(201건)
        self.c_ = AtlasEntry.objects.create(
            atlas=k, seq=9, name="Cocconeis placentula EHRENBERG", genus="Cocconeis",
            binomial="Cocconeis placentula", rank="species", item_no="300")
        AtlasPlacement.objects.create(entry=self.c_, seq=0, plate=21, book_page=147)
        # 표제어가 겹치는 자리 (한국 도감에 실제로 하나) — 뒤엣것
        AtlasEntry.objects.create(
            atlas=k, seq=10, name="Cocconeis placentula EHRENBERG", genus="Cocconeis",
            binomial="Cocconeis placentula", rank="species", item_no="301")

    def key(self, e):
        return f"{e.atlas.key}:{e.name}"

    def cmp(self, *keys):
        return self.c.get(reverse("atlas_compare"), {"e": list(keys)})

    # --- 1번 -----------------------------------------------------------------

    def test_바둑판_칸은_크롭을_먼저_띄운다(self):
        r = self.c.get(reverse("atlas"), {"q": "Fragilariopsis"})
        html = r.content.decode()
        self.assertIn('class="agrid"', html)
        card = html[html.index(f'data-key="{self.key(self.a)}"'):]
        card = card[:card.index("</label>")]
        self.assertIn("crops/pl3_fig4.png", card.replace("%2F", "/"))
        self.assertIn("fig. 4", card)

    def test_크롭이_없으면_도판_쪽이고_쪽도_없으면_그렇게_말한다(self):
        html = self.c.get(reverse("atlas"), {"atlas": "korean"}).content.decode()
        mel = html[html.index(f'data-key="{self.key(self.b)}"'):]
        mel = mel[:mel.index("</label>")]
        self.assertIn("korean/main/p0031.png", mel.replace("%2F", "/"))
        coc = html[html.index(f'data-key="{self.key(self.c_)}"'):]
        coc = coc[:coc.index("</label>")]
        self.assertIn("그림 없음", coc)
        self.assertNotIn("<img", coc)

    # --- 2번 -----------------------------------------------------------------

    def test_고른_차례대로_놓는다(self):
        r = self.cmp(self.key(self.b), self.key(self.a))
        self.assertEqual([x["key"] for x in r.context["rows"]],
                         [self.key(self.b), self.key(self.a)])
        r = self.cmp(self.key(self.a), self.key(self.b))
        self.assertEqual([x["key"] for x in r.context["rows"]],
                         [self.key(self.a), self.key(self.b)])

    def test_겹치는_표제어는_앞엣것이다(self):
        r = self.cmp(self.key(self.c_), self.key(self.a))
        self.assertEqual(r.context["rows"][0]["item_no"], "300")

    # --- 3번 -----------------------------------------------------------------

    def test_못_찾은_열쇠를_말한다(self):
        r = self.cmp(self.key(self.a), "korean:Navicula nowhere", "엉터리")
        self.assertEqual(len(r.context["rows"]), 1)
        self.assertEqual(r.context["missing"], ["korean:Navicula nowhere"])
        self.assertContains(r, "korean:Navicula nowhere")
        self.assertContains(r, "못 찾았습니다")

    # --- 4번 -----------------------------------------------------------------

    def test_다섯에서_자른다(self):
        k = Atlas.objects.get(key="korean")
        keys = []
        for i in range(7):
            e = AtlasEntry.objects.create(atlas=k, seq=100 + i, name=f"Navicula n{i}",
                                          genus="Navicula", binomial=f"Navicula n{i}")
            keys.append(self.key(e))
        r = self.cmp(*keys)
        self.assertEqual([x["key"] for x in r.context["rows"]], keys[:5])
        self.assertEqual(r.context["over"], 2)
        self.assertContains(r, "앞의 다섯 종만")

    # --- 5번 -----------------------------------------------------------------

    def test_빼는_링크는_나머지를_들고_간다(self):
        ka, kb = self.key(self.a), self.key(self.b)
        rows = self.cmp(ka, kb).context["rows"]
        nxt = self.c.get(rows[0]["drop_url"])
        self.assertEqual([x["key"] for x in nxt.context["rows"]], [kb])
        # 하나 남아도 빈 화면으로 튕기지 않는다
        self.assertContains(nxt, "한 종만 남았습니다")

    # --- 6번 -----------------------------------------------------------------

    def test_값이_있는_줄만_내고_빈_칸은_줄표로(self):
        r = self.cmp(self.key(self.a), self.key(self.c_))
        self.assertNotContains(r, ">생태<")
        r = self.cmp(self.key(self.a), self.key(self.b))
        html = r.content.decode()
        self.assertIn(">생태<", html)
        sec = html[html.index(">생태<"):]
        sec = sec[:sec.index('class="sec"')] if 'class="sec"' in sec else sec
        self.assertIn("<td>—</td>", sec)
        self.assertIn("<td>담수 부유</td>", sec)

    # --- 7번 -----------------------------------------------------------------

    def test_다시_반입해도_같은_주소가_같은_종을_연다(self):
        """반입은 행을 지우고 다시 만든다 — `id`·`seq` 가 바뀐다."""
        ka = self.key(self.a)
        AtlasEntry.objects.filter(pk=self.a.pk).delete()
        AtlasEntry.objects.create(atlas=self.a.atlas, seq=77, name=self.a.name,
                                  genus=self.a.genus, binomial=self.a.binomial)
        r = self.cmp(ka, self.key(self.b))
        self.assertEqual(r.context["missing"], [])
        self.assertEqual(r.context["rows"][0]["name"], self.a.name)

    @unittest.skipUnless(shutil.which("node"), "node 가 없다")
    def test_인라인_스크립트가_파싱된다(self):
        """이름에 따옴표가 들어도 스크립트가 안 깨진다 (`escapejs`). **렌더한
        것**을 `node --check` 에 넣는다 — 템플릿 원본은 JS 가 아니다."""
        AtlasEntry.objects.filter(pk=self.b.pk).update(name='Melosira "x" \'y\' </script>')
        self.b.refresh_from_db()
        pages = [self.cmp(self.key(self.a), self.key(self.b)),
                 self.c.get(reverse("atlas"), {"q": "a"})]
        for r in pages:
            self.assertEqual(r.status_code, 200)
            for js in re.findall(r"<script>(.*?)</script>", r.content.decode(), re.S):
                with tempfile.NamedTemporaryFile("w", suffix=".js") as f:
                    f.write(js)
                    f.flush()
                    out = subprocess.run(["node", "--check", f.name],
                                         capture_output=True, text=True)
                self.assertEqual(out.returncode, 0, out.stderr)

    # --- 8번 -----------------------------------------------------------------

    def test_주석_달린_자리의_쪽은_그림으로_안_띄운다(self):
        p = Atlas.objects.create(key="schmidt", title="Schmidt", short="Schmidt",
                                 sort_order=2)
        e = AtlasEntry.objects.create(atlas=p, seq=1, name="Coscinodiscus agapetos",
                                      genus="Coscinodiscus",
                                      binomial="Coscinodiscus agapetos")
        AtlasPlacement.objects.create(
            entry=e, seq=0, plate=240, volume="Band2", pdf_page=204,
            pdf_plate_page=205, note="Tafel 아님 · 권 뒤 Verzeichnis(색인) 쪽에서 왔다")
        html = self.c.get(reverse("atlas"), {"atlas": "schmidt"}).content.decode()
        card = html[html.index('data-key="schmidt:Coscinodiscus agapetos"'):]
        card = card[:card.index("</label>")]
        self.assertNotIn("<img", card)
        self.assertIn("그림 없음", card)
        r = self.cmp("schmidt:Coscinodiscus agapetos", self.key(self.a))
        self.assertNotIn("p0205.png", r.content.decode())
        # 자리 줄에는 남는다 — 주석과 함께 사람이 읽는다
        self.assertContains(r, "Tafel 아님")
