"""시야를 프레임 경계에서 다시 가르고, 이웃한 시야를 합치고, 시야를 지운다.

**그룹핑이 틀렸을 때 고치는 길은 여기 하나다** — 화면(`/d/<slug>/g/<n>/`)도
CLI(`resplit.py`)도 이 모듈을 부른다. 두 벌로 두면 한쪽만 고쳐지고, 그 종류의
어긋남은 사람이 화면을 눌러 보기 전까지 안 드러난다.

## 왜 부분 재분할인가

지금까지 있던 길은 `group_focus_series.py --force` 뿐이었는데 그것은 **슬라이드
전체를 다시 묶는다** — `slide.viewpoints.all().delete()` 한 줄에 그 슬라이드의
검출·교정이 통째로 딸려 간다. `am22-gc10b_25cm` 은 시야 26개 중 **4개**가
틀렸는데 `--force` 를 주면 26개가 다 날아가고 교정 100건이 사라진다. 4개를
고치려고 22개를 버리는 꼴이다.

여기서는 **가르는 시야만 지운다.** 나머지는 애초에 건드리지 않으므로 그 아래
검출·교정은 지킬 필요조차 없다 — 그대로 남아 있다.

## 지워지는 것은 진짜로 지워진다

`ObjectReview`·`ViewpointReview`·`Detection`·`Stack` 이 전부 `Viewpoint` 를
`CASCADE` 로 문다. 오래도록 `--force` 안내문이 "교정은 mask_key 로 남지만 고아가
된다" 고 적혀 있었는데 **거짓이었다** — `mask_key` 는 칼럼 값일 뿐이고 행이 없으면
아무것도 아니다.

그래서 이 도구의 값은 교정을 지키는 데 있지 않고 **다시 볼 것을 몇 개로 줄이는
데** 있다. 가른 시야는 사람이 다시 검토해야 한다. 부르는 쪽은 `preview()` 로
무엇이 사라지는지 **먼저 보여 주고** 확인을 받아야 한다.

## 밟을 곳 셋

- **`tag` 는 합성본 파일 이름을 낳는다** (`focus_stack.py` 가 `<tag>_focused.jpg`
  로 쓰고 `find_viewpoint()` 가 그것을 되읽는다). 그래서 **살아남는 시야의 `tag`
  는 건드리지 않는다.** 딸려 오는 것: `tag` 의 `g###` 접두가 `idx` 와 어긋날 수
  있다. 접두는 **만들어질 때의 번호**이고 신원은 `tag` 문자열 자체다 — 맞추려고
  이름을 바꾸면 디스크의 파일과 갈라진다
- **`idx` 는 다시 매긴다.** `(slide, idx)` 가 유일 제약이라 중간에 끼워 넣을 수
  없고, 무엇보다 뷰어가 이 순서로 시야를 늘어놓는다. 갈라진 조각을 목록 끝으로
  보내면 촬영 순서가 깨져 검토가 어려워진다. 충돌을 피해 **전부 큰 값으로 옮긴 뒤
  0부터 다시** 매긴다
- **하류는 손댈 것이 없다.** `focus_stack` 은 `Stack` 이 없는 시야만, `segment_
  diatoms` 는 `is_current` 검출이 없는 시야만 처리한다. 새로 생긴 시야가 정확히
  그것이다. 슬라이드를 `processing` 으로 돌려놓으면 **폴러가 1분 안에 이어서 하고**
  `mark_done_if_complete()` 가 `done` 으로 연다. 폴러는 `pending` 일 때만 다시
  묶으므로 방금 한 분할을 되돌리지 않는다
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .images import ensure_frame_image
from .models import Frame, Run, Viewpoint

# idx 를 다시 매기는 동안 유일 제약에 걸리지 않도록 잠깐 치워 두는 자리.
# 슬라이드 하나의 시야 수보다 훨씬 크면 된다 (가장 큰 슬라이드가 86개다).
IDX_PARK = 100000


# 앞 사진과 이만큼 넘게 떨어져 찍혔으면 화면에서 눈에 띄게 한다. 한 초점
# 시리즈 안은 2~5초 간격이고, 스테이지를 옮기면 분 단위로 벌어진다(260928
# RS14-GC04 6cm 실측 — 16:11:47 → 16:37:31).
GAP_WARN_SEC = 60


def gap_label(sec):
    """간격을 사람이 읽는 말로. 모르면 빈 문자열."""
    if sec is None:
        return ""
    sec = round(sec)
    if sec < 60:
        return f"{sec}초"
    if sec < 3600:
        return f"{sec // 60}분 {sec % 60}초" if sec % 60 else f"{sec // 60}분"
    return f"{sec // 3600}시간 {sec % 3600 // 60}분"


def frame_rows(frames) -> list[dict]:
    """가르기·합치기 화면이 그리는 프레임 줄 — 앞 사진과의 촬영 간격을 얹는다.

    시야를 잘못 묶는 것은 거의 늘 **스테이지를 옮긴 자리**이고, 그 자리는 촬영
    간격이 벌어진다. 번호만 늘어놓으면 사람이 캐러셀과 대조해야 하지만, 간격을
    보이면 어디를 볼지가 먼저 보인다.
    """
    rows, prev = [], None
    for f in frames:
        at = f.acquired_at
        gap = ((at - prev).total_seconds()
               if at is not None and prev is not None else None)
        rows.append({"name": f.name, "short": f.name.replace("Snap-", ""),
                     "prev_name": rows[-1]["name"] if rows else None,
                     "rel": f.path, "at": at, "is_sharpest": f.is_sharpest,
                     "gap": gap, "gap_label": gap_label(gap),
                     "gap_warn": gap is not None and gap > GAP_WARN_SEC})
        prev = at if at is not None else prev
    return rows


def resolve_cuts(slide, specs):
    """자를 자리를 프레임으로 푼다. → (`{viewpoint_id: {프레임 이름}}`, 문제 목록)

    **하나라도 이상하면 부르는 쪽이 아무것도 하지 않아야 한다.** 절반만 갈라진
    슬라이드가 남으면 무엇이 옳은 상태인지 알 수 없게 된다.

    이름(`Snap-22131`)도 번호(`22131`)도 받는다. **슬라이드를 반드시 함께 건다** —
    프레임 이름은 카메라 일련번호라 슬라이드 사이에서 겹친다 (devlog 031).
    """
    cuts, bad = {}, []
    for spec in specs:
        spec = str(spec).strip()
        if not spec:
            continue
        fr = Frame.objects.filter(slide=slide, name=spec).first()
        if fr is None and spec.isdigit():
            fr = Frame.objects.filter(slide=slide, name=f"Snap-{spec}").first()
        if fr is None:
            bad.append(f"{spec}: 그런 프레임이 없다")
            continue
        if fr.viewpoint_id is None:
            bad.append(f"{fr.name}: 시야에 안 붙어 있다")
            continue
        tail = fr.viewpoint.frames.order_by("seq").last()
        if tail and tail.pk == fr.pk:
            bad.append(f"{fr.name}: 이미 시야 g{fr.viewpoint.idx} 의 마지막 "
                       f"프레임이다 — 여기서 가를 것이 없다")
            continue
        cuts.setdefault(fr.viewpoint_id, set()).add(fr.name)
    return cuts, bad


def build_plan(slide, cuts):
    """슬라이드의 최종 배열. → `[("keep"|"new", 원래 시야, 프레임들), ...]`

    안 건드리는 시야도 그대로 실어 나른다 — `idx` 를 다시 매기려면 전체 순서가
    한자리에 있어야 한다.
    """
    plan = []
    for vp in slide.viewpoints.order_by("idx"):
        frames = list(vp.frames.order_by("seq"))
        here = cuts.get(vp.pk)
        if not here:
            plan.append(("keep", vp, frames))
            continue
        runs, cur = [], []
        for f in frames:
            cur.append(f)
            if f.name in here:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        for piece in runs:
            plan.append(("new", vp, piece))
    return plan


def preview(slide, specs) -> dict:
    """무엇이 사라지고 무엇이 생기는지. **DB 를 건드리지 않는다.**

    화면은 이것을 확인 페이지로 그리고, CLI 는 이것을 찍는다. 확인을 거치지 않고
    `apply()` 로 바로 가는 길은 두지 않는다 — 검토가 끝난 시야를 지우는 일이다.
    """
    cuts, bad = resolve_cuts(slide, specs)
    if bad:
        return {"ok": False, "errors": bad, "splits": [], "totals": {}}
    if not cuts:
        return {"ok": False, "errors": ["자를 자리를 하나도 고르지 않았다"],
                "splits": [], "totals": {}}

    plan = build_plan(slide, cuts)
    before = slide.viewpoints.count()
    splits, tot_det, tot_rev = [], 0, 0
    for vp in slide.viewpoints.order_by("idx"):
        if vp.pk not in cuts:
            continue
        n_det = vp.detections.count()
        n_rev = vp.object_reviews.count()
        tot_det += n_det
        tot_rev += n_rev
        splits.append({
            "idx": vp.idx, "tag": vp.tag,
            "detections": n_det, "object_reviews": n_rev,
            # 완료는 묶음마다다(073) — 여기서는 **어느 묶음에서든** 본 적이
            # 있는가를 알리면 된다. 가르면 사람이 잃는 것을 덜 세게 된다.
            "reviewed": vp.reviews.filter(done=True).exists(),
            "stack": hasattr(vp, "stack"),
            "pieces": [[f.name for f in p]
                       for k, o, p in plan if k == "new" and o.pk == vp.pk],
            # 화면이 조각마다 썸네일을 그린다 — 번호만으로는 잘못 고른 것을
            # 확인 화면에서도 못 잡는다(2026-09-29 에 그렇게 잘못 갈랐다)
            "piece_rows": [frame_rows(p)
                           for k, o, p in plan if k == "new" and o.pk == vp.pk],
        })
    created = sum(1 for k, _, _ in plan if k == "new")
    return {
        "ok": True, "errors": [],
        "before": before, "after": len(plan),
        "splits": splits, "untouched": before - len(cuts),
        "totals": {"split": len(cuts), "created": created,
                   "detections": tot_det, "object_reviews": tot_rev},
    }


@transaction.atomic
def apply_split(slide, specs, source: str = "") -> dict:
    """실제로 가른다. 한 트랜잭션이다.

    중간에 끊기면 시야 절반만 있는 슬라이드가 남고, 그 위에 검출을 돌리면 나머지
    절반이 조용히 빠진다 — `group_focus_series.save_grouping()` 이 통째로 한
    트랜잭션인 이유와 같다.
    """
    cuts, bad = resolve_cuts(slide, specs)
    if bad:
        raise ValueError(" · ".join(bad))
    if not cuts:
        raise ValueError("자를 자리를 하나도 고르지 않았다")

    plan = build_plan(slide, cuts)
    before = slide.viewpoints.count()
    doomed = [vp for vp in slide.viewpoints.order_by("idx") if vp.pk in cuts]
    lost_det = sum(vp.detections.count() for vp in doomed)
    lost_rev = sum(vp.object_reviews.count() for vp in doomed)
    created = sum(1 for k, _, _ in plan if k == "new")

    run = Run.objects.create(
        kind="group",           # 재분할도 그룹핑이다. 새 종류를 만들면 RUN_KIND
        status="running",       # 마이그레이션이 딸려 온다
        slide=slide,
        params={"tool": "regroup.apply_split", "slide": slide.slug,
                "after": sorted(n for s in cuts.values() for n in s),
                "source": source})

    _rebuild(slide, plan, doomed, run)

    # 검출이 없는 시야가 생겼다. `done` 인 채로 두면 뷰어가 빈 화면을 검토하라고
    # 내준다 — 자동 처리가 끝나기 전에는 막아야 한다 (P01 §1).
    slide.state = "processing"
    slide.state_note = f"시야 재분할 — 합성·검출 대기 {created}개"
    slide.save(update_fields=["state", "state_note"])

    run.status = "done"
    run.finished_at = timezone.now()
    run.counts = {"viewpoints_before": before, "viewpoints_after": len(plan),
                  "split": len(doomed), "created": created,
                  "detections_lost": lost_det, "object_reviews_lost": lost_rev}
    run.save()

    return {"before": before, "after": len(plan), "split": len(doomed),
            "created": created, "detections_lost": lost_det,
            "object_reviews_lost": lost_rev, "run_id": run.pk,
            # 가른 첫 조각으로 돌려보낸다 — 사람이 방금 한 일을 눈으로 확인한다
            "first_idx": next(i for i, (k, _, _) in enumerate(plan)
                              if k == "new")}


def resolve_merge(slide, idxs):
    """합칠 시야를 푼다. → (`[Viewpoint, ...]` idx 순, 문제 목록)

    **이웃한 시야만 합친다.** 뷰어가 시야를 촬영 순서로 늘어놓으므로, 사이에 다른
    시야를 두고 합치면 그 순서가 깨진다 — 가르기가 조각을 제자리에 끼워 넣는 것과
    같은 이유다. 떨어진 둘을 합칠 일이 생기면 사이의 것부터 합친다.
    """
    bad, want = [], set()
    for raw in idxs:
        try:
            want.add(int(str(raw).strip()))
        except ValueError:
            bad.append(f"{raw}: 시야 번호가 아니다")
    if bad:
        return [], bad
    vps = list(slide.viewpoints.filter(idx__in=want).order_by("idx"))
    missing = sorted(want - {vp.idx for vp in vps})
    if missing:
        bad.append("그런 시야가 없다: " + ", ".join(f"g{i}" for i in missing))
    elif len(vps) < 2:
        bad.append("합칠 시야를 둘 이상 골라야 한다")
    elif vps[-1].idx - vps[0].idx != len(vps) - 1:
        bad.append("이웃한 시야만 합칠 수 있다 — "
                   + ", ".join(f"g{vp.idx}" for vp in vps))
    return vps, bad


def build_merge_plan(slide, vps):
    """합친 뒤의 최종 배열. 모양은 `build_plan` 과 같다 — `_rebuild` 가 받는다."""
    ids = {vp.pk for vp in vps}
    plan, merged = [], []
    for vp in slide.viewpoints.order_by("idx"):
        if vp.pk not in ids:
            plan.append(("keep", vp, list(vp.frames.order_by("seq"))))
            continue
        merged.extend(vp.frames.order_by("seq"))
        if vp.pk == vps[-1].pk:
            # 시야 순서대로 이어 붙인다 — 시야가 이미 촬영 순서로 놓여 있다
            plan.append(("new", vps[0], merged))
    return plan


def merge_preview(slide, idxs) -> dict:
    """무엇이 사라지고 무엇이 생기는지. **DB 를 건드리지 않는다.** (`preview` 의 짝)"""
    vps, bad = resolve_merge(slide, idxs)
    if bad:
        return {"ok": False, "errors": bad, "merged": [], "totals": {}}
    plan = build_merge_plan(slide, vps)
    before = slide.viewpoints.count()
    merged = [{"idx": vp.idx, "tag": vp.tag,
               "detections": vp.detections.count(),
               "object_reviews": vp.object_reviews.count(),
               "reviewed": vp.reviews.filter(done=True).exists(),
               "frames": list(vp.frames.order_by("seq"))} for vp in vps]
    frames = next(fr for k, _, fr in plan if k == "new")
    starts = {m["frames"][0].name for m in merged[1:] if m["frames"]}
    for m in merged:
        m["rows"] = frame_rows(m.pop("frames"))
    rows = frame_rows(frames)
    # ★ 는 합친 뒤에 고를 한 장이다 — 옛 시야 둘의 것을 그대로 두면 둘이 뜬다.
    # 고르는 규칙은 `_rebuild` 와 같다
    best = max(frames, key=lambda f: f.sharpness or 0.0).name
    for r in rows:
        r["is_sharpest"] = r["name"] == best
    # 옛 시야의 경계 — 합친 줄 위에 "여기가 붙는 자리" 를 표시한다
    for r in rows:
        r["joint"] = r["name"] in starts
    return {
        "ok": True, "errors": [],
        "before": before, "after": len(plan),
        "merged": merged, "rows": rows,
        "untouched": before - len(vps),
        "totals": {"merged": len(vps), "frames": len(frames),
                   "detections": sum(m["detections"] for m in merged),
                   "object_reviews": sum(m["object_reviews"] for m in merged)},
    }


@transaction.atomic
def apply_merge(slide, idxs, source: str = "") -> dict:
    """이웃한 시야를 하나로 합친다. 한 트랜잭션이다. (`apply_split` 의 짝)

    합친 시야는 **새로 만든다** — 옛 시야들의 합성본·검출·교정은 가르기 때와
    같이 사라진다. 합성본은 묶음에서 나온 그림이라 묶음이 바뀌면 무효이고,
    시야 가르기·합치기는 검토를 시작하기 전에 하는 일이라(2026-09-29 사용자)
    교정을 옮겨 붙이는 길은 두지 않았다.
    """
    vps, bad = resolve_merge(slide, idxs)
    if bad:
        raise ValueError(" · ".join(bad))

    plan = build_merge_plan(slide, vps)
    before = slide.viewpoints.count()
    lost_det = sum(vp.detections.count() for vp in vps)
    lost_rev = sum(vp.object_reviews.count() for vp in vps)

    run = Run.objects.create(
        kind="group", status="running", slide=slide,
        params={"tool": "regroup.apply_merge", "slide": slide.slug,
                "merge": [vp.tag for vp in vps], "source": source})

    _rebuild(slide, plan, vps, run)

    slide.state = "processing"
    slide.state_note = "시야 합치기 — 합성·검출 대기 1개"
    slide.save(update_fields=["state", "state_note"])

    run.status = "done"
    run.finished_at = timezone.now()
    run.counts = {"viewpoints_before": before, "viewpoints_after": len(plan),
                  "merged": len(vps), "created": 1,
                  "detections_lost": lost_det, "object_reviews_lost": lost_rev}
    run.save()

    return {"before": before, "after": len(plan), "merged": len(vps),
            "detections_lost": lost_det, "object_reviews_lost": lost_rev,
            "run_id": run.pk,
            "idx": next(i for i, (k, _, _) in enumerate(plan) if k == "new")}


def resolve_delete(slide, idx):
    """지울 시야를 푼다. → (`Viewpoint` 또는 None, 문제 목록)

    **마지막 시야는 못 지운다.** 시야가 0개인 슬라이드는 `done` 인 채로 검토할
    것이 없는 빈 관찰이 되고, 폴러는 `pending` 일 때만 다시 묶으므로 되돌릴 길도
    없다. 관찰째 없애려면 정보 편집 화면의 일이다.
    """
    try:
        idx = int(str(idx).strip())
    except ValueError:
        return None, [f"{idx}: 시야 번호가 아니다"]
    vp = slide.viewpoints.filter(idx=idx).first()
    if vp is None:
        return None, [f"그런 시야가 없다: g{idx}"]
    if slide.viewpoints.count() < 2:
        return None, ["마지막 시야는 지울 수 없다"]
    return vp, []


def delete_preview(slide, idx) -> dict:
    """무엇이 사라지는지. **DB 를 건드리지 않는다.** (`preview` 의 짝)"""
    vp, bad = resolve_delete(slide, idx)
    if bad:
        return {"ok": False, "errors": bad}
    before = slide.viewpoints.count()
    return {
        "ok": True, "errors": [],
        "before": before, "after": before - 1,
        "idx": vp.idx, "tag": vp.tag,
        "rows": frame_rows(vp.frames.order_by("seq")),
        "detections": vp.detections.count(),
        "object_reviews": vp.object_reviews.count(),
        "reviewed": vp.reviews.filter(done=True).exists(),
    }


@transaction.atomic
def apply_delete(slide, idx, source: str = "") -> dict:
    """시야 하나를 지운다. 한 트랜잭션이다. (2026-10-04, 217)

    촬영 순서를 잘못해 쓸모없는 묶음이 생겼을 때 쓴다. 가르기로 떼어 낸 뒤
    지우면 시야 안의 일부 사진만 버릴 수도 있다.

    **사진(`Frame`) 행은 남는다** — `SET_NULL` 이라 시야만 떨어져 나가 "어느
    시야에도 안 든 사진" 이 된다(그룹핑 전 사진과 같은 모양). 지우지 않는 것은
    폴더에 파일이 그대로 있기 때문이다: 행이 있어야 디스크와 테이블이 맞고,
    `check_db` 의 "원본 프레임 파일이 있다" 도 그대로 성립한다. 폴러는 폴더
    단위(`Slide.image_dir`)로만 새것을 가리므로 다시 반입하지 않는다.

    다른 시야는 그대로 두고 번호만 빈틈없이 다시 매긴다. 새로 만들 시야가 없어
    슬라이드를 `processing` 으로 돌리지 않는다 — 검토가 잠기지 않는다.
    """
    vp, bad = resolve_delete(slide, idx)
    if bad:
        raise ValueError(" · ".join(bad))

    before = slide.viewpoints.count()
    frames = list(vp.frames.order_by("seq").values_list("name", flat=True))
    lost_det = vp.detections.count()
    lost_rev = vp.object_reviews.count()

    run = Run.objects.create(
        kind="group", status="running", slide=slide,
        params={"tool": "regroup.apply_delete", "slide": slide.slug,
                "delete": vp.tag, "frames": frames, "source": source})

    plan = [("keep", v, None) for v in slide.viewpoints.order_by("idx")
            if v.pk != vp.pk]
    gone = vp.idx
    _rebuild(slide, plan, [vp], run)

    run.status = "done"
    run.finished_at = timezone.now()
    run.counts = {"viewpoints_before": before, "viewpoints_after": len(plan),
                  "deleted": 1, "frames_unassigned": len(frames),
                  "detections_lost": lost_det, "object_reviews_lost": lost_rev}
    run.save()

    return {"before": before, "after": len(plan), "frames": len(frames),
            "detections_lost": lost_det, "object_reviews_lost": lost_rev,
            "run_id": run.pk,
            # 지운 자리에 이제 놓인 시야로 — 끝을 지웠으면 그 앞 시야로
            "idx": min(gone, len(plan) - 1)}


def _rebuild(slide, plan, doomed, run):
    """`plan` 대로 슬라이드의 시야를 다시 세운다 — 가르기·합치기가 함께 쓴다.

    `doomed` 를 지우고, `"new"` 항목마다 시야를 새로 만들어 프레임을 옮기고,
    `idx` 를 0부터 다시 매긴다. 두 도구의 차이는 `plan` 을 짜는 데뿐이다.
    """
    # 프레임은 `SET_NULL` 이라 시야를 지워도 살아남는다. 살아남아야 한다 —
    # 다시 붙일 것이 그것이다.
    for vp in doomed:
        vp.delete()

    # 유일 제약을 피해 전부 치워 두고 0부터 다시 매긴다
    Viewpoint.objects.filter(slide=slide).update(idx=F("idx") + IDX_PARK)
    taken = set(Viewpoint.objects.filter(slide=slide)
                .values_list("tag", flat=True))

    for i, (kind, old, frames) in enumerate(plan):
        if kind == "keep":
            old.idx = i                       # tag 는 건드리지 않는다
            old.save(update_fields=["idx"])
            continue
        a, b = frames[0].acquired_at, frames[-1].acquired_at
        vp = Viewpoint.objects.create(
            slide=slide, idx=i, tag=_tag(i, frames, taken),
            n_frames=len(frames),
            span_sec=((b - a).total_seconds() if a and b else None),
            grouping_run=run)
        best = max(frames, key=lambda f: f.sharpness or 0.0)
        for f in frames:
            f.viewpoint = vp
            f.is_sharpest = (f.pk == best.pk)
            f.save(update_fields=["viewpoint", "is_sharpest"])
            # **이미지 행도 새 시야를 따라간다** (P06). 프레임은 살아남고
            # 시야만 갈리므로, 안 맞추면 테이블이 디스크와 조용히 어긋난다.
            ensure_frame_image(f)
        vp.sharpest_frame = best
        vp.save(update_fields=["sharpest_frame"])


def _tag(idx: int, frames, taken: set) -> str:
    """`group_focus_series.py` 와 같은 모양으로 짓는다.

    같은 슬라이드 안에서 부딪히면 안 된다 — 부딪히면 `focus_stack` 이 남의
    합성본을 보고 "이미 했다" 며 건너뛴다. 프레임 이름이 유일해서 실제로 부딪힐
    일은 없지만, 조용히 틀리는 자리라 확인하고 넘어간다.
    """
    base = f"g{idx:03d}_{frames[0].name}-{frames[-1].name.split('-')[-1]}"
    tag, n = base, 2
    while tag in taken:
        tag = f"{base}_r{n}"
        n += 1
    taken.add(tag)
    return tag
