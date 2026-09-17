# 198 · 화요일 슬라이드 6개의 SAM 검출이 이틀째 매분 죽고 있었다 — 파이프라인 이미지가 DB 스키마를 몰랐다

2026-09-17 · sclee · 브랜치 `work/20260917-sclee` · 파이프라인 `v0.5.2` → **`v0.5.3`**

사용자: *"화요일에 새로 넣은 슬라이드들이 검출이 안되어 있는데, SAM 검출 안되어
있는 건 왜야?"*

## 1. 무엇이 있었나

09-15 23:34 에 폴러가 `260915/RS21-*` 슬라이드 6개를 반입했고 그룹핑·합성은
끝났다. 23:42 부터 검출이 돌았는데 **저장 마지막 단계에서 죽었다** — 그리고
폴러는 1분마다 다시 불러 같은 곳에서 같은 오류로 죽기를 **4,212번** 반복했다.
09-17 10:52 까지.

```
g000_Snap-29923-29928_focused: raw=246 크기통과=171 최종=27 (봉상 14, 원형 13)  ← 검출은 됐다
  File "/srv/DiaRUGA/scripts/rebind.py", line 112, in rebind_viewpoint
    reviews = list(ObjectReview.objects.filter(image_id=..., batch=batch))
django.db.utils.OperationalError: no such column: viewer_objectreview.note
```

로그에는 4,212번 적혔고 `/healthz` 는 내내 `ok` 였다. 폴러가 "검출 실패" 를
로그에만 적기 때문이다(그리고 로그는 아무도 매일 안 읽는다).

## 2. 왜 — 114 가 놓친 갈래

CLAUDE.md 가 경고해 둔 그 함정이다: *"스키마를 조이는 마이그레이션은 뷰어·
파이프라인 판을 함께 올려야 한다."*

- 파이프라인 컨테이너는 스크립트만 `/srv/DiaRUGA/scripts` 것을 쓰고 **Django
  모델은 이미지 안의 `/app`** 을 쓴다(`DIARUGA_APP=/app` · 100)
- 도는 이미지 `v0.5.2` 는 **08-11 에 구운 것**이라 마이그레이션이 `0032` 까지이고,
  그 `models.py` 의 `ObjectReview` 에는 `note` 칸이 있다
- 08-12 의 `0036`(`v0.12.0` · 112)이 그 칸을 개체로 옮기고 **칼럼을 걷었다**
- 114 에서 "파이프라인은 `ObjectReview` 를 안 읽는다" 고 사본에서 실측하고
  **뷰어만 올렸다.** 그 실측이 지난 갈래는 `batch_plan.py` 와 시야 삭제였고,
  **`segment_diatoms.save_detection` → `rebind.rebind_viewpoint` 는 안 지났다.**
  거기가 검출을 저장할 때마다 `ObjectReview` 행을 `list()` 로 읽는 자리다 —
  08-10(100)부터 그랬다
- **08-09 이후 새 슬라이드가 없었다.** 그래서 한 달 넘게 안 드러났다. 114 는
  *"`pipeline/` 에 `ObjectReview` 를 읽는 줄이 하나라도 들어오면 그날로
  물린다"* 고 적었는데, 그 줄은 이미 들어와 있었다

**사람이 "안 닿는다" 를 코드를 읽어 확인하는 것은 그 순간의 코드 기준이고, 그
확인 자체가 갈래 하나를 놓쳤다.** 여기서 얻는 규칙은 하나다 — **판이 다른 두
이미지가 한 DB 를 쓰면, 어긋남은 사람이 아니라 기계가 대조한다**(4절).

## 3. 피해 — 실패가 행을 남겼다

`save_detection` 은 트랜잭션 둘이다(잠금을 짧게 쥐려고 · 055). **첫째
(`Detection` + `Candidate`)는 커밋되고 둘째(`is_current` 이동 + rebind)에서
죽었다.** 그래서 실패마다 행이 남았다:

| | 10:20 사본 | 지운 시점 |
|---|---|---|
| `Run` status=failed | 4,146 | **4,212** |
| `Detection` (전부 `is_current=0` · 이미지 6장) | 4,146 | 4,212 |
| `Candidate` | 888,626 | **902,772** |
| DB 파일 | 598 MB | **635 MB** (화요일 배포 직전 104 MB · 시간당 +15 MB) |

폴러가 매분 SAM2 를 올려 슬라이드 6개의 **첫 시야만** 검출하고 죽기를 반복했다
— GPU 도 이틀을 그렇게 썼다.

## 4. 한 것 — 순서대로

### 4.1 출혈을 멈춘다 (10:50)

crontab 은 안 건드리고 `/tmp/DiaRUGA-poll.lock` 을 잡았다. 락 파일이
`paleoadmin` 소유이고 `/tmp` 가 sticky 라 `flock <파일>` 은 `Permission
denied` 다(`fs.protected_regular`) — **읽기 전용 fd 로 열면 된다**:

```bash
setsid nohup bash -c 'exec 9</tmp/DiaRUGA-poll.lock; flock 9; exec sleep infinity' &
```

돌던 주기가 끝나는 순간(10:52) 이 프로세스가 락을 쥐고, 그 뒤 cron 의 폴러는
`flock -n` 에서 조용히 물러난다. 풀 때는 그 `sleep` 을 죽인다.

### 4.2 파이프라인 이미지 `v0.5.3`

`v0.26.0` 태그를 `git archive` 로 깨끗이 풀어 구웠다(작업 트리에는 옆 세션의
미커밋이 있었다). 의존성 판은 `v0.5.2` 와 같다 — cv2 5.0.0 · torch
2.13.0+cu126 · ultralytics 8.4.7 · Django 5.2.16. 다른 것은 `/app` 의 코드뿐이다
(마이그레이션 `0043` 까지).

**스크래치 DB 에 붙여 실제로 검출·저장을 지났다** — 114 가 놓친 바로 그 갈래.
`docker run` 으로 백업 사본과 스크래치 `out/`·`locks/` 만 물리고
`/data3/DiaRUGA` 는 읽기 전용으로:

```
260915_rs21-gc05_6cm: 검출 대상 8개
g000_Snap-29802-29805_focused: raw=382 크기통과=121 최종=26 (봉상 21, 원형 5)
검출 1개 · 개체 121개 · Run #4429                      ← done · is_current=1
```

Hub 로 밀고(`koprifossillab/diaruga-pipeline:v0.5.3`) `/srv/DiaRUGA/.env` 의
`PIPELINE_TAG` 를 올렸다.

### 4.3 찌꺼기를 지운다 — `migrate/prune_failed_runs.py`

`ops/prune_detections.py` 는 이 자리에 안 맞는다 — 이미지마다 **하나를 남기는**
규칙이라 실패가 남긴 것 중 가장 새것을 화면이 그릴 것으로 남긴다. 여기서는
실패한 실행이 남긴 것은 **전부** 찌꺼기다. 그래서 따로 짰다: `status='failed'`
이고 `error` 에 그 문자열이 든 실행과 그 검출(→ 후보는 CASCADE). 지우기 전에
셋을 확인하고 하나라도 걸리면 아무것도 안 지운다 — 현재 검출이 없다 · 그
후보에 붙은 교정이 없다 · 다른 검출이 `superseded_by` 로 안 가리킨다.
`Detection.run` 이 `SET_NULL` 이라 `Run` 만 지우면 검출은 남는다 — 검출을 먼저
짚는다.

백업 사본에서 세어 본 뒤 운영은 규약대로 `dbrun.sh` 로:

```
dbrun.sh backup_db.py --note before-prune-198        # manual/ · 635 MB · integrity=ok
dbrun.sh prune_failed_runs.py                        # 세어만
dbrun.sh prune_failed_runs.py --apply                # 실행 4,212 · 검출 4,212 · 후보 902,772
docker compose run --rm -T dbtool -c "…VACUUM…"      # 컨테이너 안에서 · 1.0초
```

635 MB → **82 MB**. `check_db.py` 전부 OK · `/healthz` ok · 검출 2,817 ·
후보 122,333(= 1,025,105 − 902,772).

### 4.4 다시 안 나게 — 둘

**(a) `pipeline/schema_guard.py` — 기계가 판을 대조한다.** 파이프라인 스크립트
셋(`segment_diatoms`·`focus_stack`·`group_focus_series`)이 `django.setup()`
직후, GPU 를 올리기 전·`Run` 행을 만들기 전에 부른다. 어긋나면 3 으로 끝내고
**`db_sentinel` 깃발을 세워 `/healthz` 를 `degraded` 로** 만든다(034 의 그
통로). 맞으면 자기 줄만 지운다.

무엇을 대조하느냐가 요점이다. **마이그레이션 번호가 아니라 칼럼이다** — 이미지
의 모델이 아는 칼럼·테이블(`_meta.db_table`·`local_concrete_fields`)이 DB 의
테이블 정의에 전부 있는가. 번호를 맞추면 뷰어가 칼럼 하나를 **더할** 때마다
7 GB 이미지를 다시 구워야 하는데, 더한 칼럼은 옛 모델이 모르니 SELECT 도 안
하고 INSERT 는 `db_default` 가 받는다(CLAUDE.md 가 그래서 `db_default` 를
요구한다). 위험한 것은 **옛 모델이 아는 칼럼이 걷힌 경우**뿐이고 이번이
그것이다. 옆 세션의 `0044`(197 · AddField 둘)는 그래서 `v0.5.3` 을 다시 굽지
않아도 된다 — 시험으로 박았다.

`v0.5.2` 이미지에 대고 실측: `DB 에 없는 칼럼 1개 (viewer_objectreview.note) ·
DB 에만 있는 마이그레이션 11개 (0033_objectreview_auto_confirmed ~
0043_taxonname) — 파이프라인 이미지가 낡았다. PIPELINE_TAG 를 올릴 것` 으로
멈추고 깃발이 선다(`grade` 는 `0034` 로 생긴 칸이라 `v0.5.2` 가 모른다 — 114 가
말한 대로 모르는 칼럼은 위험하지 않다).
`v0.5.3` 은 지나가고 깃발을 지운다.

스크립트로 돌 때만이다(`if __name__ == "__main__"`) — 시험이 임포트할 때는
시험 DB 가 아직 없어 테스트 수집에서 죽었다(실제로 그렇게 한 번).

**(b) `save_detection` — 둘째 트랜잭션이 죽으면 첫째가 남긴 것을 거둔다.**
`except BaseException: Detection.objects.filter(pk=det.pk).delete(); raise`.
후보는 CASCADE. 이것이 없으면 원인이 무엇이든 둘째에서 죽을 때마다 행이 남는다
— `with_db_retry` 의 잠금 재시도도 같은 길이다(다시 돌면 첫째를 또 지나므로
앞엣것이 지워져 있어야 한다). 둘째는 `_promote_and_rebind()` 로 떼어 통계를
돌려준다.

시험 둘. `test_schema_guard`(7) 는 호스트에서 돈다. `test_save_detection_cleanup`
(2) 은 `segment_diatoms` 가 cv2·torch 를 머리에서 임포트해 **파이프라인
이미지 안에서만** 돈다(호스트에서는 skip):

```bash
docker run --rm --user 1000:1000 -e DIARUGA_DB=/testdb/DiaRUGA.db -e DIARUGA_SECRET=x \
  -e DIARUGA_DATA_ROOT=/testdb/data -e DIARUGA_THUMB_CACHE=/testdb/thumb -e HOME=/tmp \
  -v $PWD:/repo:ro -v <스크래치>/testdb:/testdb -w /repo --entrypoint python \
  koprifossillab/diaruga-pipeline:v0.5.3 web/manage.py test viewer.tests.test_save_detection_cleanup
```

거두는 줄을 떼면 `(2, 4) != (1, 2)` 로 무너지는 것을 봤다. 브라우저 제외 921개
전부 OK.

### 4.5 락을 풀고 (14:48) — 6개가 처음부터 돈다

## 5. 남긴 것 · 안 한 것

- **폴러가 같은 슬라이드를 연속으로 N번 실패하면 멈추는 것**은 안 넣었다.
  (a) 가 스키마 어긋남을 GPU 전에 잡고 깃발을 세우며, (b) 가 다른 원인의 실패도
  행을 안 남기게 하므로, 실패가 매분 반복돼도 이제 **비용이 로그 몇 줄**이다.
  그래도 `/healthz` 에 "최근 실패 실행 수" 같은 것은 없다 — 다음 판단
- 114 의 실측 표는 그때의 기록이라 안 고친다. 대신 HANDOFF 5절의 *"다음에
  파이프라인 이미지를 구울 때 함께 올린다"* 를 지금 상태로 바꿨다
- `/srv/DiaRUGA/.env` 를 `sed -i` 로 고치면서 소유자가 `sclee` 로 바뀌었다
  (그룹 `paleoadmin` rw 는 그대로). `paleoadmin` 이 만지는 데 지장은 없다
- 옆 세션(197)의 `poll_nas.sh` 변경(그룹핑 직후 `fetch_kpdc.py`)은 아직 `/srv`
  에 안 갔다 — 그쪽 판이 나갈 때 `sync_to_srv.sh` 가 민다
