"""관찰을 합치고 가른다 — 시야를 **통째로** 다른 관찰로 옮긴다. (216)

`regroup.py` 가 한 관찰 안에서 시야를 다시 묶는 도구라면 이것은 그 한 층
위다. 같은 시료를 같은 조건으로 이틀에 나눠 찍으면 폴더가 둘이라 관찰이
둘로 생긴다(`260928_rs14-gc04_6cm` · `260930_rs14-gc04_6cm`). 뷰어는 그것을
따로 보이고, 카탈로그 번호는 두 관찰의 `g00` 이 같은 번호를 받는다
(`obs_no` 가 둘 다 0 이다).

## 교정이 안 사라진다

시야 가르기·합치기(044·215)는 시야를 **지우고 새로 만들어서** 그 아래가
`CASCADE` 로 딸려 갔다. 여기서는 시야를 안 지운다 — `Viewpoint.slide` 와
`Frame.slide` 를 바꿔 끼울 뿐이다. 검출·교정·완료 표시·개체가 전부 시야나
이미지에 붙어 있고(`Slide` 를 직접 무는 것은 `Run` 이력뿐이다), 합성본 파일
이름(`stacked/<tag>_focused.jpg`)과 프레임 경로(`Frame.path`)는 슬라이드와
상관없이 자기 경로를 들고 있어 **합성·검출을 다시 돌릴 필요도 없다.**

바뀌는 것은 **주소와 번호**다. 옮겨 간 시야는 `/d/<받는 쪽>/g/<n>/` 로 가고,
카탈로그 번호(`…-g03-…`)는 새 `idx` 와 새 관찰의 `obs_no` 를 따른다 —
번호는 저장되는 값이 아니라 그때그때 만드는 값이라 행이 깨지지는 않는다.

## 빈 행을 남긴다

합쳐진 쪽 관찰은 **지우지 않고 시야 없는 행으로 남긴다**(`merged_into`).
폴러(`scan_nas.py`)가 DB 에 `image_dir` 가 없는 폴더를 새것으로 보고 다시
반입하기 때문이다 — 그것도 **파이프라인 이미지 안의 옛 코드가** 그렇게 한다.
행이 남아 있으면 옛 코드든 새 코드든 그 폴더를 안다. 그 대가로 목록·집계를
내는 자리는 이 행을 걸러야 한다(`Slide.objects.live()`).

## 받는 쪽의 번호는 안 바꾼다

합칠 때 받는 관찰의 `idx`·`seq` 는 그대로 두고 들어오는 것을 **뒤에 붙인다.**
이미 검토한 쪽의 주소와 번호가 안 흔들린다. 그래서 화면은 촬영이 이른 쪽에서
늦은 쪽을 받으라고 권한다(순서까지 맞는다). 가를 때는 남는 쪽의 `idx` 를
0부터 다시 매긴다 — 뷰어가 시야를 `idx` 순으로 놓고 앞뒤를 오가므로 구멍을
두지 않는다(`regroup` 과 같은 규칙).
"""
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from .models import Frame, Run, Slide, Viewpoint
from .regroup import IDX_PARK


def _live_problem(slide, who: str) -> str | None:
    if slide.merged_into_id:
        return f"{who} {slide.slug} 은(는) 이미 {slide.merged_into.slug} 에 합쳐졌습니다"
    if slide.state != "done":
        return f"{who} {slide.slug} 은(는) 자동 처리가 끝나지 않았습니다 ({slide.state})"
    return None


def _vp_rows(vps) -> list[dict]:
    """확인 화면에 놓을 시야 줄 — 시야마다 무엇이 함께 가는지."""
    rows = []
    for vp in vps:
        frames = list(vp.frames.order_by("seq"))
        a = frames[0].acquired_at if frames else None
        rows.append({
            "idx": vp.idx, "tag": vp.tag, "n_frames": len(frames),
            "first": frames[0].name if frames else "",
            "acquired": a,
            "folder": (frames[0].path.rsplit("/", 1)[0] if frames else ""),
            "detections": vp.detections.count(),
            "object_reviews": vp.object_reviews.count(),
            "reviewed": vp.reviews.filter(done=True).exists(),
        })
    return rows


def _first_shot(slide):
    return (Frame.objects.filter(slide=slide).exclude(acquired_at=None)
            .order_by("acquired_at").values_list("acquired_at", flat=True)
            .first())


# --- 합치기 ---------------------------------------------------------------

def merge_candidates(slide) -> list[dict]:
    """합칠 수 있는 관찰 — **같은 시료**의 다른 관찰 중 살아 있는 것.

    시료가 다른 관찰은 후보에 안 놓는다. 깊이가 다른 두 시료를 한 관찰로
    합치면 그 개체들이 어느 깊이에서 왔는지가 사라진다.
    """
    if not slide.sample_id:
        return []
    out = []
    mine = _first_shot(slide)
    for sl in (slide.sample.slides.live().exclude(pk=slide.pk)
               .order_by("obs_no", "name")):
        first = _first_shot(sl)
        out.append({"slug": sl.slug, "name": sl.name, "obs_badge": sl.obs_badge,
                    "image_dir": sl.image_dir, "state": sl.state,
                    "n_viewpoints": sl.viewpoints.count(),
                    "first_shot": first,
                    # 받는 쪽이 먼저 찍혔으면 붙인 뒤에도 촬영 순서가 맞는다
                    "later": bool(mine and first and first >= mine)})
    return out


def _resolve_merge(slide, other_slug):
    errors = []
    other = (Slide.objects.filter(slug=other_slug)
             .select_related("merged_into").first())
    if other is None:
        return None, [f"그런 관찰이 없습니다: {other_slug!r}"]
    if other.pk == slide.pk:
        return None, ["자기 자신과는 합칠 수 없습니다"]
    for s, who in ((slide, "받는 관찰"), (other, "합칠 관찰")):
        p = _live_problem(s, who)
        if p:
            errors.append(p)
    if not (slide.sample_id and slide.sample_id == other.sample_id):
        errors.append("같은 시료의 관찰끼리만 합칠 수 있습니다 — "
                      "시료가 다르면 개체가 어느 깊이에서 왔는지가 사라집니다")
    if (slide.um_per_pixel_override or None) != (other.um_per_pixel_override or None):
        errors.append(f"사람이 적은 배율이 다릅니다 "
                      f"({slide.um_per_pixel_override} · {other.um_per_pixel_override}) "
                      f"— 같은 조건으로 찍은 관찰이 아닙니다")
    clash = sorted(set(Frame.objects.filter(slide=slide).values_list("name", flat=True))
                   & set(Frame.objects.filter(slide=other).values_list("name", flat=True)))
    if clash:
        errors.append(f"사진 이름이 겹칩니다 ({len(clash)}장 · {', '.join(clash[:5])}) "
                      f"— 한 관찰 안에서 사진 이름은 유일해야 합니다")
    return other, errors


def merge_preview(slide, other_slug) -> dict:
    other, errors = _resolve_merge(slide, other_slug)
    if errors:
        return {"ok": False, "errors": errors}
    base = (slide.viewpoints.aggregate(m=Max("idx"))["m"])
    base = 0 if base is None else base + 1
    vps = list(other.viewpoints.order_by("idx"))
    rows = _vp_rows(vps)
    for r in rows:
        r["new_idx"] = base + (r["idx"] - vps[0].idx if vps else 0)
    a, b = _first_shot(slide), _first_shot(other)
    return {
        "ok": True, "other": other,
        "keep_n": slide.viewpoints.count(), "rows": rows,
        "after": slide.viewpoints.count() + len(vps),
        "out_of_order": bool(a and b and b < a),
        "n_frames": other.frames.count(),
        "unassigned": other.frames.filter(viewpoint__isnull=True).count(),
        "detections": sum(r["detections"] for r in rows),
        "object_reviews": sum(r["object_reviews"] for r in rows),
        "absorbed": list(other.absorbed.values_list("slug", flat=True)),
    }


@transaction.atomic
def apply_merge(slide, other_slug, source: str = "") -> dict:
    """`other_slug` 관찰의 시야·사진을 전부 `slide` 로 옮긴다. 한 트랜잭션이다."""
    other, errors = _resolve_merge(slide, other_slug)
    if errors:
        raise ValueError(" · ".join(errors))

    m = slide.viewpoints.aggregate(m=Max("idx"))["m"]
    vp_base = 0 if m is None else m + 1
    lo_idx = other.viewpoints.order_by("idx").values_list("idx", flat=True).first() or 0
    m = slide.frames.aggregate(m=Max("seq"))["m"]
    seq_base = 0 if m is None else m + 1
    lo_seq = other.frames.order_by("seq").values_list("seq", flat=True).first() or 0
    n_vp = other.viewpoints.count()
    n_fr = other.frames.count()

    run = Run.objects.create(
        kind="group", status="running", slide=slide,
        params={"tool": "observations.apply_merge", "slide": slide.slug,
                "from": other.slug, "source": source})

    # 받는 쪽의 가장 큰 값보다 뒤로 밀어 붙이므로 유일 제약에 안 걸린다.
    # 시야 순서·사진 순서는 그대로 따라온다.
    Viewpoint.objects.filter(slide=other).update(
        slide=slide, idx=F("idx") - lo_idx + vp_base)
    Frame.objects.filter(slide=other).update(
        slide=slide, seq=F("seq") - lo_seq + seq_base)

    # 합쳐진 쪽이 이미 받아 둔 빈 행이 있으면 그것도 받는 쪽을 가리키게 한다 —
    # 사슬을 두면 어디로 갔는지 되짚는 데 여러 번 건너야 한다.
    Slide.objects.filter(merged_into=other).update(merged_into=slide)
    now = timezone.now()
    other.merged_into = slide
    other.state_note = f"{now:%Y-%m-%d} {slide.slug} 에 합쳤다 (시야 {n_vp} · 사진 {n_fr})"
    other.save(update_fields=["merged_into", "state_note", "updated_at"])

    run.status = "done"
    run.finished_at = now
    run.counts = {"viewpoints_moved": n_vp, "frames_moved": n_fr,
                  "first_idx": vp_base}
    run.save()
    return {"moved": n_vp, "frames": n_fr, "first_idx": vp_base, "run_id": run.pk}


# --- 가르기 ---------------------------------------------------------------

NEW = "new"


def split_targets(slide) -> list[dict]:
    """가른 시야를 보낼 곳 — 새 관찰, 또는 **이 관찰에 합쳐졌던 관찰.**

    뒤엣것이 합치기를 되돌리는 길이다. 합쳐진 빈 행은 폴더·이름표·소속을 그대로
    들고 있으므로 거기로 돌려보내면 합치기 전과 같아진다.
    """
    out = [{"value": NEW, "label": "새 관찰로 뗀다"}]
    for sl in slide.absorbed.order_by("obs_no", "slug"):
        out.append({"value": sl.slug,
                    "label": f"{sl.slug} 로 되돌린다 ({sl.image_dir})"})
    return out


def split_rows(slide) -> list[dict]:
    """가르기 칸에 놓을 시야 줄 — 번호·사진 수·첫 촬영 시각·폴더.

    폴더를 함께 적는 것은 합쳐진 관찰을 되돌릴 때 어느 시야가 어느 폴더에서
    왔는지를 사람이 보고 고르게 하려는 것이다. 질의는 사진 한 번이다.
    """
    by_vp: dict[int, list] = {}
    for vid, path, at in (Frame.objects.filter(slide=slide, viewpoint__isnull=False)
                          .order_by("seq")
                          .values_list("viewpoint_id", "path", "acquired_at")):
        by_vp.setdefault(vid, []).append((path, at))
    rows = []
    for vp in slide.viewpoints.order_by("idx"):
        fs = by_vp.get(vp.pk, [])
        rows.append({"idx": vp.idx, "tag": vp.tag, "n_frames": len(fs),
                     "acquired": fs[0][1] if fs else None,
                     "folder": fs[0][0].rsplit("/", 1)[0] if fs else ""})
    # 폴더가 하나뿐이면 칸을 안 그린다 — 모든 줄에 같은 글자가 놓일 뿐이다
    if len({r["folder"] for r in rows}) <= 1:
        for r in rows:
            r["folder"] = ""
    return rows


def _resolve_split(slide, idxs, target):
    errors = []
    p = _live_problem(slide, "이 관찰")
    if p:
        errors.append(p)
    try:
        want = sorted({int(i) for i in idxs})
    except (TypeError, ValueError):
        return [], None, ["시야 번호가 숫자가 아닙니다"]
    if not want:
        errors.append("옮길 시야를 하나 이상 고르세요")
    vps = list(slide.viewpoints.filter(idx__in=want).order_by("idx"))
    missing = sorted(set(want) - {vp.idx for vp in vps})
    if missing:
        errors.append(f"이 관찰에 없는 시야입니다: {missing}")
    if want and len(vps) == slide.viewpoints.count():
        errors.append("시야를 전부 옮길 수는 없습니다 — 그것은 다른 관찰에 "
                      "합치는 일입니다(받을 관찰에서 합치기를 쓰세요)")
    dest = None
    if target != NEW:
        dest = slide.absorbed.filter(slug=target).first()
        if dest is None:
            errors.append(f"되돌릴 곳이 이 관찰에 합쳐졌던 관찰이 아닙니다: {target!r}")
        elif dest.viewpoints.exists() or dest.frames.exists():
            errors.append(f"{dest.slug} 에 시야나 사진이 남아 있습니다 — 빈 행이 아닙니다")
    if not slide.sample_id:
        errors.append("시료가 붙지 않은 관찰은 가를 수 없습니다 — 새 관찰을 어느 "
                      "시료에 둘지 알 수 없습니다")
    return vps, dest, errors


def _new_obs_no(slide) -> int:
    # 빈 행까지 센다 — 되돌릴 때 번호가 부딪히지 않게
    m = slide.sample.slides.aggregate(m=Max("obs_no"))["m"]
    return (m or 0) + 1


def split_preview(slide, idxs, target) -> dict:
    vps, dest, errors = _resolve_split(slide, idxs, target)
    if errors:
        return {"ok": False, "errors": errors}
    rows = _vp_rows(vps)
    if dest is None:
        no = _new_obs_no(slide)
        dest_label = f"새 관찰 {slide.base_name} ({no}) · 관찰 #{no}"
    else:
        dest_label = f"{dest.slug} ({dest.image_dir})"
    total = slide.viewpoints.count()
    return {
        "ok": True, "rows": rows, "dest_label": dest_label, "revive": dest is not None,
        "before": total, "after": total - len(vps),
        "detections": sum(r["detections"] for r in rows),
        "object_reviews": sum(r["object_reviews"] for r in rows),
        # 남는 시야 중 번호가 바뀌는 것 — 옮긴 것보다 뒤에 있던 것들이다
        "renumbered": slide.viewpoints.filter(idx__gt=vps[0].idx)
        .exclude(pk__in=[v.pk for v in vps]).count(),
    }


def _unique_slug(base: str) -> str:
    slug, n = base, 2
    while Slide.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@transaction.atomic
def apply_split(slide, idxs, target, source: str = "") -> dict:
    """고른 시야를 새 관찰(또는 합쳐졌던 관찰)로 옮긴다. 한 트랜잭션이다."""
    vps, dest, errors = _resolve_split(slide, idxs, target)
    if errors:
        raise ValueError(" · ".join(errors))

    frames = Frame.objects.filter(viewpoint__in=vps)
    if dest is None:
        no = _new_obs_no(slide)
        # 폴더는 옮긴 사진이 있던 곳이다. 한 폴더면 그것, 섞였으면 원래 관찰의 것.
        dirs = {p.rsplit("/", 1)[0] for p in frames.values_list("path", flat=True)}
        image_dir = dirs.pop() if len(dirs) == 1 else slide.image_dir
        dest = Slide.objects.create(
            name=f"{slide.base_name} ({no})"[:200],
            slug=_unique_slug(f"{slide.slug}-o{no}"[:110]),
            image_dir=image_dir, sample=slide.sample, obs_no=no,
            um_per_pixel_override=slide.um_per_pixel_override,
            corr_thresh=slide.corr_thresh, state="done",
            state_note=f"{timezone.now():%Y-%m-%d} {slide.slug} 에서 갈라 왔다",
            processed_at=timezone.now())
        made = True
    else:
        made = False

    run = Run.objects.create(
        kind="group", status="running", slide=slide,
        params={"tool": "observations.apply_split", "slide": slide.slug,
                "to": dest.slug, "idx": [vp.idx for vp in vps],
                "source": source})

    moved = [vp.pk for vp in vps]
    n_fr = frames.count()
    # 받는 쪽은 비어 있다 — 0부터 바로 매긴다
    for i, vp in enumerate(vps):
        vp.slide, vp.idx = dest, i
        vp.save(update_fields=["slide", "idx"])
    Frame.objects.filter(viewpoint_id__in=moved).update(slide=dest)

    # 남는 쪽은 구멍을 메운다. 유일 제약을 피해 전부 치워 두고 다시 매긴다
    Viewpoint.objects.filter(slide=slide).update(idx=F("idx") + IDX_PARK)
    for i, vp in enumerate(slide.viewpoints.order_by("idx")):
        vp.idx = i
        vp.save(update_fields=["idx"])

    if not made:
        dest.merged_into = None
        dest.state_note = f"{timezone.now():%Y-%m-%d} {slide.slug} 에서 되돌려 왔다"
        dest.save(update_fields=["merged_into", "state_note", "updated_at"])

    run.status = "done"
    run.finished_at = timezone.now()
    run.counts = {"viewpoints_moved": len(moved), "frames_moved": n_fr,
                  "created": made}
    run.save()
    return {"to": dest.slug, "moved": len(moved), "frames": n_fr, "created": made,
            "run_id": run.pk}
