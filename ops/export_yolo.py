#!/usr/bin/env python3
"""사람의 검토를 YOLO 학습 자료로 내보낸다 (P04 1단계 · 4차는 P29).

    deploy/host/dbsync.sh export_yolo.py
    A=/data3/DiaRUGA/backup/manual/DiaRUGA_20261028_151451_yolo3-final-inspected.db
    deploy/host/dbrun.sh export_yolo.py --src-db $A --out /data3/DiaRUGA/datasets/yolo/v4 --seg --dry-run
    deploy/host/dbrun.sh export_yolo.py --src-db $A --out /data3/DiaRUGA/datasets/yolo/v4 --seg

## 4차부터 정답 사본에서 뽑는다 (P29 6절 2 · P31 5.1)

학습 자료와 재현율의 기준이 **같은 판**이어야 한다. 운영 DB 는 3차 완료 시야의
유형 바꾸기가 열려 있어(P31 5절 2) 사본과 언제든 갈라질 수 있다.

**`--src-db` 를 주면 이 스크립트가 복사본을 직접 뜬다.** Django 가 뜨기 전에 원본을
파일 바이트로만 읽어(sqlite 로 열지 않는다) 임시 디렉토리에 복사하고, 그 복사본에
붙였다가 끝나면 지운다. `MANIFEST.json` 에는 **원본의** 경로와 sha256 이 들어간다.

손으로 복사해 `DIARUGA_DB` 로 붙이던 길을 버린 이유 — Django 가 열면서
`journal_mode=WAL` 을 걸어 파일 머리(19·20번째 바이트)가 바뀐다. 그래서 `--dry-run`
을 돌린 복사본으로 이어서 내보내면 manifest 의 sha256 이 원본과 안 맞는다 — 그
순서가 가장 자연스러운데 실제로 그렇게 됐다(10-28 확인 중). 원본 사본을 직접
열지 않는 이유도 같다 — 연 순간 원본이 바뀐다.

`--src-db` 없이 돌면 `DIARUGA_DB` 가 가리키는 것을 연다. 운영 DB
(`/srv/DiaRUGA/db/`)면 멈춘다(`--live-db` 로만 연다).

**묶음은 `--batch`(기본 `yolo-3차`)로 못 박는다.** 검토 대상 묶음을 따르면 4차로
옮긴 뒤 다시 낼 때 다른 자료가 된다.

## 클래스 — 일곱 (P29 3절)

`--scheme p29`(기본)가 분류를 `round · round_frag · rod · rod_frag · chaetoceros ·
eucampia · other` 로 보낸다. **Eucampia 파편은 원형 파편으로**, 여섯에 안 드는 것
(원통상 · Corethron · 유형이 정말 빈 것)은 **버리지 않고 `other` 로** 보낸다 — 빼면
그 자리를 배경으로 배워 못 잡는다. `--scheme diatom` 은 1~3차와 같은 단일 클래스다.

유형은 검토 화면이 보이는 값 그대로다 — 사람이 지정한 값, 없으면 엔진값, 묶인
개체는 판들에 걸쳐 접은 값(`fold_object_cls`). **엔진값이라도 사람이 동의한 것은
사람 라벨로 친다**(P29 3절). 자세(`pose`)는 학습에 안 쓰고 `MANIFEST.json` 에 개체마다
적어 둔다 — 성적을 자세별로 가르려고(E 의 valve).

**검토완료 시야만 쓴다.** 검토하지 않은 시야를 넣으면 "SAM2 가 통과시킨 것 = 정답"
이 되어 SAM2 의 오검출까지 그대로 배운다. 사람이 본 것만이 자료다.

판정은 뷰어와 **같은 함수**를 쓴다 — `data.detection_for_viewpoint()`. 규칙을
여기 다시 쓰면(`passed and not removed …`) 언젠가 갈라지고, 갈라진 것은 눈에
띄지 않는다. 화면에 보이는 것이 곧 라벨이어야 한다.

## 타일링을 하지 않는다

원본이 2752×2208 이고 개체 중앙값이 169 px 다. `imgsz=1280` 이면 개체가 79 px,
작은 쪽 10% 도 40 px 라 충분하다. 타일로 자르면 경계에 걸친 개체(최대 1331 px)를
어떻게 셀지 새로 정해야 하고, 그 규칙이 새로 틀릴 수 있다. RTX 8000 은 48 GB 라
1280 을 감당하므로 치를 이유가 없는 대가다. 근거는 P04 §자료 실측.

## 음성은 따로 내보내지 않는다

사람이 지운 4,039건은 **라벨을 안 쓰는 것으로 충분하다.** YOLO 는 라벨이 없는
자리를 배경으로 배운다. SAM2 가 실제로 헷갈린 자리에 사람이 "아니다" 를 붙인
것이라 무작위 배경보다 값어치가 크고, 그것이 이미지 안에 그대로 들어간다.

개체가 하나도 없는 시야(29개)도 버리지 않는다 — 빈 라벨 파일로 낸다. YOLO 는
배경 이미지를 10% 안팎 섞으라고 권한다.

## 검증을 둘로 나눈다

- `val`       — 시야 20%, 슬라이드별 층화. 학습이 되고 있나
- `val_slide` — 슬라이드 한 장 통째로. 슬라이드를 외웠나

`val` 은 좋은데 `val_slide` 가 나쁘면 염색·조명·쇄설물 같은 슬라이드 고유의
특징을 외운 것이고, 새 슬라이드에는 안 듣는다는 뜻이다. 한 슬라이드가 자료의
56% 라 이 구분 없이는 알 수 없다.

시야는 슬라이드 위의 서로 다른 자리다 — 같은 개체가 양쪽에 들어가지는 않는다.

**빼는 슬라이드는 `260803_gc03-c1_816cm` 이다** (P29 5절). 1~3차는
`wap13-gc47_450cm` 이었는데 C 202 중 144 가 거기 있어, 그대로면 C 의 학습분이 58 로
준다. 816cm 는 C 0 · E 1 이고 네 형태가 다 조금씩 있다. **개체 20개 안팎이라 슬라이드
확인은 대략적인 경고로만 읽는다.**
"""
import argparse
import hashlib
import json
import os
import random
import atexit
import shutil
import socket
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import django


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def work_copy_of_src_db():
    """`--src-db` 를 받았으면 복사본을 뜨고 `DIARUGA_DB` 를 그리로 돌린다.

    **`django.setup()` 앞에서 해야 한다** — 설정이 `DIARUGA_DB` 를 읽는 때가 그때다.
    그래서 `main()` 의 파서와 따로 `--src-db` 하나만 먼저 읽는다.

    돌려주는 것은 `(원본 경로, 원본 sha256)` 이고, 안 받았으면 `None` 이다.
    복사한 뒤 복사본도 재서 원본과 맞춘다 — 복사하는 사이에 원본이 바뀌었으면
    어느 판에서 뽑았는지 말할 수 없다.
    """
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--src-db")
    a, _ = pre.parse_known_args()
    if not a.src_db:
        return None
    src = Path(a.src_db).resolve()
    if not src.is_file():
        sys.exit(f"--src-db 가 없다: {src}")
    if any(Path(f"{src}{s}").exists() for s in ("-wal", "-shm")):
        sys.exit(f"{src} 옆에 -wal/-shm 이 있다 — 누가 열었거나 열고 있다. "
                 f"완결된 백업 사본을 줄 것")
    work_dir = Path(tempfile.mkdtemp(prefix="export_yolo-"))
    atexit.register(shutil.rmtree, work_dir, True)
    work = work_dir / src.name
    shutil.copyfile(src, work)
    src_sha = sha256(src)
    if sha256(work) != src_sha:
        sys.exit(f"복사본이 원본과 다르다 — 복사하는 사이에 {src} 가 바뀌었다")
    os.environ["DIARUGA_DB"] = str(work)
    return src, src_sha


SRC_DB = work_copy_of_src_db()

# 이 스크립트는 저장소 밖(/srv/DiaRUGA/scripts)에 복사해 두고 컨테이너 안에서
# 돌릴 수도 있다. 그때 Django 코드가 어디 있는지는 DIARUGA_APP 이 알려 준다 —
# 이미지 안의 /app 이고, 뷰어 컨테이너가 쓰는 바로 그 코드다. 저장소에서 그냥
# 돌리면 예전처럼 자기 옆의 web/ 을 본다.
# **저장소에서는 한 단계 위가 뿌리다** (스크립트가 pipeline/·ops/·migrate/
# 안에 있다). `/srv/DiaRUGA/scripts` 처럼 저장소 밖에서 돌 때는 그 짐작이
# 안 맞으므로 `DIARUGA_APP` 이 알려 준다 — 컨테이너에서는 이미지 안의 /app 이다.
APP = Path(os.environ.get("DIARUGA_APP")
          or Path(__file__).resolve().parent.parent)
# **`APP` 은 Django 코드를 찾는 자리일 뿐이다** (100). `sys.path` 앞에 통째로
# 밀어 넣으면 **이미지 안의 옛 `judge.py`·`zen_meta.py` 가 자기 옆의 것을 가린다**
# — `/srv/DiaRUGA/scripts` 로 밀어 넣은 새 규칙이 안 먹는 채로 돌았다(실측).
# 그래서 **뒤에 붙인다**: 스크립트 자신의 디렉토리(파이썬이 `sys.path[0]` 에
# 놓는다)가 먼저이고, Django 는 그 뒤에서 찾힌다.
sys.path.insert(0, str(APP / "web"))
sys.path.append(str(APP))
# **`pipeline/` 의 모듈을 함께 쓴다.** 판정 규칙(`judge`)·촬영 XML(`zen_meta`)·
# 실행 기록(`runlog`)은 파이프라인과 이쪽이 같은 것을 봐야 한다 — 규칙이 둘이면
# 검출과 검사가 다른 말을 한다. `/srv/DiaRUGA/scripts` 는 평평해서 이 줄이 없어도
# 되지만, 저장소에서는 디렉토리가 갈려 있어 알려 줘야 한다.
sys.path.insert(0, str(APP / "pipeline"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diarugaweb.settings")
django.setup()

from django.conf import settings                                    # noqa: E402
from django.utils import timezone                                   # noqa: E402

import runlog                                                       # noqa: E402
from viewer import data as vdata                                    # noqa: E402
from viewer.models import RunBatch, Viewpoint                       # noqa: E402

SPLITS = ("train", "val", "val_slide")

# 운영 DB 의 자리. 컨테이너 안팎의 경로가 같다(CLAUDE.md).
LIVE_DB_DIR = Path("/srv/DiaRUGA/db")

# 분류 → 클래스. (클래스 이름 목록, 대응표, 대응표에 없는 것이 갈 클래스).
# 클래스 이름은 `ClassDef.key` 와 맞춰 둔다 — 4차 검출을 저장할 때 `judge.py` 가
# 이 이름을 그대로 `cls` 로 읽는다(P29 6절 4). `other` 만 화면에서 미분류다.
SCHEMES = {
    "p29": (["round", "round_frag", "rod", "rod_frag",
             "chaetoceros", "eucampia", "other"],
            {"round": "round", "round_frag": "round_frag",
             "eucampia_frag": "round_frag",
             "rod": "rod", "rod_frag": "rod_frag",
             "chaetoceros": "chaetoceros", "eucampia": "eucampia"},
            "other"),
    "diatom": (["diatom"], {}, "diatom"),
}


def git_version():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5,
                             cwd=Path(__file__).resolve().parent)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def code_version() -> str:
    """이 꾸러미를 만든 코드. 커밋을 알면 커밋, 모르면 이 파일의 git blob id.

    **컨테이너에는 git 이 없다** — 4차 첫 꾸러미가 그렇게 `?` 로 나갔다(10-28).
    blob id 는 `runlog.blob_id` 가 잰다(`git log --all --find-object=<id>` 로 찾힌다).

    라벨 규칙(`viewer.data`)은 이 파일이 아니라 이미지 안에 있다 — 그쪽은
    `MANIFEST.json` 의 `image_tag` 가 따로 말한다. 그래서 여기서는 `@<판>` 을 안 붙인다.
    """
    return git_version() or f"blob:{runlog.blob_id(Path(__file__).resolve())[:12]}"


# --- 라벨 만들기 ------------------------------------------------------------
def bbox_line(c: dict, w: int, h: int, cls: int) -> str | None:
    """YOLO 상자 한 줄: `cls cx cy bw bh` (전부 0~1 로 정규화).

    상자가 이미지 밖으로 조금 나가 있는 경우가 있어 잘라 준다. 자른 뒤 넓이가
    0 이면 라벨이 될 수 없다.
    """
    bx, by, bw0, bh0 = c["bbox_xywh"]
    x0 = max(0.0, float(bx))
    y0 = max(0.0, float(by))
    x1 = min(float(w), float(bx) + float(bw0))
    y1 = min(float(h), float(by) + float(bh0))
    bw, bh = x1 - x0, y1 - y0
    if bw <= 1 or bh <= 1:
        return None
    return (f"{cls} {(x0 + bw / 2) / w:.6f} {(y0 + bh / 2) / h:.6f} "
            f"{bw / w:.6f} {bh / h:.6f}")


def seg_line(c: dict, w: int, h: int, cls: int) -> str | None:
    """YOLO 분할 한 줄: `cls x1 y1 x2 y2 …` (정규화).

    폴리곤은 `[x,y,x,y,…]` 평면 목록이다. 점이 3개(값 6개) 미만이면 면이 아니다.
    """
    p = c.get("polygon") or []
    if len(p) < 6:
        return None
    out = [str(cls)]
    for i in range(0, len(p) - 1, 2):
        out.append(f"{min(max(float(p[i]), 0.0), w) / w:.6f}")
        out.append(f"{min(max(float(p[i + 1]), 0.0), h) / h:.6f}")
    return " ".join(out)


def viewpoint_rows(vp: Viewpoint, seg: bool, scheme: tuple,
                   batch_id: int) -> tuple:
    """시야 하나 → (이미지 절대경로, 라벨 줄 목록, 개체 목록, 버린 개수).

    판은 **대표 판 하나**다 — 합성본, 없으면 그 한 장(`representative_detection`).
    프레임은 4차에 안 든다(P29 4.1).

    유형을 화면과 같게 하려고 **그 묶음의 판을 전부 읽어 접은 뒤** 대표 판을 고른다.
    대표 판만 읽으면 묶인 개체 중 사람이 유형을 안 고른 것이 옆 판의 엔진값을 못
    받는다 — 손그림 판은 엔진 후보가 없어 유형이 빈다(P31 5.2 의 51개가 그 모양이다).

    라벨을 못 만든 개체는 조용히 넘기지 않고 세어서 돌려준다 — 자료가 조용히
    줄어드는 것이 가장 알아채기 어렵다.
    """
    dets = vdata.current_detections(vp, batch_id)
    rep = vdata.representative_detection(vp, dets)
    if rep is None:
        return None, [], [], 0
    views = [vdata._with_reviews(vp, d, batch_id) for d in dets]
    vdata.fold_object_cls(views)
    det = views[dets.index(rep)]

    names, table, fallback = scheme
    img = Path(settings.DATA_ROOT) / det["image"]
    w, h = det["size"]
    lines, objs, dropped = [], [], 0
    for c in det["candidates"]:
        src = c.get("cls") or ""
        dst = table.get(src, fallback)
        idx = names.index(dst)
        line = seg_line(c, w, h, idx) if seg else bbox_line(c, w, h, idx)
        if line is None:
            dropped += 1
            continue
        lines.append(line)
        objs.append({"line": len(lines) - 1, "key": vdata.cand_key(c),
                     "cls_src": src, "class": dst,
                     "pose": c.get("pose") or ""})
    return img, lines, objs, dropped


# --- 나누기 -----------------------------------------------------------------
def split_viewpoints(vps: list[Viewpoint], val_frac: float,
                     holdout: str | None, seed: int) -> dict:
    """시야를 train/val/val_slide 로 가른다.

    `val` 은 **슬라이드별로** 뽑는다. 통째로 무작위면 작은 슬라이드(개체 3개짜리
    한 장이 있다)가 val 에서 통째로 빠지거나 통째로 몰릴 수 있다.
    """
    rng = random.Random(seed)
    by_slide = defaultdict(list)
    out = {s: [] for s in SPLITS}
    for vp in vps:
        if holdout and vp.slide.slug == holdout:
            out["val_slide"].append(vp)
        else:
            by_slide[vp.slide.slug].append(vp)

    for slug in sorted(by_slide):
        group = sorted(by_slide[slug], key=lambda v: v.id)
        rng.shuffle(group)
        n_val = round(len(group) * val_frac)
        out["val"].extend(group[:n_val])
        out["train"].extend(group[n_val:])
    return out


def main():
    ap = argparse.ArgumentParser(description="검토를 YOLO 자료로 내보낸다")
    ap.add_argument("--out", required=True, help="자료 꾸러미를 만들 곳")
    ap.add_argument("--val-frac", type=float, default=0.2,
                    help="슬라이드마다 val 로 뺄 시야 비율 (기본 0.2)")
    ap.add_argument("--holdout-slide", default="260803_gc03-c1_816cm",
                    help="val_slide 로 통째로 뺄 슬라이드 slug (기본 "
                         "260803_gc03-c1_816cm — 왜 이것인지는 머리말). "
                         "'' 를 주면 val_slide 를 안 만든다")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--seg", action="store_true",
                    help="상자 대신 폴리곤을 낸다 (-seg 모델용)")
    ap.add_argument("--batch", default="yolo-3차",
                    help="이 묶음에서 검토를 마친 시야를 낸다 (기본 yolo-3차). "
                         "검토 대상 묶음을 따르지 않는다")
    ap.add_argument("--scheme", choices=sorted(SCHEMES), default="p29",
                    help="분류 → 클래스 대응 (기본 p29 — 일곱. diatom 은 단일)")
    ap.add_argument("--src-db",
                    help="이 DB 파일(정답 사본)의 복사본을 떠서 거기서 뽑는다. "
                         "원본은 sqlite 로 열지 않는다 (머리말)")
    ap.add_argument("--live-db", action="store_true",
                    help="운영 DB 에서 뽑는 것을 허락한다. 4차는 정답 사본에서 "
                         "뽑으므로 쓰지 않는다 (머리말)")
    ap.add_argument("--link", action="store_true",
                    help="이미지를 복사하지 않고 심볼릭 링크로 (다른 기계로 "
                         "옮길 것이면 쓰지 말 것 — 링크는 따라가지 않는다)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    scheme = SCHEMES[args.scheme]
    classes = scheme[0]
    holdout = args.holdout_slide or None
    out_dir = Path(args.out).resolve()

    # **어느 DB 에서 뽑는가** (P29 6절 2). `--src-db` 면 원본 쪽 값을 적는다 —
    # 복사본은 끝나면 지워지고, 연 순간 머리가 바뀌어 원본과 안 맞는다(머리말).
    if SRC_DB is not None:
        db_path, db_sha = SRC_DB
        print(f"DB {db_path} (복사본 {settings.DATABASES['default']['NAME']})")
    else:
        db_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        if db_path.parent == LIVE_DB_DIR and not args.live_db:
            sys.exit(f"운영 DB 를 가리키고 있다 ({db_path}). 4차 자료는 정답 사본에서 "
                     f"뽑는다 — --src-db <사본> 을 줄 것(머리말). "
                     f"운영에서 뽑을 것이면 --live-db")
        print(f"DB {db_path}")
        # 아무것도 쓰기 전에 잰다 — 실제로 내보낼 때는 아래 `runlog` 가 한 줄을 쓴다.
        db_sha = sha256(db_path)
    print(f"   sha256 {db_sha}")

    # **검토 완료는 묶음마다다** (073). 예전에는 시야마다 한 줄이라
    # `review__done` 하나로 끝났는데, 지금은 `(viewpoint, batch)` 가 열쇠다.
    #
    # **그 묶음에서 끝낸 시야**를 쓴다. 다른 묶음에서 끝낸 것을 섞으면
    # "이 묶음이 낸 검출을 사람이 봤다" 가 아니게 되고, 그러면 정답이 아니다.
    # 묶음은 이름으로 못 박는다 — 검토 대상 묶음을 따르면 대상을 옮긴 뒤에 같은
    # 명령이 다른 자료를 낸다(P29 6절 2).
    rb = RunBatch.objects.filter(label=args.batch).values_list("id", flat=True).first()
    if rb is None:
        sys.exit(f"묶음 '{args.batch}' 이 없다. 있는 것: "
                 f"{list(RunBatch.objects.values_list('label', flat=True))}")
    vps = list(Viewpoint.objects
               .filter(reviews__done=True, reviews__batch_id=rb)
               .select_related("slide", "slide__sample__locality__site")
               # prefetch 를 걸지 않는다 — 시야 수백 개의 후보를 한 질의로 물으면
               # SQLite 식 깊이 한도(1000)에 걸려 죽는다(228 과 같은 것). 한 번
               # 돌리고 마는 명령이라 시야마다 묻는 쪽이 낫다
               .order_by("slide__slug", "idx").distinct())
    print(f"검토완료 시야 {len(vps)}개 (묶음: {args.batch})")
    if not vps:
        sys.exit("검토완료 시야가 없다 — 내보낼 것이 없다")

    if holdout and not any(v.slide.slug == holdout for v in vps):
        sys.exit(f"--holdout-slide '{holdout}' 에 해당하는 검토완료 시야가 없다. "
                 f"있는 것: {sorted({v.slide.slug for v in vps})}")

    splits = split_viewpoints(vps, args.val_frac, holdout, args.seed)

    # 먼저 전부 모아 본다. 파일을 쓰기 전에 무엇이 나갈지 보여야 --dry-run 이
    # 뜻이 있다.
    plan = {s: [] for s in SPLITS}
    cls_count = {s: Counter() for s in SPLITS}
    src_map = Counter()
    dropped_total, missing = 0, []
    for split, group in splits.items():
        for vp in group:
            img, lines, objs, dropped = viewpoint_rows(vp, args.seg, scheme, rb)
            dropped_total += dropped
            if img is None:
                continue
            if not img.exists():
                missing.append(str(img))
                continue
            stem = f"{vp.slide.slug}_vp{vp.idx:03d}"
            plan[split].append((stem, img, lines, objs))
            cls_count[split].update(o["class"] for o in objs)
            src_map.update((o["cls_src"], o["class"]) for o in objs)

    print()
    print(f"{'분할':<11}{'시야':>6}{'개체':>8}{'빈 시야':>9}")
    for s in SPLITS:
        n_obj = sum(len(p[2]) for p in plan[s])
        n_empty = sum(1 for p in plan[s] if not p[2])
        print(f"{s:<11}{len(plan[s]):>6}{n_obj:>8}{n_empty:>9}")

    # 클래스마다 몇 개 나가는가 — 한 클래스가 val 이나 val_slide 에서 0 이면
    # 그 클래스의 성적은 잴 수 없다. 학습 전에 보여야 한다.
    print()
    print(f"{'클래스':<14}" + "".join(f"{s:>11}" for s in SPLITS))
    for c in classes:
        print(f"{c:<14}" + "".join(f"{cls_count[s][c]:>11}" for s in SPLITS))
    print("\n분류 → 클래스")
    for (src, dst), n in sorted(src_map.items(), key=lambda kv: (kv[0][1], -kv[1])):
        print(f"  {src or '(유형 없음)':<16} → {dst:<12} {n:>6}")
    if dropped_total:
        print(f"\n라벨을 못 만들어 버린 개체 {dropped_total}개 "
              f"(폴리곤/상자가 비었다)")
    if missing:
        print(f"\n이미지가 없는 시야 {len(missing)}개 — 건너뛴다")
        for m in missing[:5]:
            print(f"    {m}")

    if args.dry_run:
        print("\n--dry-run 이라 아무것도 쓰지 않았다")
        return

    if out_dir.exists():
        sys.exit(f"{out_dir} 가 이미 있다. 지우거나 다른 이름을 줄 것 — "
                 f"덮어쓰면 어느 판으로 학습했는지 알 수 없게 된다")

    code_ver = code_version()
    image_tag = runlog.image_tag()
    run = runlog.start("export", params={
        "out": str(out_dir), "seg": args.seg, "classes": classes,
        "batch": args.batch, "scheme": args.scheme,
        "val_frac": args.val_frac, "holdout_slide": holdout, "seed": args.seed,
        "db": str(db_path), "db_sha256": db_sha,
    }, host=socket.gethostname(), code_version=code_ver)

    try:
        manifest_vps = {s: [] for s in SPLITS}
        for split in SPLITS:
            if not plan[split]:
                continue
            (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
            (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
            for stem, img, lines, objs in plan[split]:
                dst = out_dir / "images" / split / f"{stem}{img.suffix}"
                if args.link:
                    dst.symlink_to(img)
                else:
                    shutil.copy2(img, dst)
                (out_dir / "labels" / split /
                 f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
                manifest_vps[split].append({"stem": stem,
                                            "source": str(img),
                                            "n_objects": len(lines),
                                            "objects": objs})

        # data.yaml 은 상대경로로 쓴다. 절대경로면 RTX 8000 으로 옮긴 뒤 안 맞는다.
        # 단 ultralytics 는 path 를 yaml 위치가 아니라 실행 디렉토리 기준으로
        # 푼다 — 학습은 꾸러미 디렉토리 안에서 실행해야 한다.
        val_line = "val: images/val\n"
        if plan["val_slide"]:
            # ultralytics 는 val 에 목록을 받지만, 두 검증을 따로 보고 싶으므로
            # val_slide 는 학습에 걸지 않고 나중에 `model.val(data=…)` 로 따로 잰다.
            val_line += "# val_slide 는 따로 잰다: images/val_slide\n"
        yaml = (f"# {timezone.now():%Y-%m-%d} · export_yolo.py · "
                f"{code_ver}"
                f"{' · 이미지 ' + image_tag if image_tag else ''}\n"
                f"path: .\n"
                f"train: images/train\n"
                f"{val_line}"
                f"names:\n" +
                "".join(f"  {i}: {c}\n" for i, c in enumerate(classes)))
        (out_dir / "data.yaml").write_text(yaml)

        # val_slide 만 겨냥한 두 번째 yaml — 같은 자료를 val 로 걸어 둔 것이다.
        if plan["val_slide"]:
            (out_dir / "data_val_slide.yaml").write_text(
                yaml.replace("val: images/val\n", "val: images/val_slide\n"))

        manifest = {
            "created_at": timezone.now().isoformat(),
            "code_version": code_ver,
            # 라벨을 만드는 판정 함수(`viewer.data`)가 사는 이미지. 호스트에서
            # 돌리면 비고, 그때는 `code_version` 의 커밋이 둘 다를 말한다.
            "image_tag": image_tag,
            "host": socket.gethostname(),
            "run_id": run.id,
            "args": vars(args),
            # `--src-db` 면 원본 파일의 값이다(복사본은 지워진다). 아니면 연 DB 를
            # 쓰기 전에 잰 값이다(그 DB 에는 그 뒤 실행 기록 한 줄이 더해졌다).
            "source_db": {"path": str(db_path), "sha256": db_sha,
                          "copied": SRC_DB is not None},
            "batch": args.batch,
            "scheme": args.scheme,
            "classes": classes,
            "class_map": {"table": scheme[1], "fallback": scheme[2]},
            "label_kind": "polygon" if args.seg else "bbox",
            "note": ("검토완료 시야만, 시야마다 대표 판 하나(합성본, 없으면 그 한 "
                     "장). 유형은 검토 화면과 같다(사람 지정 · 엔진값 · 묶인 판의 "
                     "접은 값). 사람이 지운 개체는 라벨 없이 배경으로 남는다. "
                     "viewpoints[].objects 의 line 이 라벨 파일의 줄 번호다."),
            "recall_caveat": ("정답은 사람이 그 묶음의 엔진 후보 위에서 만든 것에 "
                              "사람이 그린 개체를 더한 것이다. 사람이 끝까지 못 "
                              "찾은 개체는 정답에도 없다."),
            "counts": {s: {"viewpoints": len(plan[s]),
                           "objects": sum(len(p[2]) for p in plan[s]),
                           "empty": sum(1 for p in plan[s] if not p[2]),
                           "classes": dict(cls_count[s])} for s in SPLITS},
            "class_sources": [{"cls_src": s, "class": d, "n": n}
                              for (s, d), n in sorted(src_map.items())],
            "dropped_objects": dropped_total,
            "missing_images": missing,
            "viewpoints": manifest_vps,
        }
        (out_dir / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2))

        # 옮기다 깨진 것을 학습이 끝난 뒤에 알면 늦다.
        if not args.link:
            sums = {}
            for split in SPLITS:
                for p in sorted((out_dir / "images" / split).glob("*")) if (
                        out_dir / "images" / split).exists() else []:
                    sums[f"images/{split}/{p.name}"] = sha256(p)
            (out_dir / "SHA256SUMS").write_text(
                "".join(f"{v}  {k}\n" for k, v in sorted(sums.items())))

        run.status = "done"
        run.counts = manifest["counts"]
    except Exception as e:
        run.status, run.error = "failed", f"{type(e).__name__}: {e}"
        raise
    finally:
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at", "counts"])

    print(f"\n{out_dir} 에 썼다")
    print(f"  data.yaml · MANIFEST.json"
          f"{' · SHA256SUMS' if not args.link else ' (심볼릭 링크 — 옮기지 말 것)'}")
    if plan["val_slide"]:
        print(f"  val_slide 는 data_val_slide.yaml 로 따로 잰다 "
              f"(슬라이드 {holdout})")


if __name__ == "__main__":
    main()
