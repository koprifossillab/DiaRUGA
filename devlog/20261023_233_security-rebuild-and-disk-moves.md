# 233 — 보안 때문에 뷰어 이미지를 다시 굽는다 (pip 26.1 · 베이스 갱신) · 서버 디스크가 바뀐 자리 · v0.35.2

2026-10-23 · `work/20261023-paleoadmin` · paleoadmin

기능 변경이 없는 판이다. 같은 날 서버에 일이 셋 겹쳐 함께 적는다 — ① 보안 점검,
② `/data` 디스크(sda) 고장과 `/data3` 디스크(sdc) 열화, ③ Ubuntu 26.04 로 올린 뒤 깨진
호스트 환경. 판으로 나가는 것은 ①뿐이고 ②·③은 이 저장소 밖에서 바뀐 것을 기록한다.

## 1. 보안 — 왜 다시 굽나

2026-10 에 pip·uv·PHP 의 취약점이 잇달아 나와 서버와 컨테이너를 점검했다. 이
저장소의 이미지에 걸리는 것은 **pip** 하나였다.

| 무엇 | 취약점 | 이 저장소 |
|---|---|---|
| pip | CVE-2026-6357 (설치 직후 자기 갱신 확인이 방금 깐 wheel 의 모듈을 임포트해 코드가 돈다) · CVE-2026-3219 (tar 이면서 zip 인 파일을 zip 으로 읽어 다른 파일이 깔린다) · CVE-2026-8643 (entry point 이름으로 scripts 디렉토리 밖에 쓴다) · CVE-2026-13346 (두 번 인코딩한 URL 로 인덱스가 임의 경로에 쓴다) · CVE-2026-1703 (wheel 을 설치 디렉토리 밖 형제 경로에 푼다). 대부분 **26.1 미만** | 뷰어·파이프라인 이미지 **25.0.1**. 걸린다 |
| uv | CVE-2026-114109 (0.11.15 에서 고침) · CVE-2026-114110 (0.11.6) | 이미지·CI 어디에도 uv 가 없다. 안 걸린다 |
| PHP | CVE-2026-109618 · 109619 ("PHP2Shell", 원격 코드 실행, 실제 공격 있음) | PHP 가 없다. 안 걸린다 |

pip 의 결함은 전부 **악성 패키지나 인덱스로 설치할 때** 일어난다. 컨테이너는
돌면서 pip 을 안 부르므로 운영 중인 이미지가 바로 위험한 것은 아니다 — 위험한
자리는 **이미지를 굽는 순간**이다. 그래도 고쳐 둔다: 굽는 자리가 CI 와 이 서버
둘이고, 고정하지 않은 간접 의존이 그때마다 새로 받힌다.

**pip 은 베이스 이미지를 새로 받아도 안 올라간다.** `python:3.12-slim` 의 pip 은
그 파이썬 판이 묶어 낸 것이라 지금 받아도 25.0.1 이다. 그래서 Dockerfile 에서
직접 올린다. 다시 굽는 김에 베이스(Debian 13 · 파이썬 3.12)의 보안 갱신도 들어온다.

### 무엇을

- `deploy/Dockerfile.base` — `pip install -r` 앞에 `pip install --upgrade "pip>=26.1"`
- `deploy/Dockerfile.pipeline` — 같은 줄
- 판은 PATCH 만 올린다: 뷰어 `v0.35.1` → **`v0.35.2`** (사용자 방침 · 기능 변경 없음). 같은 날 sclee 의 `v0.35.1`(231·232)이 먼저 나가 그 뒤에 붙였다

### 버린 것

- **파이프라인 이미지는 이번에 안 굽는다** (`PIPELINE_TAG=v0.5.3` 그대로). 지금
  `v0.5.3` 은 `v0.26.0` 코드로 구운 것이라, 지금 코드로 다시 구우면 pip 만이 아니라
  **파이프라인 코드가 아홉 판을 건너뛴다** — 보안 판이 할 일이 아니다. 파이프라인은
  돌면서 pip 을 안 부르므로 급하지 않다. Dockerfile 에는 줄이 들어갔으니 **다음에
  파이프라인 판을 올릴 때 저절로 실린다**
- pip 판을 `==` 로 박기 — 다음 보안판을 받으려면 또 고쳐야 한다. 하한만 둔다

## 2. 디스크 — 자리가 바뀐 것

**`/data` 디스크(sda, 8 TB)가 고장 났다.** SMART 재할당 7,912 · 읽기 불가 1,512,
파일시스템 비트맵 오류가 07-31 부터 3만 건 쌓여 있었다(fstab 의 점검 칸이 0 이라
부팅 때 한 번도 안 봤다). **`/data3` 디스크(sdc, 같은 모델)도 열화 중이다** — 재할당이
10-23 하루에 6,136 → 6,272 로 늘었고, 요청 한 건에 읽기 1초 · 쓰기 3초가 걸린다.
**두 디스크 다 바꿀 때까지의 임시 배치다.**

| 무엇 | 전 | 지금 (2026-10-23) |
|---|---|---|
| `/data` | sda | **`/data3/data-rescue` 를 bind mount** (sdc). sda 에만 있던 것(GSM·Cropobite·WegenersDream·ghrunner)을 옮겼다. `/data/data` 2.7 T 는 NAS 공유의 백업이라 NAS 원본이 있다 |
| Docker 데이터 루트 | `/data3/docker` (sdc) | **`/data2/docker`** (sdb SSD) · `daemon.json` 에 `containerd-snapshotter: false` 도 같이 — 빈 루트에서 Docker 29 가 이미지를 루트 nvme 의 containerd 저장소에 쌓기 때문이다. 옮길 때 overlay2 를 복사하지 못해(sdc 가 너무 느리다) **이미지를 Docker Hub 에서 같은 digest 로 다시 받았다** |
| `/data3`·`/data` 마운트 | `relatime` | `noatime` (지금 부팅에서만) — 읽기마다 접근 시각을 써서 느린 sdc 의 쓰기를 늘렸다 |
| NAS 의 03:00 백업 수신(rsync 데몬, `/data` 로 받음) | 켜짐 | **꺼짐** — 켜 두면 1.2 T 를 sdc 에 다시 쓴다. **NAS 는 지금 백업이 없다** |
| 옛 `/data3/docker` | — | 되돌릴 때를 위해 남겨 둠 |

**이 저장소가 쓰는 자리는 경로가 그대로다** — `/data3/DiaRUGA`(사진·`stacked/`·`out/`·
`backup/`·`models/`·`.thumbcache/`)와 `/srv/DiaRUGA/db`(운영 DB, nvme). 다만
`/data3/DiaRUGA` 는 **열화 중인 sdc 위에 있다.** 잃어도 되돌릴 수 있는 근거:
`photos/` 는 NAS 원본과 1:1 · `backup/` 의 사본과 `models/` 는 매일 NAS 동기화(04:40)가
NAS 로 보낸다 · `stacked/`·`out/`·캐시는 다시 돌리면 나온다 · 운영 DB 는 sdc 에 없다.

## 3. 호스트 — Ubuntu 26.04 로 올린 뒤 깨진 것

10-22 저녁에 서버를 Ubuntu 24.04 → 26.04 로 올렸다. 26.04 에는 파이썬 3.12 가 없어
**`~/venv/DiaRUGA` 가 깨졌고**, 그 venv 로 도는 cron 이 조용히 실패했다:

- **시간별 DB 백업(`:20`)이 10-22 20:20 부터 10-23 10:20 까지 15번 실패** — 그 사이의
  rolling 사본이 없다. 운영 DB 자체는 멀쩡했다
- NAS 동기화(04:40)도 10-23 에 실패
- **NAS 폴러가 10-22 19:55 부터 10-23 10:55 까지 멈췄다** — 파이프라인 컨테이너가
  `nvidia-container-cli: ldcache error: /sbin/ldconfig.real` 로 못 떴다(26.04 는
  `/sbin/ldconfig`). `/etc/nvidia-container-runtime/config.toml` 을 고쳤다. 그 사이
  NAS 에 올라온 슬라이드는 그 뒤 첫 폴러가 가져간다

`~/venv/DiaRUGA` 는 **uv 가 받은 파이썬 3.12.15**(`~/.local/share/uv/python/`)로 다시
만들고 깨지기 전과 같은 판의 패키지 60개를 다시 깔았다(torch `2.13.0+cu126` · CUDA 인식 ·
SAM-2 `2b90b9f`). 앞으로 Ubuntu 를 올려도 이 파이썬은 안 사라진다. 옛 venv 는
`~/venv/DiaRUGA.py312-bak` 에 남겼다. CLAUDE.md 의 `python --version` 줄도 3.12.15 로 고쳤다. uv 로 패키지를 받을 때는 사내망 TLS 때문에 `--system-certs` 가 필요하다.

## 확인

- 시험(호스트 venv · 3.12.15): `test viewer --exclude-tag browser` 1,076개 OK
- CI 가 구운 이미지 안에서 `pip --version` 이 26.1 이상인지 본다
