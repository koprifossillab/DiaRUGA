# 생층서 기준면(FO·LO) 층 — 논문 14편의 연령 자료를 도감 속·종에 붙인다 (계획)

2026-09-18 · sclee · P20(출현 기록)·P24(학명 유효성) 다음 층.

사용자가 도감에 **멸종된 속을 대거 반입하는 중**이고, 그와 짝으로 **화석
규조의 최초 산출(FO)·최종 산출(LO) 연령**을 논문 열넷에서 뽑아 한 벌로 정리해
두었다(`N:\DiaRUGA\Diadiction\temp\` · 2026-09-18). 이것을 DB 에 넣고, **이미
등록된 속·종과 이어서 화면에서 보이게** 하는 것이 목표다.

## 1. 자료 — 여덟 파일은 판이 셋으로 자란 것이다

| 판 | 파일 | 무엇이 더해졌나 |
|---|---|---|
| 1 | `diatom_datums.{tsv,json}` · `규조_생층서_기준면_대조표.xlsx` (17:08) | 기준면 728행 · 대조표 · 대(zone) 44 · 참고문헌 14 |
| 2 | `규조_생층서_기준면_대조표_1.xlsx` (17:16) | **용어** 시트 (FO/FAD/FOD · LCO/LAAD · CONOP 두 모델 · s.l./var.) |
| 3 | **`diatom_datums_1.{tsv,json}` · `대조표_2.xlsx`** (17:26) | **MIS 대비** — LR04 경계표 + 행마다 MIS 열 다섯 |

**행 단위로 대조했다 — 1판과 3판의 728행은 공통 열 27개가 한 칸도 안 다르고,
3판은 열 다섯(`mis_stated`·`mis_calc`·`mis_kind`·`termination`·`mis_note`)이
더 있을 뿐이다.** 그래서 **3판(`_1.json` · `_2.xlsx`)만 원본으로 삼는다.**
앞 두 판은 지우지 말고 두되 반입은 안 본다. `verification_report.txt` 는
그 표를 만들며 원문과 대조한 기록(Warnock↔Cody 재인용 오차 5 · IODP↔원표 2 ·
Warnock 논문 내부 불일치 1)이고 **그 내용이 xlsx 「읽기 전에」 시트와 행의
`비고` 에 이미 들어 있다** — 따로 반입할 것이 없다.

### 1.1 행이 무엇인가

한 줄 = **출처 × 기준종 × 기준면(FO/LO/…)** 하나. 728행 · 출처 14 · 기준종
174(표기) · 기준면 종류 8(FO 390 · LO 312 · LCO 14 · FCO 5 · LCO(LAAD) 4 ·
AC1/AC2/AC+LCO 3). 열 27+5:

```
source/source_label/region      출처키 · 표시 이름 · 해역
species/species_printed         정규화 이름 · 원문 표기
datum · age · age_min · age_max · uncertainty · age_text
zone · code · chron · scheme · timescale      대 이름 · 대 코드(NPD 12·#D 120·SSODZ) · 지자기 크론 · 대 체계 · 시간척도
spread_myr · spread_n · spread_detail          연구 간 연령 폭 (파생)
pkg · pkg_atlases · plate_path · algaebase     오프라인 꾸러미 대조 (파생)
confidence · note · citation · url
mis_stated · mis_calc · mis_kind · termination · mis_note   (3판)
```

### 1.2 그대로 넣으면 안 되는 자리 — 실측한 것

**`(출처, 종, 기준면)` 이 열쇠가 아니다.** 209건이 겹친다. 세 갈래다.

1. **Cody et al. (2008) 은 한 사건에 값이 둘이다** — Average Range Model
   254행 · Total Range Model 206행. 어느 모델인지는 `note` 의 첫 토막에만
   있다(`Average Range Model · 기록 18 (10) · 평균 misfit 1.11 · 주요 지시종(+)`).
   용어 시트가 "인용할 때 어느 모델인지 반드시 밝힐 것" 이라 못 박은
   자리다 — **칸으로 세운다**(`variant`).
2. **Censarek (2002) 은 남부/북부 대 구분이 둘이다** — 같은 FO 가 SSODZ
   10.15 · NSODZ 10.3. 이쪽은 `code` 열에 있다. 같은 칸으로 간다.
3. **재인용이 원문 직접 파싱과 같은 출처키로 앉아 있다.** `cody2008` 460행
   중 48행이 `Warnock et al. (2025) Table 2 경유` 이고, 그중 42행은 직접
   파싱한 행과 (이름·기준면·연령) 이 똑같다 — **같은 값이 두 줄이다.**
   나머지 6행이 바로 `verification_report` 가 잡은 재인용 오차 5건 +
   `tetraoestruppii` 오식 1건이다. `crampton2016` 44행 · `gersonde_barcena1998`
   · `kato2024` · `winter2012` · `zielinski_gersonde2002` 는 **전부 재인용**
   이다(원문을 안 봤다). **경유 문헌을 칸으로 세운다**(`via`) — 화면이
   "Cody 2008 (Warnock 2025 경유)" 로 말해야 하고, 겹치는 42행을 그림에서
   두 번 찍으면 안 된다.

**`species`(정규화) 열이 다 정규화되어 있지 않다.** 종소명이 대문자인
것(`Rouxia Antarctica`·`Thalassiosira Antarctica`·`Eucampia Antarctica` —
Cody 표 파싱 산물), 낱말이 갈라진 것(`Denticulopsis prae dimorpha`), 대시가
붙은 것(`–Crucidenticula nicobarica`), 오식(`Shionodiscus tetraoestruppii var.`),
`var.` 없이 변종명만 붙은 것(`Thalassiosira tetraoestrupii reimeri`). 소문자로
내리고 붙이면 174 → 170 이 되는데 **넷이 합쳐지는 것이 다 맞는지는 표를 만든
사람이 확인한다**(§7). 비공식 이름 다섯(`Actinocyclus F Zielinski and Gersonde
2003` · `Fragilariopsis A Gersonde 1991` · `Fragilariopsis ritscheri A` ·
`Hemidiscus karstenii f1` · `Nitzschia 17 Schrader 1976`)은 **합치지 않는다** —
용어 시트가 `sp.` 류는 기준면으로 못 쓴다고 했지만 이것들은 Cody 가 이름 붙인
형태이고 사건 자체는 유효하다. 이명법(`binomial`)이 비고 이름만 든다.

**`var.` 는 떼지 않는다.** 용어 시트: "A. ingens 와 A. ingens var. ovalis 는
서로 다른 사건이고 연령도 다르다. 표를 합칠 때 var. 를 떼면 값이 뒤섞인다."
`AtlasEntry.binomial` 은 두 낱말이라 **맞추는 열쇠(`binomial`)와 표시 이름
(`name`)을 갈라 든다** — P24 가 `var.` 에서 걸린 것과 같은 자리다.

**파생 열은 안 넣는다.** `spread_*`(연구 간 폭)은 행들에서 계산되는 값이고,
`pkg`·`pkg_atlases`·`plate_path`·`algaebase` 는 **DB 가 이미 더 정확하게
안다**(`AtlasEntry`·`AtlasPlacement`·`TaxonName`). `mis_calc`·`mis_kind`·
`termination` 도 연령 → LR04 경계표 계산이라 화면이 한다(§4.4). 원문이 직접
말한 `mis_stated` 두 행만 자료다.

### 1.3 도감과 얼마나 맞는가 (저장소 `atlas/*.json` 으로 실측)

```
종   99 / 174 이 AtlasEntry.binomial 에 있다   (표의 pkg=O 73 종보다 많다 — 표는 꾸러미 v1.2.0 기준, 저장소는 2002 논문 둘이 더 들어와 있다)
속   25 /  31 이 AtlasEntry.genus 에 있다
없는 속 여섯   Alveus · Araniscus · Neobrunia · Proboscia · Raphidodiscus · Shionodiscus
```

**없는 속 여섯이 곧 사용자가 반입 중인 멸종 속 쪽에서 올 것이다.** 그래서
연결을 FK 로 매지 않고 **문자열(`genus`·`binomial`)로 느슨하게 잇는다** —
P20·P24 와 같은 이유(도감 반입이 `AtlasEntry` 를 통째로 갈아치운다)에 하나가
더 붙는다: **속이 나중에 들어와도 아무것도 다시 안 해도 이어진다.** 없는
종 75 는 화면에서 숨기지 않고 "도감에 없다" 로 표시한다 — 숨기면 도감 쪽
반입이 끝났는지 이 화면으로 알 수가 없다.

## 2. 스키마 — `Atlas`·`Occurrence` 와 같은 자리다 (사본 · 통째로 갈아치운다)

원본은 NAS 의 표(사람이 논문을 읽고 대조해 만든 것 — 재생성 불가지만 **그
판단은 NAS 파일에 남는다**). DB 는 사본이라 지우고 다시 만들어도 안전하다.
`TaxonName`·`Occurrence` 와 같은 논리.

```python
class Biodatum(models.Model):
    """생층서 기준면 하나 — 종 하나의 FO/LO 가 어느 문헌에서 몇 Ma 인가 (P28)."""
    reference = FK(Reference, CASCADE, related_name="biodatums")   # 출처. Reference 는 key 로 upsert 라 CASCADE 가 안전하다
    via = CharField(40, blank)          # 재인용 경유 문헌의 Reference.key. 원문 직접이면 빈 칸
    seq = PositiveIntegerField()        # 원본 표에서의 행 순서. (reference, seq) 가 열쇠 — AtlasEntry 와 같다
    name = CharField(120)               # 정규화 표시 이름. var./f./s.l. 유지 · 종소명 소문자 · 대시 제거
    name_printed = CharField(120)       # 원문 표기 그대로 (AtlasEntry.name 과 같은 규칙 — 안 고친다)
    binomial = CharField(120, blank, db_index)   # 두 낱말. AtlasEntry.binomial 과 맞추는 열쇠. 비공식 이름은 빈 칸
    genus = CharField(64, db_index)     # AtlasEntry.genus · atlas_genera 와 맞추는 열쇠
    infra = CharField(64, blank)        # `var. ovalis` · `s.l.` · `(plicate)` — 표시용
    datum = CharField(12)               # FO · LO · FCO · LCO · LCO(LAAD) · AC1 · AC2 · AC+LCO — 어휘를 못 박고 벗어나면 반입이 멈춘다
    variant = CharField(24, blank)      # `average`·`total`(Cody 두 모델) · `SSODZ`·`NSODZ`(Censarek) · `composite`(Crampton) · ''
    age = FloatField(); age_min = FloatField(); age_max = FloatField()   # Ma. 단일값이면 셋이 같다
    uncertainty = FloatField(null)      # ± Ma. 원문이 준 것만
    age_text = CharField(40)            # 원문 연령 표기 (`∼ 13–13.37` · `6430 ka` · `0.121 ± 0.003`)
    zone = CharField(120, blank); code = CharField(24, blank); chron = CharField(24, blank)
    scheme = CharField(80, blank); timescale = CharField(80, blank); region = CharField(120, blank)
    confidence = CharField(8)           # `high` 원문 대조 · `recite` 재인용 원문 대조 · `mid` 재인용 · `low` 웹 요약 1회
    primary = BooleanField(default False)   # 주요 지시종(+)/주요 기준면(#) — Cody·Yanagisawa 가 표시한 것
    mis_stated = CharField(80, blank)   # 원문이 직접 말한 MIS (2행뿐)
    note = TextField(blank)             # 나머지 전부 — 모델 기록 수·misfit·환산 근거·원문 오식

    class Meta:
        constraints = [UniqueConstraint(fields=["reference", "seq"])]
        indexes = [Index(fields=["binomial"]), Index(fields=["genus"]), Index(fields=["genus", "datum"])]


class Biozone(models.Model):
    """생층서대 하나 — 상·하한 연령과 그것을 정의하는 기준면 (P28). 44행. 그림의 바탕띠."""
    scheme = CharField(80)              # `warnock2025` · `censarek-ssodz` · `censarek-nsodz` · `npd`
    seq = PositiveIntegerField()
    name = CharField(120)               # `Thalassiosira lentiginosa Partial Range Zone` · `NPD 12`
    top_ma = FloatField(null); base_ma = FloatField(null)   # Censarek·NPD 는 하한만 있다 — 상한은 위 대의 하한. **null 을 0 으로 채우지 않는다**
    top_def = CharField(120, blank); base_def = CharField(120, blank)
    author = CharField(200, blank)
```

**`Reference` 를 그대로 쓴다.** 출처 14 는 문헌이라 P20 의 `Reference`(key
upsert · `kind="paper"`) 에 앉는다. 다만 지금 `Reference` 에는 `url` 이 없고
`authors` 가 64자다 — **`url` 한 칸을 더한다**(blank · `db_default=""` · 더하기
만이라 파이프라인 이미지는 안 굽는다). 해역·대 체계·시간척도·확보 경로·
이용 조건은 **출처가 아니라 행의 성격**이라(Fujiwara 는 원문, IODP 는 환산 병기)
행에 둔다 — 728행이라 중복 비용이 없다. 출처 수준 메모(`basis`·`licence`)는
`Reference.note` 로.

출처키는 표의 `출처키` 를 그대로 `Reference.key` 로 쓴다(`warnock2025`·
`cody2008`·`censarek704B`…). `import_occurrence.py` 의 `REF_KEY` 처럼 **스크립트에
못 박고 벗어나면 멈춘다** — 표에 새 출처가 생기면 사람이 열쇠를 정한다.
**`censarek2002` 와 도감 `2002-censarek-miocene`, `zielinski2002b` 와
`2002-zielinski-rouxia` 는 같은 논문이다** — FK 로 안 맨다(`Occurrence.source`
가 문자열인 것과 같다). 화면이 `Reference.key` ↔ `Atlas.key` 대응표 하나를
들고 "이 논문의 도판 →" 링크를 낸다.

**MIS 경계표(LR04, 104+ 경계)는 DB 가 아니라 코드다** — `web/viewer/mis.py`.
`antarctica.py`(해안선)·`atlas.py` 의 `AREA_OF` 와 같은 성격: 바뀌지 않는
참조표이고 계산에 쓰는 것이라 행으로 두면 질의만 는다. 오프라인 꾸러미도
같은 표를 JS 로 굽는다.

## 3. 반입 — 도감·출현·학명과 같은 두 단계 문

```
1) NAS  Diadiction/temp/diatom_datums_1.json  →  atlas/biodatum/datums.json    tools/parse_biodatums.py  (호스트 · 저장소에 커밋)
2) atlas/biodatum/datums.json                 →  DB                            ops/import_biodatums.py   (dbrun.sh · 컨테이너 안)
```

`atlas/*.json` 옆에 두면 `import_atlas.py` 의 `glob("*.json")` 이 삼킨다(P20
이 당했다) — **`atlas/biodatum/` 으로 한 단 내린다**(`atlas/occurrence/` 와
나란히).

### 3.1 `tools/parse_biodatums.py` 가 하는 것

- 3판 JSON 을 읽는다(`_1.json`). tsv·xlsx 는 안 본다 — 같은 내용이고 JSON 이
  `sources`·`zones_warnock2025`·`mis_reference` 까지 든다. **대(zone) 44행은
  JSON 에 Warnock 것 6 만 있고 Censarek 20·NPD 18 은 xlsx 「대(zone)」 시트에만
  있다** — 이것만 xlsx 에서 읽는다(`openpyxl` 은 venv 에 있다)
- 이름 정규화: 종소명 소문자 · 앞 대시 제거 · `prae dimorpha` 붙이기 · `var.`
  없는 변종명은 `var.` 을 붙이지 않고 그대로 `infra` 로 → `name`·`binomial`·
  `genus`·`infra`. **합쳐지는 것(174→170)을 전부 찍고 멈춘다** — `--accept`
  없이는 안 쓴다. 표를 만든 사람이 넷을 보고 결정한다(§7)
- `note` 첫 토막에서 `variant` 를, `경유`/`재인용` 에서 `via` 를 뽑는다. 뽑은
  뒤 `note` 에서 그 토막을 뺀다(칸으로 갔으니 두 벌이 안 된다)
- `confidence` 넉 자를 코드로(`high`·`recite`·`mid`·`low`). **모르는 문구가
  오면 멈춘다** — 다섯째 등급이 조용히 `mid` 로 뭉개지면 안 된다
- `datum` 어휘 여덟 밖이면 멈춘다
- `age_min ≤ age ≤ age_max` 가 아니면 멈춘다(`Rouxia constricta LO 0.43–0.05`
  같은 자릿수 오타가 표에 남아 있으면 여기서 걸린다 — 표는 원문값으로 고쳐
  넣었다고 하지만 검사는 둔다)
- 출력 JSON 에 원본 파일의 sha256 을 넣는다(`Atlas.source_sha256` 과 같은
  이유 — 어느 판에서 왔는지가 파일에 있어야 한다)
- `--dry-run` 이 기본 통계(출처별 행 수 · 재인용 수 · 도감에 없는 종·속)를
  찍는다

### 3.2 `ops/import_biodatums.py`

`import_occurrence.py` 를 베낀다. `Reference` upsert(키는 `REF_KEY` 못 박기) →
`Biodatum.objects.all().delete()` → `bulk_create` → `Biozone` 같은 순서.
**한 트랜잭션.** `--dry-run`. `dbsync.sh` 로 `/srv` 에 옮기고 `dbrun.sh` 로
돈다. **판 먼저, 반입 나중** — JSON 이 이미지에 실려 가므로 배포된 이미지가
그 파일을 들고 있어야 컨테이너 안에서 읽힌다(도감 반입에서 매번 그랬다).

### 3.3 `ops/check_db.py` 13번

- 출처(`reference`)가 `Reference` 에 있고 `kind="paper"` 인가
- `binomial` 이 비어 있지 않은 행 중 `AtlasEntry.binomial` 에 없는 종 수 —
  **경고이지 오류가 아니다**(멸종 속 반입이 끝나면 줄어야 하는 숫자. 표로
  찍어 두면 그쪽 반입이 어디까지 왔는지 이 숫자로 본다)
- `genus` 가 `AtlasEntry.genus` 에 없는 속 (지금 여섯)
- `age_min ≤ age ≤ age_max` · `datum` 어휘 · `(reference, seq)` 빈 자리
- `via` 가 비어 있지 않으면 그 키도 `Reference` 에 있는가

## 4. 화면 — 두 자리, 그리고 속 목록

### 4.1 도감 검색 카드에 「기준면」 줄 (P20 의 「출현」 줄 옆)

`atlas_search` 가 이미 `_occurrences_by_binomial()`·`_taxon_names_by_binomial()`
로 한 번에 묻는 자리다 — `_biodatums_by_binomial()` 을 그 옆에 둔다.
카드에 한 줄:

```
기준면   FO 4.9 Ma (Censarek 2002 · SSODZ) · LO 1.26–1.43 Ma (Cody 2008 · 전범위)  … 7건 →
```

- **`binomial` 정확 일치**(168 의 규칙 — `icontains` 면 `Rouxia` 가
  `Rouxia antarctica` 것까지 끌어온다). `var.` 행은 종 카드에 걸리되
  `infra` 를 붙여 낸다
- 없으면 줄을 안 낸다(168 · "이 종은 기준면이 없다" 로 읽히면 안 된다)
- 재인용 행은 "(Warnock 2025 경유)" 를 단다. 신뢰도 `low` 는 흐리게
- `→` 가 4.2 화면으로 그 속을 들고 간다

### 4.2 `/atlas/datums/` — 범위 그림 (새 화면)

**이것이 "가시적으로" 다.** 속 하나(또는 검색어)를 고르면 그 속의 종들이
세로 시간축(Ma · **아래가 오래된 쪽** — 층서 관례) 위에 **FO 에서 LO 까지
막대**로 놓이고, 막대 양 끝에 출처마다 점을 찍는다. 같은 사건을 여러 문헌이
다르게 본 것(대조표 시트의 "연구 간 폭")이 **점의 흩어짐으로 보인다** —
표의 `spread_*` 열을 안 넣는 이유가 이것이다.

- 거르개: **권역**(남극해 / 북서태평양·일본 — 출처의 `region` 으로 가른다 ·
  `atlas.py` 의 `AREAS` 와 같은 자리에 표를 둔다) · **속**(4.3 목록) ·
  **출처**(체크) · **재인용 포함** (기본 꺼짐 — 42행 겹침) · **Cody 모델**
  (평균 / 전범위 · 기본 평균 — Warnock Table 2 가 그것을 인용한다)
- 바탕띠: 그 권역의 `Biozone`(Warnock/Winter 대 · SSODZ · NSODZ · NPD). 대
  경계를 정의한 기준면이 곧 이 그림의 점이라 띠와 점이 맞물려야 하고, 안
  맞으면 자료 오류다(`check_db` 가 아니라 눈이 잡는 자리)
- 0~1.3 Ma 구간은 MIS 눈금을 오른쪽에 덧댄다(`mis.py`). **환산 MIS 를 값으로
  적지 않는다** — 표의 「MIS 대비」 시트가 두 번 경고한 자리(시간척도가 다르다
  · 단계 폭이 오차보다 좁다). 눈금일 뿐이다
- 종 이름을 누르면 도감 카드(`/atlas/?q=`)로, 출처를 누르면 `Reference` 의
  url/DOI 로, 그 논문에 도판이 있으면(`censarek2002`·`zielinski2002b`) 도감
  도판으로
- 그림은 서버가 SVG 로 낸다(`core.html` 의 깊이 축과 같은 식 — 인라인 SVG ·
  JS 없이도 선다). 색은 `base.html` 토큰(테마 둘 · 107). 그리기 전에 dataviz
  스킬을 연다
- **시간척도가 다른 값을 한 축에 놓는다는 것을 화면이 말한다.** 「읽기
  전에」 ① — 같은 기준면도 척도에 따라 수십만 년 다르다. 점 하나에 마우스를
  올리면 `age_text`·`timescale`·`confidence` 가 뜬다. 축 하나로 뭉개는 것을
  피하려면 척도마다 축을 세워야 하는데 그것은 이 화면이 할 일이 아니다 —
  말로 적고 값은 그대로 둔다

### 4.3 속 목록 — "연결" 이 여기다

`atlas_genera`(211속 `<select>` · 196)에 **기준면이 있는 속을 표시한다**
(이름 뒤 `· 기준면 12`). 4.2 의 속 목록은 같은 함수에서 **기준면이 있는
속만** 거른 것이다. 없는 속 여섯은 도감 목록에는 아직 없고 4.2 목록에는
"도감에 없다" 표시로 있다 — 멸종 속 반입이 끝나면 표시가 저절로 빠진다.

### 4.4 안 만드는 화면

- **코어 화면의 깊이–연령 대비**(이 코어의 어느 깊이에서 어느 기준면이 걸리나)
  — 코어에 연령 모델이 없다(P17 의 코어 자료는 깊이별 물성뿐). 사용자가
  RS21·GC03 의 연령 모델을 넣는 날 다시 본다
- **기준면을 화면에서 고치는 UI** — P24 와 같다. 원본은 NAS 표이고 고치려면
  표를 고쳐 다시 반입한다

## 5. 오프라인 꾸러미 (v1.3.0 · 따로 낸다)

`build_offline_atlas.py` 가 `atlas/biodatum/datums.json` → `data/biodatum.js`
로 싣고 카드의 「기준면」 줄을 같은 규칙으로 낸다(196 의 "두 화면이 다른 말을
하면 안 된다"). 범위 그림은 서버 SVG 를 JS 로 옮겨야 하므로 **첫 판에는
안 넣는다** — 줄만 맞추고, 그림은 다음 판.

## 6. 순서

| 단계 | 무엇 | 어디서 | 커밋 |
|---|---|---|---|
| 1 | `tools/parse_biodatums.py` · `atlas/biodatum/datums.json` · §7 확인 | 호스트 | 하루치 브랜치 |
| 2 | `Biodatum`·`Biozone` · `Reference.url` · 마이그레이션 `0045`(더하기만) · `ops/import_biodatums.py` · `check_db` 13번 · `mis.py` · 시험 | 호스트 venv 시험 | 하루치 브랜치 |
| 3 | 카드 줄(4.1) · 속 목록(4.3) · `/atlas/datums/`(4.2) · 브라우저 시험 | 사본 DB 개발 서버 | 하루치 브랜치 |
| 4 | 판(`v0.30.0` · 마이그레이션 있음) → 배포 → `dbsync.sh`/`dbrun.sh import_biodatums.py` → `check_db` | admin | — |
| 5 | 오프라인 v1.3.0 | 호스트 | 따로 |

2·3 을 한 판에 싣는다 — 스키마만 나간 판은 화면에 아무것도 안 보여 "됐다" 를
확인할 길이 없다. 1 은 2 와 함께 커밋해도 되지만 §7 의 답이 먼저다.

## 7. 구현 전에 표를 만든 사람이 확인할 것

1. **`temp/` 는 임시 자리다.** 반입 원본을 `Diadiction/datums/` 같은 제자리로
   옮기고 그 경로를 파서에 박는다 — `temp/` 를 원본으로 두면 다음 정리에
   사라진다(v1.1.0 이 그렇게 없어졌다 · 196)
2. 종소명 대문자 넷을 소문자 쪽과 **합쳐도 되는가** — `Rouxia Antarctica`(Cody
   직접 4행) ↔ `Rouxia antarctica`(Cody 경유·Crampton·Warnock). 값을 보면 같은
   종이 맞는 것 같지만(Average LO 1.495 가 양쪽에 같다) 표를 만든 사람이 안다
3. `Shionodiscus tetraoestruppii var.`(Warnock Table 2 재인용 · `var.` 뒤가
   비었다) 은 Cody 원문의 `Thalassiosira tetraoestrupii reimeri` 와 같은
   사건인가 — 같으면 `via` 행으로 붙이고, 모르면 그대로 둔다
4. 재인용 42행(값까지 같은 것)을 **DB 에 넣되 그림에서 기본 숨김**으로 할지,
   반입에서 아예 뺄지 — 이 계획은 넣고 숨기는 쪽이다(표에 있는 것을 반입이
   조용히 버리면 표와 DB 가 다른 말을 한다)
5. Winter & Iwai (2002) 28행은 표 스스로 "교정 연령으로 인용하지 말 것" 이라
   했다 — 넣고 흐리게(`low`)가 이 계획이다. 빼는 것이 맞으면 말해 달라
6. 권역을 어떻게 가를지 — 출처 14 를 남극해(11)와 북서태평양·일본(3:
   `yanagisawa1998`·`iodp346`·`fujiwara2008`)으로 나누는 것이 자연스럽다.
   `Site.area` 의 `한국`·`남극` 과는 다른 축이라(북서태평양은 한국 도감 권역이
   아니다) 이름을 `atlas.py` 의 `AREAS` 에 안 섞고 따로 둔다
7. **`2002-censarek-miocene`·`2002-zielinski-rouxia` 가 `AREA_OF` 에 없다**
   (207 이 안 넣었다 — 도감 화면에서 "권역 미정" 으로 서 있을 것이다). 이
   작업과 무관하지만 같은 파일을 만지므로 함께 `antarctic` 으로 넣는다

## 8. 버린 것

- **`Occurrence` 에 얹기** — 출현 기록은 "어디서 보고됐다" 이고 기준면은
  "언제 나타나고 사라졌다" 다. 지역 칸에 연령을 넣는 식으로 우겨 넣으면
  `region` 질의가 깨지고 두 모델의 값·재인용을 둘 자리가 없다
- **`AtlasEntry.extra` JSON 에 넣기** — 도감 반입이 통째로 갈아치우는 표라
  다음 `import_atlas.py` 가 지운다. 게다가 도감에 없는 종 75 는 놓을 항목이
  없다
- **종 × 기준면 하나로 접어 "대표 연령" 을 두기** — 어느 문헌·모델·척도인지가
  값의 일부다(「읽기 전에」 ①·용어 시트의 CONOP 두 모델). 접으면 그 정보가
  없어지고, 접는 규칙을 사람이 정해야 하는데 표를 만든 사람은 접지 않았다.
  화면이 점의 흩어짐으로 보여 주면 된다
- **MIS 를 행에 넣기** — 3판이 붙인 열 다섯 중 원문이 직접 말한 것은 두 행이고
  나머지는 LR04 환산이다. 환산은 시간척도가 다른 자로 잰 것이라 표 스스로
  "참고용" 이라 했다. 눈금으로만 그린다
- **`Reference` 를 안 쓰고 `BiodatumSource` 를 새로 두기** — 문헌은 문헌이다.
  `Occurrence` 가 논문을 인용하는 날 같은 행을 가리켜야 한다
