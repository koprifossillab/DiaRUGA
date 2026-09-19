# 웨델해 논문 하나(Gersonde & Burckle 1990)를 도판·기준면으로 반입하고, 기준면 그림의 왼쪽 축에 기·세·절과 MIS 를 세운다 (209)

2026-09-19 · sclee · 브랜치 `work/20260918-sclee` · 판 `v0.30.1`. 208(기준면
층) 다음. 사용자가 `N:\DiaRUGA\Diadiction\datums\` 에 PDF 하나를 두고 "반입하고
도판·기준면을 뷰어에 보이게, 그리고 왼쪽 축을 숫자만 말고 IUGS 지질시대를
절(stage)까지 · 우리가 정리한 MIS 도 세로축에" 라고 했다. 배포까지 이
세션이 한다(admin 이 주말).

`tools/plate_figs.py` · `tools/parse_paper_atlas.py` · `atlas/1990-gersonde-weddell.json` ·
`web/viewer/atlas.py`(`AREA_OF`) · `tools/parse_biodatums.py` ·
`atlas/biodatum/datums.json` · `ops/import_biodatums.py`(`REF_KEYS`) ·
`web/viewer/gts.py`(새) · `web/viewer/mis.py`(`stage_bands`) · `web/viewer/biodatum.py` ·
`templates/viewer/biodatum.html` · 시험 둘의 수.

## 논문 — Gersonde & Burckle 1990, Proc. ODP Sci. Results 113 ch.43

웨델해 Maud Rise(Holes 689B·690B)의 신제3기 규조 대 16 을 고지자기에 직접
대비한 첫 논문. **Table 1**(대 16 · 상·하한 정의 · "other important datums") ·
**Table 2**(종 28 의 연령 범위 · 남극해 열) · **Plate 1~5**(그림 99). 시간척도는
Berggren et al. (1985) — 표의 다른 열넷과 같은 축에 놓되 점의 시간척도가
다르다는 것을 화면이 말한다(208 과 같은 방침).

PDF 는 `Diadiction/papers/1990_gersonde_burckle_odp113_weddell.pdf` 로 옮겼다
(`datums/` 는 표의 자리라 · 원래 이름은 `_original_names.md`). 29쪽 · ABBYY OCR
텍스트 레이어 · 8비트 회색조.

## 도판 — 207 의 절차 그대로, 손 상자는 아홉

캡션 다섯 쪽을 220dpi 로 렌더해 대조했다(OCR 산출이라 그냥 믿지 않는다 — 207).
OCR 이 틀린 것 셋: `dementia` → **`clementia`**(Plate 2 fig22–23 · *Nitzschia
clementia* Gombos 1977), `Nitzschiapraecurta`·`Crucidenticulapunctata`(띄어쓰기).
원문 자체는 깨끗하다.

`--probe` 상자 수: 28/27 · 25/23 · 16/19 · 14/16 · 15/14. 더 잡힌 것은 축척
막대(p26 · p29)·그림의 조각(p25 fig17 의 오른쪽 가장자리 · p26 fig11 이 가로
띠로 둘)이고, 모자란 것은 **닿아 있는 원반 쌍**(p27 2+3·4+5·16+17, p28
1+2·3+4)이다. 쌍은 `MANUAL_BOXES` 에 둘로 갈라 적었다(겹치는 폭은 pad 로
이웃이 조금 들어오는 정도 — 207 과 같다). 자른 99장을 판마다 9열 시트로
훑었다 — 번호·이름 어긋난 것 0.

`atlas/1990-gersonde-weddell.json` — 항목 50 · 자리 99(*T. inura* 가 Plate 3·5
에 걸쳐 4자리). `Hemidiscus sp. 1~3`·`Rouxia sp. 1~3` 은 속 수준
(`GENUS_ONLY_RE`), `Thalassiosira majuramica-torokina group` 도 속 수준. 크롭은
`/data3/DiaRUGA/atlas/1990-gersonde-weddell/crops/` 로 옮겨 뒀다. `AREA_OF`
에 `antarctic`(207 의 구멍을 다시 안 만든다 — `test_atlas_area` 7번이 센다).
`test_atlas` 의 수 18 · 2,701 → **19 · 2,751**.

AlgaeBase 판정이 없는 18종(전부 *Nitzschia* 의 화석종·*Katathiraia*·
*Crucidenticula punctata*·*Cosmiodiscus intersectus*)은
`names/algaebase/weddell1990_todo_20260919.md` 로 냈다 — 답이 오면
`parse_taxon_names.py` 에 넷째 소스로.

## 기준면 — 출처 파일을 하나 더 두고 파서가 여럿을 읽는다

**14편 표(`diatom_datums_1.json`)에 행을 덧붙이지 않았다** — 그 표는 다른
사람이 만든 것이고 sha256 으로 판이 못 박혀 있다. 대신 같은 모양의
`Diadiction/datums/gersonde_burckle1990.json`(출처 1 · 행 61 · 대 16)을 두고
`parse_biodatums.py` 가 `SRC_JSONS` 를 차례로 읽는다. `seq`·합침 검사는 파일
사이로 이어 가고, 출처키가 겹치면 멈춘다. **대(zone)는 xlsx 시트가 아니라
JSON 의 `zones`** 에 든다(`read_zones_json` · 코드는 `ZONE_CODES` 로 못 박는다).

행은 Table 2 남극해 열(FO = 오래된 끝 · LO = 젊은 끝)에 Table 1 의 "other
important datums" 를 더한 것이다. 괄호 범위 `(4.2–4.1)` 는 `age` 가 중앙값,
`age_min`·`max` 가 양끝. `?`·`ca.`·`>`·`<` 는 `age_text` 에만 남는다.
**FAAD·LAAD 는 새 어휘를 안 만들고** `FCO`·`LCO(LAAD)` 에 넣고 note 에 원문
용어(`>15%`)를 적었다 — 어휘를 늘리면 `BIODATUM_KINDS` 의 choices 가 바뀌어
마이그레이션이 생긴다. *Nitzschia aurica* 의 `7.9*`(first consistent
occurrence)는 `FCO`. *Synedra jouseana* 는 FO 가 `Oligocene` 이라 LO 만.
*Cosmiodiscus insignis*·*Thalassiosira kolbei* 의 LO 는 Table 1 에만 있다.

```
기준면 728 → 789 · 출처 14 → 15 · 대 43 → 59 · 이름 170 → 183
check_db 13번: 도감에 없는 기준종 63/143 → 57/155 · 없는 속 6/31 → 5/32 (Raphidodiscus 가 도판으로 들어왔다)
```

`biodatum.py` 의 표 넷(`AREA_OF_REF`·`AREA_OF_SCHEME`·`SCHEME_LABEL`·
`ATLAS_OF_REF`)에 한 줄씩 — 참고문헌 절에 「도판 →」이 붙는다.
`test_biodatum` 의 수 (14, 728, 43) → **(15, 789, 59)**.

## 왼쪽 축 — 숫자 옆에 기·세·절 기둥과 MIS 기둥

숫자(Ma) 하나로는 "이 기준면이 어느 절에 드는가" 를 사람이 매번 환산해야
했다. **`web/viewer/gts.py`** — ICS International Chronostratigraphic Chart
v2023/09 의 신생대(66 Ma 까지)를 기(3)·세(7)·절(24)로 옮겼다. **색은 CGMW
공식 RGB 그대로**이고 테마를 안 탄다(지질도·층서표의 관례 — 바꾸면 못
알아본다), 글자만 늘 어두운 색. 한글 이름(대한지질학회 음역 + 절)은 마우스
설명에만. `mis.py`·`antarctica.py` 와 같은 자리 — DB 가 아니라 코드다.

- 기둥 셋(14·18·28px)이 Ma 숫자 오른쪽, 그 옆에 **MIS 기둥**(24px), 그 다음이
  대 띠. 오른쪽에 있던 MIS 눈금은 걷었다 — 한 축의 눈금은 한쪽에 모아 둔다
- 글자는 세로로 눕혀 아래에서 위로(층서표 관례). **띠에 안 들면 세 글자
  약자(`Gel.`), 그것도 안 들면 빈 칸** — 마우스 설명(`<title>`)에는 늘 전체
  이름과 경계 연령이 있다(`gts.label_for`)
- **축 길이가 5 Ma 를 넘으면 늘어난다**(640 → 20 Ma 에서 1040px ·
  `axis_height`). 안 늘리면 젤라절(0.78 Ma)이 20 Ma 축에서 25px — 약자도
  못 넣는다. 5 Ma 이하는 그대로라 208 의 그림은 안 바뀐다
- MIS 는 **띠**다(`mis.stage_bands` — `stage_ticks` 가 선이라면 이것은 그
  사이). 빙기(짝수 — LR04 의 번호 규칙 · 문자 단계도 같다)를 칠하고, 번호는
  띠가 7px 이상일 때만, 종결면(TI~TVII)은 2.5 Ma 이하 축에서만. LR04 끝
  (5.3 Ma)을 넘는 축은 거기까지만 칠한다 — 긴 축에서는 줄무늬로만 보이는데
  "여기까지가 LR04 다" 는 그것으로 읽힌다. **값이 아니라 눈금이다**(208 ·
  `mis.py` 머리말) — 문헌마다 시간척도가 달라 경계와 수십만 년 어긋날 수
  있고, 그 사실을 범례에 한 줄 적었다

헤드리스 크로미움으로 두 테마 · 세 축(2 · 5 · 20 Ma) 캡처 — 콘솔 오류 0.

## 시험

브라우저 밖 997 통과(수는 그대로 — 새 시험 없음, 두 시험의 수만 올렸다).
브라우저 포함 전체는 판을 내기 전에 돌린다(아래).

## 안 한 것

- **`Upper`(후기 플라이스토세)는 절 이름이 없다** — ICS 가 아직 `Upper` 로 둔다.
  그대로 냈다
- 종 열의 회전 글자가 그림 오른쪽 끝에서 잘리는 것(종이 하나일 때) — 208
  부터 있던 것이고 이번 일이 아니다
- 오프라인 꾸러미 v1.3.0 — 여전히 다음(P28 §5). 이 판의 도판·기준면도 거기
  실려야 한다
- Table 2 의 저위도·북태평양 열(Barron 1983·1985)은 이 논문의 자료가 아니라
  안 옮겼다 — 필요하면 Barron 원문으로
