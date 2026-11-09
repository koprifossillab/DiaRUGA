# 252 — 분류에 Corethron 파편을 더한다

2026-11-09 · sclee · 같은 일을 먼저 한 것은 [237](20261025_237_eucampia-fragment-class.md)
(Eucampia 파편) · Corethron 자체는 [227](20261021_227_corethron-and-optional-hotkey.md)

## 무엇을

`corethron_frag` — 「Corethron 파편」. 마이그레이션 `0055` · `base.html` CSS 여덟 자리 ·
픽스처 줄 · 시험 다섯.

| 칸 | 값 |
|---|---|
| short · badge | `Cor파편` · `corf` |
| color | `237,156,246` (#ed9cf6) — Corethron 자홍을 흰색 쪽으로 40% (0051 과 같은 셈) |
| hotkey | 비움 — Corethron 을 따른다 |
| counted · is_taxon | 거짓 · 참 |
| sort_order | 9 (Corethron 과 같다. 차례가 `(sort_order, key)` 라 바로 뒤에 온다) |

## 왜

사용자 요청(11-09). 237 과 같은 이유다 — 속으로 알아본 것의 파편을 형태 파편에
섞어 붙이면 나중에 가를 수 없고, 갈라 둔 것은 언제든 합칠 수 있다.

## 버린 것

- **단축키 주기** — Corethron 은 227 에서 사용자가 키를 일부러 비웠다. 본체에 키가
  없는데 파편에만 주면 순환이 성립하지 않고, 다른 키를 하나 더 쓰게 된다
- **YOLO 대응표 고치기** — Corethron 은 「기타」(`other`)로 가고, 대응표에 없는
  분류도 `other` 로 간다. 파편도 그대로 같은 자리로 간다

## 남은 것

- **판** — 더하기만 하는 마이그레이션이라 뷰어만 올린다(파이프라인은 안 굽는다)
