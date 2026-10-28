#!/usr/bin/env python3
"""실행 이력(`Run`)을 열고 닫는 규칙을 한 곳에 둔다.

**닫히지 않은 실행이 남는다.** 컨테이너가 OOM 이나 `docker kill` 로 죽으면
`finally` 가 돌지 않아 `status="running"` 인 채로 영원히 남는다. 실제로 두 건이
세 시간 동안 "돌고 있음" 으로 남아 있었다.

그러면 이력의 뜻이 흐려진다 — "지금 뭐가 돌고 있나" 와 "무엇으로 돌렸었나" 를
같은 테이블에서 물을 수 없게 된다.

**같은 종류는 한 번에 하나만 돈다**(GPU 잠금·flock 이 그것을 보장한다). 그래서
새 실행이 시작할 때 같은 종류의 옛 `running` 을 닫아도 안전하다. 죽은 것을
치우는 일을 살아 있는 것이 한다.
"""
import hashlib
import importlib.util
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from django.utils import timezone


def _main_script() -> Path | None:
    """지금 도는 스크립트 파일. `python -c`·`python -` 이면 없다."""
    f = getattr(sys.modules.get("__main__"), "__file__", None)
    return Path(f).resolve() if f else None


def git_commit(where: Path | None = None) -> str:
    """`where` 가 git 저장소 안이면 HEAD 의 짧은 커밋, 아니면 빈 문자열."""
    where = where or _main_script() or Path.cwd()
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5,
                             cwd=where if where.is_dir() else where.parent)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def blob_id(path: Path) -> str:
    """파일의 git blob id — `git hash-object` 와 같은 값.

    저장소에서 `git log --all --find-object=<id>` 로 어느 커밋의 파일인지 찾힌다.
    """
    body = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()


def image_tag() -> str:
    """지금 도는 이미지의 판. 컨테이너 밖이면 빈 문자열.

    **두 컨테이너가 같은 `.env` 를 받아 `IMAGE_TAG`·`PIPELINE_TAG` 가 둘 다 있다**
    (compose 의 `env_file`). 어느 쪽 이미지인지는 이미지에 적혀 있지 않아서
    `torch` 로 가른다 — 파이프라인 이미지에만 있다(`poll_nas.sh` 의 `rundb` 주석과
    같은 구분이다). 둘 다 없으면 호스트다.
    """
    if not (os.environ.get("IMAGE_TAG") or os.environ.get("PIPELINE_TAG")):
        return ""
    if importlib.util.find_spec("torch") is not None:
        return os.environ.get("PIPELINE_TAG", "")
    return os.environ.get("IMAGE_TAG", "")


def code_version(script: Path | None = None) -> str:
    """실행 이력에 적을 코드 판. 커밋을 알면 커밋, 모르면 `blob:<id>@<이미지 판>`.

    **컨테이너에는 git 이 없다** — `/srv/DiaRUGA/scripts` 는 저장소가 아니라
    `dbsync.sh`·`sync_to_srv.sh` 가 파일만 옮겨 놓은 자리다. 그래서 스크립트마다
    가진 `git_version()` 이 컨테이너에서 빈 값을 내고, 08-03 뒤로 컨테이너에서 돈
    실행이 전부 코드 판 없이 남았다(10-28 운영 DB · detect 147건 중 147건).

    blob 은 **도는 스크립트 하나**의 것이다 — 그것이 부르는 `judge.py` 같은 옆
    모듈은 안 담긴다. 이미지 판이 Django 쪽(`/app`)을 말한다. 64자 칸에 들어간다.
    """
    script = script or _main_script()
    v = git_commit(script)
    if v:
        return v
    if script is None or not script.is_file():
        return ""
    tag = image_tag()
    return f"blob:{blob_id(script)[:12]}" + (f"@{tag}" if tag else "")


def close_stale(kind: str, older_than_min: float = 5.0) -> int:
    """같은 종류의 오래된 `running` 을 `failed` 로 닫는다. 닫은 개수를 돌려준다.

    `older_than_min` 을 두는 이유: 방금 시작한 형제 실행을 닫지 않기 위해서다.
    같은 종류가 겹치지 않는다는 전제가 깨졌을 때 피해를 줄인다.
    """
    from viewer.models import Run                       # 순환 임포트를 피한다

    cut = timezone.now() - timedelta(minutes=older_than_min)
    stale = list(Run.objects.filter(kind=kind, status="running",
                                    started_at__lt=cut))
    for r in stale:
        r.status = "failed"
        r.error = (r.error or "") + (
            " · " if r.error else "") + "끝나지 않은 채 남아 있었다 (다음 실행이 닫음)"
        r.finished_at = timezone.now()
        r.save(update_fields=["status", "error", "finished_at"])
    return len(stale)


def batch(kind: str, label: str, note: str = ""):
    """이름으로 묶음을 찾거나 만든다. 같은 이름이면 같은 묶음이다.

    파이프라인은 슬라이드 단위로 돌기 때문에 "전체를 한 번 훑었다" 는 작업이
    실행 여럿으로 흩어진다. 명령을 슬라이드마다 나눠 부르더라도 같은 이름표를
    주면 한 덩어리로 남는다.
    """
    from viewer.models import RunBatch                  # noqa: PLC0415

    obj, made = RunBatch.objects.get_or_create(
        kind=kind, label=label, defaults={"note": note})
    if made:
        print(f"  묶음 '{label}' 을 새로 만들었다")
    return obj


def start(kind: str, batch_label: str = "", batch_note: str = "", **fields):
    """새 실행을 연다. 옛 것을 먼저 치운다.

    `batch_label` 을 주면 그 이름의 묶음에 매단다 — 여러 슬라이드에 걸친 한 번의
    작업을 나중에 한 덩어리로 보기 위해서다.

    **`code_version` 이 비었으면 여기서 채운다.** 부르는 쪽은 저마다의
    `git_version()` 을 넘기는데 컨테이너에서는 그것이 빈 값이다(`code_version()`).
    """
    from viewer.models import Run                       # noqa: PLC0415

    if not fields.get("code_version"):
        fields["code_version"] = code_version()
    n = close_stale(kind)
    if n:
        print(f"  끝나지 않은 {kind} 실행 {n}개를 닫았다")
    if batch_label:
        fields["batch"] = batch(kind, batch_label, batch_note)
    return Run.objects.create(kind=kind, status="running", **fields)
