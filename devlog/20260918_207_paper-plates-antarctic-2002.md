# 남극 논문 도판 둘 — Censarek 2002 · Zielinski 2002 (207)

`tools/plate_figs.py` · `tools/crop_plates.py` · `tools/parse_paper_atlas.py` ·
`tools/parse_atlas.py` · `atlas/2002-*.json`. P22(169~177)·P23 다음.
사용자가 `N:\DiaRUGA\Diadiction\temp\` 에 남극 논문 여섯을 두고 "도판 넣을
만한 거 있는지" 물어서 훑었고, 도판이 있는 둘을 "그렇게 해줘" 로 땄다.

## 여섯 중 둘

| 파일 | 무엇 | 도판 |
|---|---|---|
| **Censarek 2002** (Thermal history…, Ber. Polarforsch. 430, 176쪽) | ODP 689·690·1088·1092 마이오세 규조 층서(박사논문 2장) | **Plate 1~5 · 101개** |
| **Zielinski et al. 2002** (Mar. Micropaleo. 46:127–137) | *Rouxia leventerae*·*R. constricta* LOD | **Plate I · 14개** |
| Yanagisawa & Akiba 1998 (Refined Neogene…) | 북서태평양 신제3기 대 코드 | 없음 — 층서표·범위도 |
| Warnock et al. 2025 (J. Micropal. 44) + sup.zip | IODP 382 생층서 개정 | 없음 — 보충은 Table S1 |
| Cody et al. 2008 (Thinking outside the zone) | CONOP 복합 범위 | 없음 |
| Fujiwara et al. 2008 (地質調査研究報告 59) | 센다이 주변 연대 | 없음 |

**한 번 저해상도로 훑고 끝내지 않았다**(169 의 교훈) — 여섯 다 `pdftotext`
로 `Plate`·`Fig` 줄을 세고, 텍스트가 없는 것(1998 은 1비트 CCITT 스캔)은
쪽 전체를 contact sheet 로 렌더해 눈으로 확인했다. `.tab` 하나는 PANGAEA
연령 모델(704B) 자료라 도판과 무관하다.

## 결과

```
Censarek  Plate 1~5 (8·39·27·12·15) · 그림 101개 · 잘라낸 것 101 · 이름 101
Zielinski Plate I (14)               · 그림  14개 · 잘라낸 것  14 · 이름  14
AlgaeBase 대조(sp. 하나 뺀 50개 형태) 있다 16 · 없다 34
```

`Diadiction/plate/plate_2002cen_pl<1-5>_fig<NN>_<학명>.png` ·
`plate_2002zie_pl1_fig<NN>_<학명>.png`. PDF 는 `Diadiction/papers/` 로
옮겼다(`2002_censarek_so_miocene_thesis.pdf` · `2002_zielinski_rouxia_lod.pdf`,
원래 이름은 `_original_names.md`).

## 캡션 — 텍스트 레이어는 OCR 이라 원문을 렌더해 대조했다

Censarek 은 텍스트 레이어가 있지만 **OCR 산출**이다(1비트 JBIG2 스캔 위에
얹힌 것). 캡션 쪽 다섯(pdf 72·74·76·78·80)을 150dpi 로 렌더해 전부
읽었다 — OCR 이 셋을 틀렸다: `praecurfa`→`praecurta`(Plate 3 fig19·20),
`splendide`→`splendida`(Plate 5 fig5), `Thalassiofrix`→`Thalassiotrix`
(Plate 5 fig15). 175~177 에서 본 것과 같은 모양(그럴듯해서 안 걸리는
오류)이다.

**원문 자체의 흔들림은 그대로 뒀다**(176·177 방침): Plate 3 fig27
`Hemidiscus kastenii`(보통 *karstenii*), Plate 5 fig15 `Thalassiotrix
miocenica`(보통 *Thalassiothrix*). **Plate 5 는 원문이 fig4 자리를 "6."
으로 찍었다**(6 이 둘) — 도판에서 4번 자리의 *Rouxia peragalli* 를
`4` 로 두고 `CAPTIONS` 주석에 적었다.

Zielinski 는 8비트 원본이라 텍스트가 정확하다. 캡션이 1–7·8–14 두 묶음뿐
이고 그림마다 시료(1094A-4H-3 14–15 cm 등)가 붙어 있는데 1994 와 같은
이유로 `CAPTIONS` 에는 안 실었다.

## 크롭 — 자동 검출이 처음으로 거의 그대로 먹혔다

169~177 아홉 편은 전부 손으로 잰 것이 기본값이었다. **이 둘은 자동
검출(`--probe`) 상자 수가 그림 수와 거의 맞았다** — 9/8·42/39·28/27·
14/12·16/15·15/14. 더 잡힌 것은 매번 머리줄(상자 1)과 **한 그림이 두
판인 자리**(초점을 달리한 같은 개체)였다. 이유는 자료의 모양이다:
Censarek 은 1비트 스캔이라 배경이 순백이고 그림끼리 떨어져 있으며,
Zielinski 는 사진 격자다(1996 Plate 1 도 격자만 맞았다).

손으로 보탠 것은 다섯 상자뿐이다:
- Plate 2 fig3 — 작고 옅어 문턱을 못 넘었다. 격자를 얹어 쟀다
- Plate 2 fig12·33·34, Plate 4 fig7 — 두 판이 한 그림. 자동 상자를
  `ASSIGN` 에서 `None` 으로 걷고 `MANUAL_BOXES` 에 둘을 합친 상자 하나
  (한 그림 = 파일 하나. `ASSIGN` 에 같은 번호를 둘 적으면 같은 파일명에
  덮어써서 뒤엣것만 남는다)

**겹침 검사 → 자르기 → 대조 시트**(174·177 의 표준 절차)를 그대로 갔다.
겹침·빠짐·남음 전부 0. 자른 115장을 판마다 8열 시트로 훑었다 — 이웃이
pad 안으로 넘어온 자리는 있어도 자기 번호·모양이 어긋난 것은 없다.

## 도감 JSON 까지 — P23 의 문 그대로

`PAPER_META` 에 둘을 더하고 `parse_paper_atlas.py` 로 `atlas/2002-censarek-
miocene.json`(항목 49 · 자리 101)·`atlas/2002-zielinski-rouxia.json`(항목 2 ·
자리 14)을 냈다. 크롭 115장은 `sync_paper_plate_images.py` 로
`/data3/DiaRUGA/atlas/<key>/crops/` 에 옮겨 뒀다(P23 과 같은 순서 — 판이
나가기 전에 이미지가 자리에 있어야 한다).

**`Rouxia sp.1 Gersonde` 가 `unreadable` 로 떨어졌다.** 원문이 `sp.1` 을
띄어쓰기 없이 조판해 `GENUS_ONLY = {"sp.", …}` 집합에 안 걸린다. 캡션을
고치면 원문대로 두는 방침이 깨지고, `unreadable` 로 두면 "이름이
상했다" 는 뜻이 된다(P15 8.4 가 가르라고 한 자리). **판별을 넓혔다** —
`parse_atlas.py` 에 `sp.\d+` 정규식 하나(`GENUS_ONLY_RE`). 다른 도감
JSON 에는 그 모양이 없어 결과가 안 바뀐다(전수 확인). `test_parse_atlas`
에 한 줄 더했다.

`test_atlas` 가 도감 수·항목 수를 못 박고 있어(16 · 2,650) 18 · 2,701 로
올렸다.

## AlgaeBase 대조

`sp.` 하나를 뺀 50개 형태를 로컬 대조표(`algaebase_day*.md`, 1,845종)에
grep 했다. **있다 16 · 없다 34** — `paper_plates_pending.md` 에 얹었다.

- **속째 없는 것 넷** — `Cavitatus`·`Crucidenticula`·`Mediaria`·
  `Thalassiotrix`(원문 오식 — 조회는 *Thalassiothrix* 로)
- **`Fragilariopsis` 는 속은 있는데 마이오세 12종이 통째로 없다.** 대조표가
  도감 셋(한국 담수·Schmidt·동남극 제4기)에서 뽑혀 남극 마이오세 층서
  종을 원래 안 담는다 — 1993 의 `Chaetoceros`·1996 의 `Nitzschia` 와
  같은 모양(속 하나가 범위 밖이면 그 속이 통째로 걸린다)
- **`Rouxia leventerae` 는 대조표에 "AlgaeBase 에 없음" 으로 이미 조회돼
  있다.** Zielinski & Gersonde 2002 가 세운 종인데 AlgaeBase 가 안 담고
  있다는 뜻 — 이 논문이 그 종의 원기재라 이름의 근거는 이 도판이다
- `Denticulopsis praedimorpha`·`Mediaria splendida` 는 1991 항목과 겹친다

## 남은 것

- **판을 내고 `dbrun.sh import_atlas.py` 를 돌린다** — `atlas/*.json` 은
  이미지에 실려 가므로 판이 먼저다(P23·147 과 같은 사정). 반입 뒤 도감
  16 → **18**(작업 이름 포함), 항목 2,650 → **2,701**, 자리 3,186 →
  **3,301** 이 되어야 한다
- **Censarek 8비트 원판** — 같은 도판이 Censarek & Gersonde 2002(Mar.
  Micropaleo. 45:309–356)에 실렸을 가능성이 크다. 구해지면 Plate 2·3 의
  작은 개체(*Denticulopsis*·*Fragilariopsis*)를 그쪽으로 갈아 끼운다.
  지금 크롭은 300dpi 망점이라 큰 개체는 읽히지만 작은 것은 거칠다
- 오프라인 도감 꾸러미(v1.2.0)는 이 둘을 모른다 — 다음에 구울 때 따라간다

## 같은 날 저녁 — AlgaeBase 답 32종을 반입했다 · `v0.29.3`

낮에 넘긴 `temp/algaebase_todo_antarctic_2002.md`(32종)가 18:03 에
답으로 돌아왔다(`_ANSWERED.md` · `filled 2.json` · `raw.tsv`·`raw2.tsv` ·
정리 노트). **32건 전부 판정** — 그대로 유효 14 · 교정하면 유효 7 · AlgaeBase
도 "추가 조사 필요" 6 · 이명 3 · 교정 후 이명 1 · 없음 1. "성글 것" 이라던
예상과 달리 없는 것은 *F. praeinterfrigidaria* 하나였고 2026년 갱신이 12건 —
AlgaeBase 가 남극 마이오세 종을 최근에 손봤다.

답변 파일은 `Diadiction/names/algaebase/antarctic2002_*_20260918.*` 로
옮기고(ASCII 이름 · `temp/` 는 비워도 되는 자리다) `tools/parse_taxon_names.py`
에 둘째 소스로 얹었다 — `from_paper_plates()` 가 경로·source 를 받게 넓혔을
뿐 규칙은 08-31 과 같다. 손으로 잡은 자리 둘:

- **`HOLD` — *Nitzschia denticuloides*.** AlgaeBase 가 *N. amphibia* f.
  *frauenfeldii*(담수종의 품종)로 넘기는데, 남극 중기 마이오세 층서 지표종이
  담수종 품종일 리 없다 — 정리 노트 5절이 동명이의 오연결로 보고 반영하지
  말라고 했고 worms_master 도 같은 이유(Hustedt 판 vs Schrader 판)로 `확인
  필요` 를 뒀다. `unassessed` 로 두고 그 사실을 note 에 남겼다
- **`EXTRA` — *Nitzschia reinholdii*(1985 Plate).** 답변 표엔 없지만
  `raw2.tsv` 에서 *F. reinholdii* 와 함께 ***F. kanayae*** 로 확인됐다.
  종소명이 통째로 바뀌어 기계적으로는 못 잇는 자리라 손으로 실었다

**자기 자신을 가리키는 synonym 이 하나 나왔다** — `Crucidenticula kanayae
var. kanayae` 의 열쇠는 `binomial()` 이 `C. kanayae` 로 뭉뚱그리는데 답이
굵게 `C. kanayae` 라 "이명 → 자기 자신" 이 됐다. 굵은 이름의 binomial 이
열쇠와 같으면 `accepted` 로 낸다(08-31 의 156종에는 그 모양이 없어 결과가
안 바뀐다 — 전수 확인).

`taxon_names.json` 1,999 → **2,031** 건(accepted 1,010 · synonym 750 ·
unassessed 151 · absent 120). `dbrun.sh import_taxon_names.py --src
/data3/DiaRUGA/tmp/taxon_names_20260918.json` 으로 18:26 에 운영에 넣었다 —
`check_db` OK, `/atlas/?q=Rouxia+peragalli` 에 "이명" 칩이 뜬다. **판에는
아직 안 실렸다** — 다음 판이 저장소의 `taxon_names.json` 을 싣기 전까지
기본 `--src` 로 다시 돌리면 1,999 로 되돌아간다(HANDOFF 3.8).

옆 세션이 짚은 `AREA_OF` 누락은 `v0.29.3`(18:23) 으로 나갔다 — 카드에는
"권역 미정" 이 안 뜨고(쪽을 구운 책 도감만 카드가 선다) `?area=antarctic`
거르개에서 그 종이 조용히 빠지고 있었다. `test_atlas_area` 7번이 이제
`atlas/*.json` 마다 권역을 본다.
