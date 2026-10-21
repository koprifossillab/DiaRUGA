# 228 — 멤버의 이미지를 조인으로 가져온다 (SQLite 식 깊이 한도)

2026-10-21 · `work/20261021-sclee-ui` · sclee

## 무엇이 났나

v0.33.3 배포(17:22) 뒤 판 세션이 `check_db` 를 돌렸더니 **8번 「같은 개체 묶음」이
죽고 그 뒤가 안 돌았다.**

```
check_db.py:476  links = list(qs.prefetch_related("members__image"))
sqlite3.OperationalError: Expression tree is too large (maximum depth 1000)
```

16:50(v0.33.2 뒤)에는 끝까지 돌았다. 이번 판은 `check_db` 4번만 바꿨고 이 자리는 그대로다.

## 왜

컨테이너에서 그 질의 하나만 읽기로 돌려 실패한 SQL 을 찍었다.

```
SELECT … FROM "viewer_image" WHERE ("viewer_image"."id" = %s OR "viewer_image"."id" = %s OR …)
params 1002 · OR 1001 · IN 0
```

**Django 5.2 는 앞쪽 FK(`members → image`)를 미리 부를 때 IN 목록이 아니라 `=` 를
OR 로 이어 붙인다.** OR 하나가 식 트리 한 단이라, 이미지가 1,000 장을 넘으면 SQLite 의
`SQLITE_LIMIT_EXPR_DEPTH`(1000)에 걸린다. 그날 묶음 2,483 개의 멤버가 이미지 **1,002 장**을
가리켰다 — 369cm 검토로 넘어선 것이다. 17:00 사본에서는 1,000 장 아래라 호스트에서 안 났다.

헷갈린 자리 둘을 먼저 지웠다 — SQLite 판(호스트 3.45.1 · 컨테이너 3.46.1)과 Django 설정
(`max_query_params` 999 · 변수 한도 250000 · 식 깊이 1000)은 같았고, 맨 IN 목록은 둘 다
20,000 개까지 멀쩡했다. 역방향 FK(`candidates` 등)는 IN 으로 묻어 안 걸린다 — `check_db`
1번이 검출 2,900 개로 돌았다.

## 고침

`MEMBERS_WITH_IMAGE = Prefetch("members", queryset=ObjectReview.objects.select_related("image"))`
— 멤버를 가져오는 질의에 이미지를 **조인**한다. 둘째 질의가 없어져 목록이 아무리 커도 식이
안 깊어진다. 같은 모양이 넷이었다.

| 자리 | 묻는 범위 | 지금 위험 |
|---|---|---|
| `ops/check_db.py` `check_links` | **DB 전체** | 죽었다 |
| `data.object_facts` (카탈로그·검토 화면) | 슬라이드 하나 | 369cm_100 이 377 장 — 검토가 늘면 닿는다 |
| `data.link_mains` | 슬라이드 하나 | 같다 |
| `data._reelect_removed_reps` | 고른 개체 | 낮다 |

`migrate/` 의 일회성 둘(`reelect_removed_reps.py` · `refix_drawn_reps.py`)은 안 고쳤다 — 지난
이전기다. 다시 돌릴 일이 있으면 같은 자리를 고친다.

## 확인

`test_many_member_images.py` 셋 — 이미지 1,002 장 · 개체 501 × 멤버 둘을 `bulk_create` 로
세우고 `check_links` · `object_facts` · `link_mains` 를 부른다. **옛 코드로 돌리면 셋 다 같은
오류로 죽는다.**

**배포 뒤 `/srv` 의 `check_db.py` 를 새 것으로.**
