# 262 · 오프라인 도감 v1.5.0 — 기재문

2026-11-15 · sclee · `work/20261115-sclee-offline` · 앞 판은 v1.4.0([244](20261029_244_offline-atlas-v140-crops-grid-compare.md), 10-29)

## 왜

257 이 도감·논문의 기재문을 서버 도감 화면에 얹었는데 꾸러미에는 없었다. 사용자가
11-15 에 "오프라인 꾸러미에 기재문을 넣을 수 있으면 다음 단계에서 판을 올리면서 넣자" 고 정했다.

## 한 것

- **v1.4.0 코드가 main 에 없었다.** 10-29 에 굽고 `work/20261029-sclee` 에 push 만 해 둔
  채였다(커밋 둘 · devlog 244). 이 브랜치가 그것을 합쳐 받는다 — 충돌 없음
- **굽는 쪽** (`tools/build_offline_atlas.py`) — 색인 `atlas/<이름>.json` 옆의
  `atlas/descriptions/<같은 이름>.json` 을 항목의 `extra` 에 얹는다. 반입기
  (`ops/import_atlas.merge_descriptions`)와 **같은 규칙의 두 벌**이다: 열쇠는 `seq`,
  표제어가 어긋나면 옆 종에 붙은 것이라 **멈춘다**. 그 파일들의 해시가
  `MANIFEST.json` 의 `index_sha256` 에 `descriptions/<이름>.json` 으로 들어간다
- **화면** (`offline_assets/app.js`·`app.css`) — 항목 카드의 「기재」 펼침 칸(기계가 읽은
  원문이라는 말 · OCR 문장 · 텍스트 레이어 · 출처 줄)과 비교 화면의 "기재 (기계가 읽은
  원문)" 줄. 뷰어 `atlas.html`·`atlas_compare.html` 과 같은 모양이다
- **뷰어 도감 화면이 출처 줄(`description_source`)을 안 내고 있었다.** 257 8절이 근사
  일치로 얹은 것을 "출처 줄에 적는다" 고 했는데 그 줄이 화면에 없었다 — 근사로 얹은
  것이 정확히 맞은 것과 구별되지 않았다. `atlas.html` 에 줄을 더하고 시험에 박았다.
  **`v0.41.0` 에는 안 실렸다 — 다음 판이 싣는다**

## 구운 것

| | v1.4.0 | **v1.5.0** |
|---|---|---|
| 항목 | 2,748 | 2,748 |
| 기재문 | 0 | **1,575** (한국 510 · Schmidt 862 · 논문 넷 203) |
| 쪽 · 크롭 | 1,881 · 2,584 | 1,881 · 2,584 |
| 꾸러미 | 1.5 GB · 파일 6,355 | 1.5 GB · 파일 6,355 (+0.85 MB) |
| 글자만 한 파일 | — | 4.7 MB |

`/nfs/temp-share/DiaRUGA/Diadiction/offline/` 에 `diadiction-offline-v1.5.0/` · `.zip` ·
`diadiction-index-v1.5.0.html`. 커밋 `c3a0346` 에서 구웠다. v1.2.0~v1.4.0 은 그대로 뒀다.

## 확인

- `--limit 8` 로 구운 것을 헤드리스 크로미움으로 열어 `Achnanthes minutiss` 를 찾고 「기재」
  칸을 펼쳤다 — OCR 문장 · 텍스트 레이어 · 출처 줄이 나오고 콘솔 오류가 없다
- 완전판의 `data/entries.js` 에 기재문 1,575건 · `missing_placements` 0 · `missing_crops` 0
- **완전판을 브라우저로 열어 보지는 않았다.** 비교 화면의 기재 줄도 눌러 보지 않았다

## 안 한 것

- 영문 토글 — 꾸러미에는 아직 없다(244 와 같다)
- 기재문 안 검색 — 검색은 이름만 본다
