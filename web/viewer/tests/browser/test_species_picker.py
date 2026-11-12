"""`종명` 글자를 누르면 뜨는 **속별 목록** (254).

칸의 자동완성(`datalist`)은 치는 글자로 좁히는 길이고, 이 목록은 이미 쓴 이름을
속마다 접어 훑어보는 길이다. 검토 화면의 개체 카탈로그와 카탈로그 화면이 **같은
partial**(`_species_picker.html`)을 쓴다.

여기서 보는 것은 전부 눌러야 드러나는 것이다 —

- 접혀서 뜨는가, 펴면 이름이 보이는가
- 고르면 칸에 적히고 **저장까지 가는가** (값만 넣고 `input` 을 안 내면 화면에는
  적혀 있고 DB 에는 없다 — "됐다" 고 말하는 고장이다)
- **읽기 전용에서 안 열리는가** (051)
- 검토 화면의 단축키가 목록 안의 키 입력을 안 받는가
"""
from django.urls import reverse

from .base import BrowserTestCase
from .. import factories as fx
from ...models import DiatomObject, ObjectReview, RunBatch

NAMES = ["Eucampia antarctica", "Eucampia sp.", "Chaetoceros sp."]


class CatalogSpeciesPickerTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}", n_candidates=4)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        for _vp in self.w.viewpoints:
            fx.review_done(_vp)
        # **이름은 옆 슬라이드에 적어 둔다.** 목록은 관찰을 안 가리고
        # (`data.species_seen`), 이 슬라이드의 카드는 전부 비어 있어야 어느
        # 카드를 집어도 같은 시험이 된다.
        other = fx.make_world(slug=f"rs24-{self.uniq}",
                              site_code=f"RT{self.uniq}", n_candidates=8)
        for _vp in other.viewpoints:
            fx.review_done(_vp)
        objs = list(DiatomObject.objects.filter(
            viewpoint__slide=other.slide).order_by("pk"))
        assert len(objs) >= 3, "개체가 모자라 시험이 헛돈다"
        for o, name in zip(objs, NAMES):
            o.species = name
            o.save()

    def open_catalog(self):
        return self.open(reverse("catalog", args=[self.w.slide.slug]))

    def empty_card(self, page):
        return page.locator('.catcard:has(input.species[value=""])').first

    def test_속마다_접혀서_뜬다(self):
        page = self.open_catalog()
        self.assertEqual(page.locator(".sppop:visible").count(), 0,
                         "누르기 전인데 목록이 떠 있다")
        self.empty_card(page).locator("label.sppick").click()
        pop = page.locator(".sppop")
        self.assertTrue(pop.is_visible(), "종명을 눌렀는데 목록이 안 떴다")
        self.assertEqual(pop.locator("details").count(), 2)
        heads = [t.split()[0] for t in pop.locator("summary").all_inner_texts()]
        self.assertEqual(heads, ["Chaetoceros", "Eucampia"])
        # **접혀 있다** — 이름은 펴야 보인다
        self.assertEqual(pop.locator(".spitem:visible").count(), 0,
                         "접혀 있어야 할 속이 펴져 있다")
        pop.locator("summary", has_text="Eucampia").click()
        self.assertEqual(pop.locator(".spitem:visible").all_inner_texts(),
                         ["Eucampia antarctica", "Eucampia sp."])

    def test_고르면_적히고_저장된다(self):
        page = self.open_catalog()
        card = self.empty_card(page)
        card.locator("label.sppick").click()
        pop = page.locator(".sppop")
        pop.locator("summary", has_text="Eucampia").click()
        pop.locator(".spitem", has_text="Eucampia sp.").click()
        self.assertTrue(pop.is_hidden(), "골랐는데 목록이 안 닫혔다")
        page.wait_for_timeout(1500)
        self.assertEqual(
            DiatomObject.objects.filter(species="Eucampia sp.").count(), 2,
            "화면에는 적혔는데 저장이 안 갔다")

    def test_적힌_이름의_속은_펴져_있다(self):
        page = self.open_catalog()
        card = self.empty_card(page)
        card.locator(".species").fill("Eucampia antarctica")
        card.locator("label.sppick").click()
        pop = page.locator(".sppop")
        self.assertEqual(pop.locator(".spitem.cur:visible").all_inner_texts(),
                         ["Eucampia antarctica"])

    def test_거르면_걸린_것만_남는다(self):
        page = self.open_catalog()
        self.empty_card(page).locator("label.sppick").click()
        pop = page.locator(".sppop")
        pop.locator(".sphead input").fill("chae")
        self.assertEqual(pop.locator(".spitem:visible").all_inner_texts(),
                         ["Chaetoceros sp."])
        self.assertEqual(pop.locator("details:visible").count(), 1)

    def test_Esc_와_바깥_누르기로_닫힌다(self):
        page = self.open_catalog()
        label = self.empty_card(page).locator("label.sppick")
        label.click()
        page.keyboard.press("Escape")
        self.assertTrue(page.locator(".sppop").is_hidden())
        label.click()
        self.assertTrue(page.locator(".sppop").is_visible())
        page.locator("body").click(position={"x": 5, "y": 5})
        self.assertTrue(page.locator(".sppop").is_hidden())

    def test_자동완성_목록은_그대로다(self):
        """칸의 `datalist` 를 걷은 것이 아니다 — 둘이 나란히 있다."""
        page = self.open_catalog()
        self.assertEqual(
            self.empty_card(page).locator(".species").get_attribute("list"),
            "species-seen")
        self.assertEqual(page.locator("#species-seen option").count(), 3)


class ReviewSpeciesPickerTest(BrowserTestCase):

    def make_data(self):
        fx.make_classes()
        self.w = fx.make_world(slug=f"rs23-{self.uniq}",
                               site_code=f"RS{self.uniq}",
                               n_frames=3, n_candidates=3)
        RunBatch.objects.filter(for_review=True).update(code="S1")
        keys = self.w.keys()
        self.key = keys[0]
        # 고를 개체(첫 번째)는 비워 두고 옆 둘에 이름을 적어 둔다
        fx.add_review(self.w.vp, keys[1], species="Eucampia antarctica")
        fx.add_review(self.w.vp, keys[2], species="Chaetoceros sp.")

    def open_review(self, query=""):
        page = self.open(reverse("group", args=[self.w.slug, self.w.vp.idx])
                         + query)
        page.wait_for_selector(".detview .box")
        return page

    def pick_first(self):
        self.click_image(40 + 30, 50 + 20)
        self.page.wait_for_timeout(200)

    def test_고르면_개체에_저장된다(self):
        page = self.open_review()
        self.pick_first()
        page.click('label[for="catsp-stack"]')
        pop = page.locator(".sppop")
        self.assertTrue(pop.is_visible(), "종명을 눌렀는데 목록이 안 떴다")
        self.assertEqual(pop.locator(".spitem:visible").count(), 0)
        pop.locator("summary", has_text="Eucampia").click()
        pop.locator(".spitem", has_text="Eucampia antarctica").click()
        self.assertEqual(page.input_value("#catsp-stack"), "Eucampia antarctica")
        page.wait_for_timeout(900)
        row = ObjectReview.objects.filter(mask_key=self.key).first()
        self.assertIsNotNone(row, "판정 줄이 안 생겼다")
        self.assertEqual(row.diatom_object.species, "Eucampia antarctica")

    def test_목록_안의_키는_단축키로_안_간다(self):
        """Space 는 고른 개체를 지우는 키다. 속 이름(`summary`)에 초점을 두고
        Space 로 펴는 것이 거기까지 가면 **이름을 찾다가 개체를 지운다** —
        검토 단축키는 글자 칸만 비켜 가고 단추·`summary` 는 안 비켜 간다."""
        page = self.open_review()
        self.pick_first()
        page.click('label[for="catsp-stack"]')
        head = page.locator(".sppop summary", has_text="Eucampia")
        head.focus()
        page.keyboard.press("Space")
        page.wait_for_timeout(700)
        self.assertEqual(page.locator(".sppop .spitem:visible").count(), 1,
                         "Space 로 속이 안 펴졌다 — 키가 목록에 안 닿았다")
        self.assertFalse(
            ObjectReview.objects.filter(mask_key=self.key).exists(),
            "목록에서 친 키가 검토 단축키로 갔다")

    def test_읽기_전용에서는_안_열린다(self):
        run = fx.add_other_engine(self.w.vp, label="yolo-시험")
        page = self.open_review(f"?batch={run.id}")
        self.click_image(300 + 27, 250 + 22)
        page.wait_for_timeout(200)
        if page.query_selector("#catbox-stack").is_hidden():
            self.fail("읽기 전용 화면에서 개체를 골랐는데 카드가 안 떴다")
        # 잠긴 칸의 label 은 playwright 가 "못 누르는 것" 으로 보고 기다린다 —
        # 사람은 그래도 누를 수 있으니 그대로 누른다
        page.click('label[for="catsp-stack"]', force=True)
        self.assertEqual(page.locator(".sppop:visible").count(), 0,
                         "잠긴 칸인데 목록이 열렸다")
