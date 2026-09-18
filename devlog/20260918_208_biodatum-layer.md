# 생층서 기준면 층을 만든다 — 반입·스키마·범위 그림 (208)

2026-09-18 · sclee · 브랜치 `work/20260918-sclee` · 계획은
[P28](20260918_P28_biodatum-layer.md). 1~3단계를 같은 날 했다. 4단계(판 ·
배포 · 반입)는 admin, 5단계(오프라인 v1.3.0)는 따로.

`tools/parse_biodatums.py` · `atlas/biodatum/datums.json` · `web/viewer/models.py`
(`Biodatum`·`Biozone`·`Reference.url`) · 마이그레이션 `0045` ·
`ops/import_biodatums.py` · `ops/check_db.py` 13번 · `web/viewer/mis.py` ·
`web/viewer/biodatum.py` · `data.py` · `views.py` · `urls.py` ·
`templates/viewer/biodatum.html` · `atlas.html` · `tests/test_biodatum.py` (19).

## P28 §7 의 답 (사용자, 09-18)

| # | 물음 | 답 | 한 것 |
|---|---|---|---|
| 1 | `temp/` 는 임시 자리 | 알아서 옮겨라 | `Diadiction/datums/` 로 옮겼다(최종판 셋 + report · 앞 판은 `_old/`) · README 를 두었다 |
| 2 | 종소명 대문자 넷 합치기 | 합쳐도 된다 | `MERGE_OK` 넷에 못 박았다 — 새 합침이 생기면 파서가 멈춘다 |
| 3 | `S. tetraoestruppii var.` ↔ `T. tetraoestrupii reimeri` | **함부로 합치지 마라.** 반입 뒤 AlgaeBase 에서 전부 다시 확인한다 — 목록을 만들어 달라. 도판 논문에서 이미 확인한 종은 빼라 | 합치지 않았다. `--recheck` 가 `taxon_names.json` 에 판정이 없는 이름을 낸다 → **85 이름** · 같은 날 저녁에 답이 와서 반입했다(아래 · `names/algaebase/biodatum_*_20260918.md`) |
| 4 | 재인용 겹침 42행 | 넣고 숨기되 **참고문헌은 남겨라** | DB 에 다 넣고 그림은 기본 숨김 · 경유 문헌이 점·표·참고문헌 절에 남는다 · 「재인용 겹침도」 체크로 다 그린다 |
| 5·6 | Winter & Iwai · 권역 | (답 없음 → 계획대로) | 넣고 흐리게 · 남극해 / 북서태평양·일본 |
| + | 권역 거르개 | **체크박스로** — 태평양을 남극과 함께 볼 때가 있다 | 체크박스 둘. 둘 다 끄면 안 그리고 말한다 |

## 1단계 — 파서 (`tools/parse_biodatums.py`)

`diatom_datums_1.json`(728행)과 xlsx 「대(zone)」 시트(43행 — JSON 에는 Warnock
6 만 있다)를 읽어 `atlas/biodatum/datums.json` 을 낸다. 원본 두 파일의 sha256 을
넣는다(`Atlas.source_sha256` 과 같은 이유).

**칸으로 올린 것** — `note` 첫 토막의 모델(`Average/Total Range Model` ·
`Composite mid-age`) → `variant`, `code` 의 `SSODZ/NSODZ` → `variant`,
`Warnock … 경유/재인용` → `via`, `주요 지시종(+)/주요 기준면(#)` → `primary`.
올린 토막은 `note` 에서 뺀다(두 벌이 되면 화면이 같은 말을 두 번 한다).

**이름** — 종소명 소문자 · 앞 대시 제거 · `prae dimorpha` 붙이기(`NAME_FIX`) ·
`var.`/`s.l.`/`(plicate)` 는 `infra` 로 남기고 `name` 에 든다. 맞추는 열쇠
`binomial` 은 `harvest_worms.binomial()`(도감과 같은 규칙 — `Chaetoceras` →
`Chaetoceros` 까지 같이). **종소명이 두 글자 이하면 형태 기호로 본다**
(`Actinocyclus F …`·`Fragilariopsis A …`) — 처음엔 `f` 가 정규식을 통과해
`Actinocyclus f` 라는 이명법이 생겼다. 비공식 이름 셋은 `binomial` 이 빈 칸.

**멈추는 자리** — 기준면 어휘 여덟 밖 · 신뢰도 문구 넷 밖 · `age_min ≤ age ≤
age_max` 아님 · `MERGE_OK` 밖의 합침 · 모르는 경유 문구 · 모르는 대 체계.

```
기준면 728행 · 출처 14 · 이름 170(표기 208) · 재인용 102 · 대 43
```

## 2단계 — 스키마·반입·검사

P28 §2 그대로. `Biodatum`(열쇠 `(reference, seq)`) · `Biozone`(`(scheme, seq)`)
· `Reference.url`. **더하기만이라 파이프라인 이미지는 안 굽는다.**

`ops/import_biodatums.py` — `Reference` 는 `REF_KEYS` 열넷으로 못 박고 upsert,
두 표는 통째로 갈아치운다, 한 트랜잭션, 넣고 세어 어긋나면 되돌린다. 사본 DB
(09-18 18:20 백업)에 넣어 봤다 — 문헌 14 · 기준면 728 · 대 43, 두 번 넣어도
같다.

`check_db` 13번 — 경유 키가 `Reference` 에 있는가 · 출처가 `paper` 인가 ·
연령 순서 · **도감에 없는 기준종·속은 오류가 아니라 숫자**(멸종 속 반입이
진행되면 줄어야 한다: 지금 종 63/143 · 속 6/31). 12번의 "출현 기록이 없는
문헌" 이 기준면 출처 열넷을 잡길래 `biodatums__isnull=True` 를 더했다.

**`Reference` 의 열쇠는 `key` 이고 pk 가 아니다.** `reference_id__in=keys` 로
썼다가 `Field 'id' expected a number but got 'kato2024'` — 질의는
`reference__key`, 행에서는 `b.reference.key`(`select_related`).

`web/viewer/mis.py` — LR04 경계 227 + 종결면 7 을 코드로. `stage_of(0.121)`
= 5 · `stage_of(0.135)` = 6 (Termination II 를 사이에 둔 그 예).

## 3단계 — 화면

### 카드 줄 (`atlas.html`)

`_biodatums_by_binomial()` — `_occurrences_by_binomial()` 옆. 정확 일치, 없으면
줄을 안 낸다, 카드에는 Cody 평균 모델만(전범위는 그림에서 고른다), 값 같은
재인용은 뺀다. 「→ 그림」이 `/atlas/datums/?q=<이명법>` 으로 간다. 속 목록의
항목에 `· 기준면 N` 이 붙는다(`atlas_genera` 가 `biodatum_counts_by_genus()`
를 한 번 묻는다). 머리줄 「도감 · N종」 옆에 「기준면」 링크.

### `/atlas/datums/` (`biodatum.html` · `viewer/biodatum.py` · `data.biodatum_chart`)

**무엇을 그릴지는 `data.py` 가 정하고 자리는 `biodatum.layout` 이 잡는다**
(Django 를 안 부른다). 세로 시간축(아래가 오래된 쪽) · 종마다 한 열 · 가장
젊은 LO ~ 가장 오래된 FO 막대 · 사건마다 문헌의 점(연령 폭은 세로선) · 대
띠(그 권역의 체계 — Winter/Warnock · SSODZ · NSODZ · NPD, 하한만 있는 체계는
위 대의 하한이 상한) · 축이 1.5 Ma 이하면 오른쪽에 MIS 눈금과 종결면.
서버가 인라인 SVG 로 낸다(JS 는 마우스 설명 상자뿐). 아래에 점 전부의 표와
참고문헌 절(DOI · 도판 있는 논문은 「도판 →」).

거르개 — 권역 체크박스 둘 · 속 목록(기준면 있는 속만 · 도감에 없는 속은
그렇게 적는다) · 이름 검색 · Cody 모델(평균/전범위/둘 다) · 재인용 겹침 ·
출처 체크. **체크박스는 다 끄면 아무것도 안 보내므로** 폼이 `f=1` 을 함께
보내고, 그것이 없으면(처음 열었거나 카드 링크로 왔거나) 둘 다 켠다.

**색은 사건 종류(FO·LO·그 밖)이지 문헌이 아니다** — 문헌 열넷은 색으로 못
가른다. 세 색은 dataviz 팔레트 1·2·3 슬롯이고 밝은·어두운 면 둘 다 검증기를
돌렸다(all-pairs 통과 · 밝은 면의 aqua 가 3:1 아래라 표가 함께 있다). 재인용은
속 빈 점, `low` 는 흐리게, 주요 지시종은 큰 점 — 색만으로 가르지 않는다.
토큰은 `:root`(어두운 값) + `[data-theme="light"]` — 미디어 쿼리 아님(201).

### 당한 것 둘

- **`base.html` 의 `.bar { height: 4px }` 가 SVG `rect.bar` 에 먹었다.**
  Chromium 은 `height` 를 CSS 로도 받아 막대가 전부 4px 이 됐고, `.grid { display:
  grid }` 는 격자선에 걸렸다. **SVG 안의 클래스는 전부 `bd-` 접두사**로 갈았다
  — 화면 CSS 는 `base.html` 이 어떤 선택자로 잡고 있는지 보고 쓴다(CLAUDE.md).
- **`{# #}` 는 한 줄짜리다** — 두 줄로 썼더니 폼 위에 주석이 글자로 떴다.
  `{% comment %}` 로.

## 재인용 겹침 — 42 가 아니라 41

Warnock Table 2 가 옮긴 Cody 값 48행 중 (이름·기준면·연령) 이 같은 것은 42
지만 **모델까지 같은 것은 41** — LO *Hemidiscus karstenii* 0.305 는 평균 모델
이라 적고 전범위 값을 옮긴 것이라(표의 「읽기 전에」가 짚은 오차) 겹침이 아니라
재인용 오차 쪽이다. `_dedupe_via` 가 `(출처, 이름, 기준면, 모델, 연령)` 로
가르므로 이것은 그림에 남는다 — 맞는 동작이다.

## 시험 (`test_biodatum.py` · 19)

재인용 겹침 기본 숨김/켜기 · Cody 모델 · 권역 비면 없음 · 도감에 없는 종 ·
화면(점·숨김 수·권역 없음 문구·`f` 없는 링크) · 카드 줄(정확 일치 · 없으면 안
냄) · 속 목록 `기준면 N` · 배치(하한만 있는 대 · MIS 눈금 · 막대 열림) · MIS
단계 · 파서(이름·note·MERGE_OK·어휘) · **저장소 JSON 이 그대로 들어온다**
(14·728·43 · 겹침 41 · 13번 통과) · 검사가 어긋난 것을 잡는다.
브라우저 밖 994개 통과. 헤드리스 크로미움으로 두 테마 캡처 — 콘솔 오류 0.

## 같은 날 저녁 — AlgaeBase 답 85 이름을 반입했다 · `v0.30.0`

낮에 넘긴 재확인 목록 85 이름이 18:47 에 답으로 돌아왔다(`_ANSWERED.md` ·
정리 노트). **85행 전부 판정** — 그대로 유효 53 · AlgaeBase 도 "추가 조사
필요" 9 · 이명 8 · 없음 7 · 철자·조합 교정 5 · 비공식 3. 이번엔 `filled.json`
이 없고 마크다운 표뿐이라 `tools/parse_taxon_names.py` 에 `from_answered_md()`
를 더했다 — 판정 문구를 읽는 규칙은 `_verdict()` 하나로 떼어 JSON 쪽과 같이
쓴다. 답변 파일 셋은 다른 AlgaeBase 답과 같은 자리
`Diadiction/names/algaebase/biodatum_{todo,answered,notes}_20260918.md` 로
옮겼다(`datums/README` 가 가리킨다).

**85행이 77 열쇠가 된다** — 비공식 셋은 열쇠가 없고(종소명 두 글자 이하 ·
`split_name()` 과 같은 규칙 · 처음엔 `binomial()` 이 `Actinocyclus f` 를
냈다), 변종·`s.l.`·`(plicate)` 다섯은 종으로 뭉뚱그려진다(같은 열쇠에 판정이
갈리면 파서가 멈춘다 — 실측 0). `taxon_names.json` 2,031 → **2,108**, 더하기만.

정리 노트가 짚은 것을 손으로 잡았다:

- **`HOLD` — *Actinocyclus maccollumii*.** AlgaeBase 가 *Diploneis
  mollenhaueri* 로 넘기는데 중심규조가 깃돌말의 이명일 수 없다 — 207 의
  *N. denticuloides* 와 같은 동명이의 오연결. `unassessed` 로 두고 note 에 남겼다
  (같은 종소명의 *Denticulopsis maccollumii* 가 2002 건에서 "확인 필요" 였다)
- **`REMARK`** — *Rouxia antarctica* 는 AlgaeBase 가 종이 아니라 *R. peragalloi*
  의 변종으로만 잡는다(판정은 그대로 synonym · 계급은 원기재로 확인할 것),
  *S. tetraoestruppii* 는 p 하나 더 붙은 오식이고 `var.` 뒤가 비어 있어 합치지
  않는다(absent 그대로)
- *Cosmiodiscus insignis* → *Thalassiosira insigna* 는 표 안의 #62 와 같은 종 —
  `TaxonName` 에서는 synonym 행이 accepted 행을 가리키는 것으로 이미 한 줄이다
- *Thalassiosira* → *Shionodiscus* 재조합 넷은 종마다 판정 그대로(일괄 치환 없음)

**그림에도 붙였다** — `biodatum_chart()` 가 `_taxon_names_by_binomial()` 을 한
번 물어 종마다 `taxon` 을 들고, 표의 이름 칸에 「이명」 칩(현재 통용명)과
「AlgaeBase 에 없다」 를 낸다(유효·미확인은 낼 것이 없다 — 도감 카드와 같은
규칙). 도감에 있는 종은 카드 쪽 칩이 이미 있으니 도감에 없는 63종에서 이것이
유일한 자리다. 시험 3 (22).

이 판(`v0.30.0`)이 `0045` 와 함께 새 `taxon_names.json`(2,108)을 처음 싣는다 —
배포 뒤 `import_biodatums.py` 와 `import_taxon_names.py`(기본 `--src`) 둘을 돌린다.

## 안 한 것

- 오프라인 꾸러미 v1.3.0 (P28 §5) — 카드 줄만 맞추는 것도 다음에
- 코어의 깊이–연령 대비 (P28 §4.4) — 연령 모델이 없다
- 점이 같은 자리에 겹칠 때 옆으로 비키기 — 마우스 설명과 표로 대신한다
- 영문 토글 — 도감 도판 화면 넷에만 있는 것이라 여기도 안 달았다
