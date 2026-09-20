# 논문 캡션의 속명 약자를 편다 — `C. centralis` 가 도감에 그대로 있었다 (211)

2026-09-20 · sclee · 브랜치 `work/20260920-sclee` · 210 다음. 사용자가
"C. centralis 같은 약어 표현이 도감에 그대로 나오는 이유가 뭐지?" 라 물었고,
원인을 짚자 "이건 고쳐야 되는 버그지" 라 했다.

`tools/parse_paper_atlas.py`(`GENUS_ABBREV`·`expand_abbrev`) ·
`atlas/2017-yun-ulleung.json` · `atlas/2001-park-bransfield.json` ·
`web/viewer/templates/viewer/atlas.html`(원문 표기 줄) · 시험 셋.

## 왜 그대로였나 — 두 층이 겹쳤다

**원본이 캡션을 인쇄된 대로 옮긴 표다.** 논문 도판 항목은 `tools/plate_figs.py`
의 `CAPTIONS` 에서 나오는데, 논문은 같은 속이 이어지면 둘째부터 속을
약자로 쓴다 — 2017 울릉은 `Figs A-C. Coscinodiscus asteromphalus; Figs D–E.
C. centralis; …`. 169 가 그때 정했다: "캡션 표기는 고치지 않고 그대로
저장했다". 약자가 무엇을 받는지(`A. octonarius` → *Actinocyclus*, `Th.` →
*Thalassionema*)는 부록 표로 검산해 **devlog 에만** 적었고 표에는 안 넣었다.

**파서는 이름을 안 고치는 것이 규칙이다.** `parse_atlas.name_fields()` 는
"표제어 자체는 안 고친다" 이고 `genus` 는 첫 낱말이라 `C.` 가 된다.
`harvest_worms.binomial()` 은 **종소명만 검사하고 속 토큰의 모양은 안 본다** —
`binomial` 까지 `C. centralis` 로 나갔다. 안 펴는 이유가 있었다: Schmidt
색인에서 약자를 **그 쪽에 나온 다른 속**으로 잘못 편 것이 가장 큰 고장
갈래였다(119·160). 그래서 "`genus` 는 색인에 적힌 그대로" 로 못 박았다.

그 둘이 합쳐져 DB 에 속이 `A.`·`C.`·`F.`·`T.`·`Th.` 인 항목이 **14건** 있었다
(2001 브랜스필드 9 · 2017 울릉 5). 화면에서는:

- 속 필터 드롭다운에 `A.`·`C.`·`F.`·`T.`·`Th.` 가 **속처럼 따로 뜬다**
- `binomial` 이 `C. centralis` 라 `TaxonName`·`Occurrence`·`Biodatum` 을
  정확 일치로 짚는 자리(`data.py` `_taxon_names_by_binomial` 등)에 **하나도
  안 걸린다** — 14건 전부 0. 169 는 `Coscinodiscus centralis` 를 대조표에서
  "있다" 고 세었는데, 그것은 사람이 눈으로 맞춘 것이고 화면은 못 맞췄다
- 같은 논문 안에서 **같은 종이 둘로 갈렸다** — 2001 의 `C. fasciolata (Ehrenberg)
  Brown`(pl.1 fig.6)과 `Cocconeis fasciolata (Ehrenberg) Brown`(fig.32),
  `T. antarctica Comber`·`F. ritscheri Hustedt` 도 같다

## 어디를 고쳤나 — 표가 아니라 파서

**`CAPTIONS` 는 그대로 둔다.** 그것은 옮긴 표이고 `source_sha256` 이 그 표를
가리킨다(약자를 펴고 나서 해시가 바뀌길래 되돌렸다 — 해시는 편 사본이 아니라
`CAPTIONS[paper]` 로 잰다). 논문·색인의 "원문 그대로" 규칙은 **표제어에
대한 것**이고, 캡션의 약자는 표제어가 아니라 **바로 앞 이름을 가리키는
조판 관행**이다 — 그것을 그대로 두는 것은 원문을 지키는 것이 아니라 논문이
읽히기를 바란 대로 안 읽는 것이다.

`parse_paper_atlas.build()` 가 훑기 전에 `expand_abbrev()` 로 사본을 편다.
규칙은 논문의 것 그대로 — **캡션 순서(도판, 그림)로 바로 앞에 나온, 같은
글자로 시작하는 온전한 속**. `A.` 는 `Actinoptychus`(F·G)와
`Actinocyclus`(H)가 다 앞에 있어도 더 가까운 H 다. `Th.` 는 `Thalassiosira`
도 `Th` 로 시작하지만 더 가까운 `Thalassionema` 다.

**그 결과를 `GENUS_ABBREV` 와 대조한다** — 사람이 원문으로 확인한 표(2017 은
169 의 부록 표 검산, 2001 은 같은 논문의 다른 그림이 온전한 이름으로 확인해
준다). **규칙과 표가 어긋나거나 표에 없으면 `SystemExit`** — 119 의 고장은
규칙이 조용히 다른 속을 집은 것이라, 규칙 하나로는 안 되고 검산이 있어야
한다. 약자가 없는 논문은 표에 안 적는다 — 새 논문에 약자가 나오면 표에 없어
멈추고, 그때 사람이 확인해 적는다. `build()` 끝에서 `genus` 가 `.` 로 끝나는
항목이 남아 있으면 또 멈춘다.

**원문 표기는 `extra.original_note` 에 남긴다** — "`C. centralis` 로 적혀 있다
(pl.1 fig.D·E)". 동남극 도판집이 오식 메모에 이미 쓰는 칸이라 새 칸을 안
만들었다. 그런데 **뷰어 `atlas.html` 은 이 칸을 한 번도 안 내고 있었다**
(오프라인 `app.js` 만 냈다) — 동남극의 8건도 그동안 웹에서는 안 보였다. 이번에
「원문 표기」 줄을 달았다.

## 달라진 것

```
2017 울릉    항목 13 (그대로) · 5건 폄
2001 브랜스필드 항목 41 → 38 · 9건 폄 · 셋이 합쳐졌다 (Cocconeis fasciolata ·
             Thalassiosira antarctica · Fragilariopsis ritscheri)
도감 항목 합계 2,751 → 2,748
```

편 13개 이명법을 백업 사본(`DiaRUGA_20260920_172001.db`)의 표와 맞춰 보니
**13개 전부 `TaxonName` 에 이미 있었다**(12 accepted · *Thalassiosira gracilis*
는 synonym → *Shionodiscus gracilis*). 기준면이 8종(*Actinocyclus octonarius* 6 ·
*F. ritscheri* 7 · *F. curta*·*F. kerguelensis*·*T. antarctica* 5 …), 산출이
1종(*Coscinodiscus centralis* 4)에 붙는다 — 그동안 `C.` 뒤에 숨어 있던 것.

2001 의 `T. eccentrica (Ehrenberg) Cleve`(pl.1 fig.17)와 `Thalassiosira eccentrica
(Ehr.) Cleve`(pl.2 fig.3)는 **여전히 둘이다** — 속은 펴졌지만 저자 표기가
다르다. 그것은 논문이 실제로 다르게 찍은 것이라 이번 일이 아니다.

## 시험

- `tools/test_parse_atlas.py` 9절 — 편다 · 가장 가까운 같은 글자 속
  (`Actinoptychus` 가 아니다) · 두 글자 약자 · 원문 표기를 남긴다 · 표와
  어긋나면 멈춘다 · 표에 없으면 멈춘다
- `test_atlas.py` — 저장소 JSON 에 `genus` 가 `.` 로 끝나는 항목이 없다
  (되살려 보면 14건이 잡힌다) · 합계 2,748
- `test_atlas_search.py` — `original_note` 가 「원문 표기」로 난다

## 배포 뒤

`atlas/*.json` 은 이미지에 실려 가므로 판을 낸 뒤 **`dbrun.sh import_atlas.py`**
— 통째로 갈아치우는 반입이라 옛 `C.` 항목은 저절로 빠진다(도감 19 · 항목
2,748). `import_taxon_names.py` 는 안 돌려도 된다 — 13개가 이미 있다.

## 배포 — `v0.31.1` · 18:37

`main` push → CI 통과 → 태그 → CI 가 굽고 밀었다 → `backup_db.py --note
before-211` → `deploy.sh v0.31.1`(smoke 통과) → `import_atlas.py`(도감 19 ·
항목 **2,748** · 자리 3,400) → `check_db` — 경고는 "개체 종명이 도감에 없다
2건"(`Centrales indet.` 2 개체) 하나이고 배포 전 사본에도 같은 2건이라
새 것이 아니다. 슬라이드 18개 전수 네 화면과 도감·기준면 전부 200.
`/atlas/?q=Coscinodiscus+centralis` 에 「원문 표기」 줄이 나고, `Fragilariopsis
curta` 에 기준면 줄이, `Cocconeis fasciolata` 에 크롭 둘(fig.6·32)이 붙는다.
속 필터에 `A.`·`C.`·`F.`·`T.`·`Th.` 가 없다. 테스트 인스턴스(`testdeploy.sh`)
에도 올리고 같은 반입을 컨테이너 안에서 돌렸다(테스트 compose 엔 `dbtool`
서비스가 없어 `docker exec diaruga-test-web-1 python ops/import_atlas.py`).

## 덤 — 웨델해 1990 의 AlgaeBase 답 18종

사용자가 배포 중에 `N:\DiaRUGA\Diadiction\temp\algaebase_todo_20260920_ANSWERED.md`
를 두고 "하는 김에 이것도 반영해" 라 했다. 209 가 낸 조회 목록(18종)의 답이다
— `names/algaebase/weddell1990_answered_20260920.md` 로 옮기고
`tools/parse_taxon_names.py` 의 넷째 소스로 얹었다. 표가 **다섯 칸**이다
(`| [x] | 이름 | 자리 | 판정 | 비고 |`) — 정규식을 하나 더 두고 자리 칸을
건너뛴다. 체크 안 된 `[ ]` 행(2절 "원문에서 볼 것" 셋)은 답이 아니라 안
읽는다 — 처음엔 읽혀서 21 이 나왔다.

18종 전부 새 열쇠라 기존 판정은 하나도 안 바뀌었다(2,108 → **2,126**).
*Nitzschia* 화석종 열넷 가운데 아홉이 *Fragilariopsis* 로 재조합(synonym),
넷(*lacrima*·*praecurta*·*cylindrica*·*pusilla*)은 *Fragilariopsis* 조합이
AlgaeBase 에 없어 *Nitzschia* 가 유효(accepted), *praeinterfrigidaria* 와
*Katathiraia aspera* 는 없음(absent). 18종이 전부 `1990-gersonde-weddell`
도감 항목의 `binomial` 과 맞는다. 원문 확인 셋(*Rouxia antarctica* 계급 ·
*S. tetraoestruppii var.* · *A. maccollumii* 속)은 그대로 남았다.

`import_taxon_names.py --src /data3/DiaRUGA/tmp/taxon_names_20260920.json`
으로 운영·테스트에 넣었다 — **`v0.31.1` 이미지엔 2,108 짜리가 실려 있다.**
다음 판이 저장소의 `taxon_names.json` 을 싣기 전까지 기본 `--src` 로 돌리면
2,108 로 되돌아간다(207 때와 같은 자리 · HANDOFF 3.8).
