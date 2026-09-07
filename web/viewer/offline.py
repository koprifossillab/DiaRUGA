"""오프라인 검토기·동정기 — 번들을 굽고, 되돌아온 것을 받는다 (P25).

현장·이동 중에는 서버에 못 붙는다. 그때도 검토와 동정은 이어져야 하므로
**화면 하나를 파일 하나로 구워 들고 나간다.** 돌아와서 결과 파일을 올리면
그것이 DB 로 들어간다.

## 화면을 두 벌 만들지 않는다

오프라인 검토기가 그리는 것은 **검토 화면 그대로**다(`_detection.html` +
`_detview_js.html`). 서버에 닿는 자리 다섯만 `window.DiaRUGA.env` 로 갈아
끼운다 — 사진은 파일 안에 실려 있고, 저장은 기록으로 받는다. 배선을 다시
적으면 교정의 규칙이 두 벌이 되고, **두 벌은 조용히 어긋난다**(038·053).

## 되돌려 넣는 것이 위험한 이유 — 지문

`/review` 는 **그 판의 교정을 통째로 갈아치운다**(017·027). 오프라인 파일은
꺼낸 시점의 상태 위에서 만든 것이라, 그 사이 누가 온라인에서 같은 시야를
검토했으면 그 판단이 통째로 사라진다.

그래서 번들이 판마다 **지문 둘**을 싣는다.

| | 무엇 | 달라졌으면 |
|---|---|---|
| `state` | 그 판에 사람이 만들어 놓은 것 전부 | **건너뛴다** — 사람이 골라야 덮어쓴다 |
| `keys` | 엔진이 낸 후보 키의 집합 | **거절한다** — 재검출이 돌아 짚을 자리가 없다 |

지문은 **양쪽이 같은 함수로 잰다**(`state_fp`·`keys_fp`). 꺼낼 때 한 번,
넣을 때 다시 한 번 — 재는 법이 갈리면 늘 충돌이거나 늘 통과다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from pathlib import Path

from django.utils import timezone

from . import data
from .models import Slide, Viewpoint

# 한 파일에 담는 시야의 상한. 시야 하나가 사진 250~400 KB 라 60이면 20 MB 쯤
# 된다 — 그보다 크면 브라우저가 열다 말고, 메일로도 못 보낸다. **막고 나서
# 무엇을 하라고 적는다**(범위를 나눠 두 번 꺼낸다).
MAX_VIEWPOINTS = 60

# 검토기의 사진 폭. **검토 화면과 같은 값이다**(`{% thumb base 1600 %}`) —
# 다르게 잡으면 같은 개체를 다른 해상도로 보게 되고, 그 차이가 판단에 든다.
VIEW_W = 1600

# 동정기의 크롭 폭. 카탈로그 카드가 쓰는 값(`cropurl … 200`)보다 크게 잡는다 —
# 오프라인에서는 이 그림 하나로 동정을 끝내야 하고, 다시 받아 올 곳이 없다.
CROP_W = 360

# 사진이 붙기 전의 자리 채우개. `src=""` 로 두면 브라우저가 **그 페이지 자신을**
# 다시 받아 온다(빈 문자열은 현재 주소다) — 파일이 두 번 파싱된다.
BLANK_PX = ("data:image/gif;base64,"
            "R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==")


# --- 범위 ------------------------------------------------------------------

def parse_gids(raw: str, ids: list[int]) -> list[int]:
    """`"1-20,25"` → 시야 번호. 빈 값이면 **그 슬라이드 전부**.

    **없는 번호는 조용히 버리지 않는다** — 사람이 적어 준 범위와 꺼낸 것이
    다르면 그 사실을 알아야 한다. 다만 오름차순으로 정렬하고 겹친 것은 한
    번만 담는다(`1-5,3` 은 다섯 개다).
    """
    raw = (raw or "").strip()
    if not raw:
        return list(ids)

    have, want, unknown = set(ids), [], []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        # `g3` 처럼 화면에 적힌 그대로 붙여 넣는 일이 잦다 — 받아 준다.
        part = part.replace("g", "")
        try:
            if "-" in part.lstrip("-"):
                a, b = part.split("-", 1)
                lo, hi = int(a), int(b)
                if lo > hi:
                    lo, hi = hi, lo
                rng = range(lo, hi + 1)
            else:
                rng = [int(part)]
        except ValueError:
            raise ValueError(f"범위를 읽을 수 없습니다: {part}")
        for i in rng:
            (want if i in have else unknown).append(i)

    if unknown:
        # **앞의 몇 개만 적는다** — `1-999` 를 넣으면 목록이 화면을 덮는다.
        head = ", ".join(f"g{i}" for i in sorted(set(unknown))[:8])
        more = "" if len(set(unknown)) <= 8 else f" 외 {len(set(unknown)) - 8}개"
        raise ValueError(f"이 슬라이드에 없는 시야입니다: {head}{more}")
    return sorted(set(want))


# --- 그림을 파일 안으로 ------------------------------------------------------

def _b64(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""


def thumb_b64(rel: str, width: int) -> str:
    """축소본 하나를 base64 로. **`data:` 접두는 안 붙인다.**

    화면이 `atob` 로 풀어 Blob 을 만들고 그 주소를 쓴다 — `data:` URI 를 그대로
    쓰면 같은 400 KB 짜리 글자가 `<img src>` 와 캐러셀 속성 셋에 **여러 벌**
    앉는다. 파일이 그만큼 커지고, 브라우저도 같은 그림을 여러 번 디코드한다.

    축소본은 검토 화면이 쓰는 그 캐시를 그대로 쓴다.
    """
    # **부를 때 들인다** — `views` 가 이 모듈을 임포트하므로 위에서 부르면
    # 순환이 된다. 축소본을 굽는 규칙을 여기 또 적지 않으려고 이렇게 한다.
    from .views import _thumbnail

    p = data.safe_image_path(rel)
    if p is None:
        return ""
    return _b64(_thumbnail(p, width))


def crop_b64(rel: str, c: dict, width: int = CROP_W) -> str:
    """개체 하나를 **세워서** 잘라 낸 것 (카탈로그 카드와 같은 규칙).

    방향이 통일돼야 형태를 나란히 비교할 수 있고, 동정은 그 비교로 한다.
    """
    from .views import _crop_thumb, _upright_thumb

    p = data.safe_image_path(rel)
    if p is None:
        return ""
    box = [int(round(float(v))) for v in (c.get("bbox_xywh") or [])]
    if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
        return ""
    geo = data.crop_geometry(c, rotate=True)
    if geo:
        ow, oh = (int(v) for v in geo["out"].split(","))
        out = _upright_thumb(p, box, width, geo["rot"], (ow, oh))
    else:
        out = _crop_thumb(p, box, width, None)
    return _b64(out)


# --- 지문 ------------------------------------------------------------------

def _fp(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def _is_manual(d: dict) -> bool:
    """사람이 그린 개체인가. **화면의 `isManual` 과 같은 규칙이다.**"""
    return d.get("source") == "manual"


def state_fp(det: dict) -> str:
    """그 판에 **사람이 만들어 놓은 것 전부**의 지문.

    무엇을 담는가가 곧 "무엇이 바뀌면 충돌인가" 다. 담는 것:

    - 지운 것 · 되살린 것 · 사람이 지정한 유형
    - 사람이 그린 개체와 손으로 고친 경계(폴리곤 그대로)
    - 개체 카탈로그의 넷(종명·등급·자세·코멘트)
    - 검토 완료 표시

    **엔진이 낸 유형(`cls`)도 담는다.** 재검출·문턱 변경으로 그것이 바뀌면
    사람이 오프라인에서 본 화면과 지금 화면이 다른 것이고, 그 위에 옛 판단을
    덮어쓰면 안 된다.
    """
    rows = []
    for d in (det.get("candidates") or []) + (det.get("removed_candidates") or []):
        key = data.cand_key(d)
        # 기하는 **사람이 만든 것일 때만** 담는다 — 엔진의 폴리곤까지 넣으면
        # 지문이 검출 자료 전체의 해시가 되어 `keys` 지문과 하는 일이 겹친다.
        poly = (list(d.get("polygon") or [])
                if (_is_manual(d) or d.get("geom_edited")) else None)
        rows.append([key, bool(d.get("removed")), d.get("cls") or "",
                     d.get("species") or "", d.get("grade") or "",
                     d.get("pose") or "", d.get("note") or "", poly])
    rows.sort(key=lambda r: (r[0], r[1]))
    return _fp({"rows": rows,
                "accepted": sorted(det.get("accepted_keys") or []),
                "labels": det.get("labels") or {},
                "done": bool(det.get("review_done")),
                "note": det.get("review_note") or ""})


def keys_fp(det: dict) -> str:
    """**엔진이 낸 후보 키의 집합**. 재검출이 돌면 달라진다.

    탈락분까지 담는다 — 되살리기는 그쪽을 짚으므로, 문턱만 다시 걸어도
    (`refilter.py`) 사람이 보던 목록과 달라진다.
    """
    keys = set()
    for name in ("candidates", "removed_candidates", "rejected"):
        for d in det.get(name) or []:
            if not _is_manual(d) and not d.get("orphan"):
                keys.add(data.cand_key(d))
    return _fp(sorted(keys))


# --- 번들 ------------------------------------------------------------------

def _head(slide: Slide, kind: str, gids: list[int]) -> dict:
    """결과 파일이 되돌려 보낼 머리. **어디서 왔는가가 전부 여기 있다.**"""
    return {
        "id": uuid.uuid4().hex[:12],
        "kind": kind,
        "slug": slide.slug,
        "label": slide.name,
        # 검토 대상 묶음. **다르면 반입을 거절한다** — 다른 엔진의 판 위에
        # 만든 교정은 키가 거의 전부 어긋난다(051).
        "batch": data.review_batch_id(),
        "batch_label": data.review_batch_label(),
        "made_at": timezone.now().isoformat(timespec="seconds"),
        "gids": list(gids),
    }


def review_bundle(slug: str, gids: list[int]) -> dict:
    """검토기 한 벌. 시야마다 **합성본 한 장**과 그 판의 검출·교정.

    **프레임은 안 싣는다**(P25 3.2) — 시야당 5~7장이라 파일이 다섯 배가 된다.
    판이 하나뿐이면 캐러셀의 `swapDet` 이 곧장 빠져나가므로 화면은 그대로 돈다.
    """
    slide = Slide.objects.filter(slug=slug).first()
    if slide is None:
        raise ValueError(f"모르는 슬라이드입니다: {slug}")

    views, skipped, n_bytes = [], [], 0
    for gid in gids:
        ctx = data.group_detail(slug, gid)
        if ctx is None:
            skipped.append({"gid": gid, "why": "시야를 찾지 못했습니다"})
            continue
        det, rel = ctx.get("base_det"), ctx.get("base_rel")
        if not det or not rel:
            skipped.append({"gid": gid, "why": "아직 합성하지 않았습니다"})
            continue
        if det.get("preview_only"):
            skipped.append({"gid": gid, "why": "이 묶음의 검출이 없습니다"})
            continue
        b64 = thumb_b64(rel, VIEW_W)
        if not b64:
            skipped.append({"gid": gid, "why": "사진 파일을 읽지 못했습니다"})
            continue
        n_bytes += len(b64)
        views.append({
            "uid": f"vp{gid}",
            "gid": gid,
            "tag": ctx.get("tag") or "",
            "det": det,
            "rel": rel,
            "image": ctx.get("base_image"),
            "name": ctx.get("base_name") or "합성본",
            "b64": b64,
            # 캐러셀이 쓰는 한 판짜리 목록. `_shots.html` 이 이것으로 단추를
            # 그리고, 그림은 화면이 붙인다(오프라인은 주소가 없다).
            "stack": {"focused_rel": rel, "detkey": "__stack__",
                      "detection": det},
            "state": state_fp(det),
            "keys": keys_fp(det),
            "done": bool(det.get("review_done")),
            "n": len(det.get("candidates") or []),
        })

    # **이웃 시야로 가는 길** — 주소가 아니라 `#g<번호>` 다. 캐러셀의 «»
    # 단추와 `Ctrl+←/→` 가 이 값을 쓰고, 껍데기가 `hashchange` 로 판을 바꾼다.
    # `leave()` 를 그대로 지나므로 **못 나간 저장이 있으면 안 떠난다**(116).
    for i, v in enumerate(views):
        v["prev_id"] = views[i - 1]["gid"] if i else None
        v["next_id"] = views[i + 1]["gid"] if i + 1 < len(views) else None
        v["prev_url"] = f"#g{v['prev_id']}" if v["prev_id"] is not None else None
        v["next_url"] = f"#g{v['next_id']}" if v["next_id"] is not None else None

    head = _head(slide, "review", [v["gid"] for v in views])
    # 화면과 결과 파일이 함께 들고 다닐 것 — **지문은 여기 한 벌만 둔다.**
    head["views"] = [{"gid": v["gid"], "image": v["image"], "tag": v["tag"],
                      "state": v["state"], "keys": v["keys"]} for v in views]
    return {"head": head, "views": views, "skipped": skipped,
            "n_bytes": n_bytes, "slide": slide}


def catalog_bundle(slug: str, gids: list[int]) -> dict:
    """동정기 한 벌. **개체마다 크롭 한 장**과 카드 넷.

    시야 사진을 안 싣는다 — 동정은 개체를 보고 하는 일이고, 그림이 크롭이면
    같은 파일에 개체 500개가 들어간다.
    """
    slide = Slide.objects.filter(slug=slug).first()
    if slide is None:
        raise ValueError(f"모르는 슬라이드입니다: {slug}")

    want = set(gids)
    cards, skipped, n_bytes = [], [], 0
    # **카탈로그와 같은 문으로 고른다** — 카드가 무엇인가(개체 하나)를 두 곳에서
    # 정하면 화면마다 다른 것을 카드라 부르게 된다 (`data.catalog_rows`).
    for r in data.catalog_rows(slug):
        if r["group_id"] not in want:
            continue
        view = r.get("view") or r
        rel = view.get("rel") or r["image_rel"]
        b64 = crop_b64(rel, view)
        if not b64:
            skipped.append({"gid": r["group_id"],
                            "why": f'{r["catalog_no"]} 의 크롭을 못 만들었습니다'})
            continue
        n_bytes += len(b64)
        cards.append({
            "gid": r["group_id"], "image": r["image_id"], "key": r["key"],
            "no": r["catalog_no"], "cls": r.get("cls") or "",
            "species": r.get("species") or "", "grade": r.get("grade") or "",
            "pose": r.get("pose") or "", "note": r.get("note") or "",
            "major_um": r.get("major_um"), "minor_um": r.get("minor_um"),
            "b64": b64,
            # 카드 하나의 지문. **검토기와 달리 판이 아니라 개체 단위다** —
            # 저장 문이 좁아(`/catalog/save`) 충돌도 그 단위로 난다.
            "fp": _fp([r.get("species") or "", r.get("cls") or "",
                       r.get("grade") or "", r.get("pose") or "",
                       r.get("note") or ""]),
        })

    head = _head(slide, "catalog", sorted({c["gid"] for c in cards}))
    head["cards"] = [{"gid": c["gid"], "image": c["image"], "key": c["key"],
                      "no": c["no"], "fp": c["fp"]} for c in cards]
    return {"head": head, "cards": cards, "skipped": skipped,
            "n_bytes": n_bytes, "slide": slide}


# --- 되돌려 넣기 -------------------------------------------------------------
#
# **두 걸음이다** — 첫 POST 는 무엇이 바뀌는지 보여 주기만 하고, `apply=1` 이
# 실린 두 번째 POST 만 쓴다 (`split_group` 과 같은 모양).
#
# **지문은 두 번 다 잰다.** 미리보기와 적용 사이에 누가 온라인에서 그 시야를
# 검토할 수 있다 — 미리보기 때 통과한 것을 그대로 쓰면 그 판단을 덮어쓴다.

def read_result(raw: bytes) -> dict:
    """올라온 결과 파일을 읽는다. **모양이 아니면 여기서 멈춘다.**

    남이 만든 자료다 — 이 서버 밖에서 며칠을 돌아 온다. 안의 값은
    `views.parse_review_payload` 가 다시 본다(화면이 보내는 것과 같은 문이다).
    """
    try:
        res = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ValueError("JSON 파일이 아닙니다 — 오프라인 화면의 "
                         "「결과 내려받기」 가 낸 파일을 올리십시오.")
    if not isinstance(res, dict) or res.get("diaruga_offline") != 1:
        raise ValueError("DiaRUGA 오프라인 결과 파일이 아닙니다.")
    if res.get("kind") not in ("review", "catalog"):
        raise ValueError("모르는 프로그램의 결과입니다.")
    if not isinstance(res.get("bundle"), dict):
        raise ValueError("어디서 꺼낸 것인지가 파일에 없습니다.")
    for name in ("review", "done", "note", "catalog"):
        if name in res and not isinstance(res[name], list):
            raise ValueError(f"`{name}` 의 모양이 이상합니다.")
    return res


def _n(label: str, n: int) -> str:
    """수가 0 이면 아예 안 적는다 — 없는 것을 `0` 으로 적으면 눈이 그것을 센다."""
    return f"{label}{n}" if n else ""


def _review_what(det: dict, e: dict) -> str:
    """이 판이 **어떻게 달라지는가** 를 한 줄로.

    "무엇이 바뀌는지" 를 안 적으면 사람은 목록을 보고도 누를지 말지를 정할 수
    없다 — 지우기 문턱을 버튼에 적어 두는 것과 같은 자리다 (063).
    """
    now_rm = {k for k in (data.cand_key(d)
                          for d in det.get("removed_candidates") or [])
              if not data.MANUAL_KEY.match(k)}
    new_rm = {str(k) for k in (e.get("removed") or [])}
    now_lab = det.get("labels") or {}
    new_lab = e.get("labels") or {}
    now_drawn = {data.cand_key(d)
                 for d in (det.get("candidates") or []) + (det.get("removed_candidates") or [])
                 if _is_manual(d)}
    new_drawn = {str(d.get("key")) for d in (e.get("drawn") or []) if d.get("key")}
    now_geom = {data.cand_key(d) for d in det.get("candidates") or []
                if d.get("geom_edited")}
    new_geom = {k for k, v in (e.get("edits") or {}).items() if v}

    parts = [_n("지우기 +", len(new_rm - now_rm)),
             _n("되살리기 ", len(now_rm - new_rm)),
             _n("유형 ", len({k for k in set(now_lab) | set(new_lab)
                              if now_lab.get(k) != new_lab.get(k)})),
             _n("그린 것 +", len(new_drawn - now_drawn)),
             _n("그린 것 지움 ", len(now_drawn - new_drawn)),
             _n("경계 ", len(new_geom ^ now_geom))]
    parts = [p for p in parts if p]
    return " · ".join(parts) if parts else "바뀌는 것이 없습니다"


def _cat_what(cur: dict, e: dict) -> str:
    names = {"species": "종명", "grade": "등급", "pose": "자세", "note": "코멘트"}
    out = []
    for f, label in names.items():
        if f not in e or e[f] is None:
            continue
        was, now = (cur.get(f) or ""), (e[f] or "")
        if was == now:
            continue
        out.append(f"{label} {was or '—'} → {now or '—'}")
    return " · ".join(out) if out else "바뀌는 것이 없습니다"


def _cands_by_key(det: dict) -> dict:
    out = {}
    for d in (det.get("candidates") or []) + (det.get("removed_candidates") or []):
        out[data.cand_key(d)] = d
    return out


def plan(res: dict) -> dict:
    """무엇이 어떻게 될지 **재 보기만 한다.** 아무것도 안 쓴다.

    막는 자리가 셋이고 **뜻이 다르다** (P25 4절).

    | | 왜 | 어떻게 |
    |---|---|---|
    | `reject` | 짚을 자리가 없어졌다 (재검출·다른 묶음·없는 시야) | 사람도 못 고른다 |
    | `conflict` | 그 사이 온라인에서 누가 만졌다 | 골라야 덮어쓴다 |
    | `ok` | 꺼낼 때 그대로다 | 기본으로 적용 |
    """
    head = res.get("bundle") or {}
    out = {"kind": res.get("kind"), "head": head, "by": res.get("by") or "",
           "saved_at": res.get("saved_at") or "", "rows": [], "stop": ""}

    slide = Slide.objects.filter(slug=head.get("slug")).first()
    if slide is None:
        out["stop"] = f"이 서버에 없는 슬라이드입니다: {head.get('slug')}"
        return out
    out["slide"] = slide

    # **묶음이 다르면 통째로 멈춘다.** 다른 엔진의 판 위에서 한 교정은 키가
    # 거의 전부 어긋난다(051) — 줄마다 거절할 일이 아니라 파일이 안 맞는 것이다.
    if head.get("batch") != data.review_batch_id():
        out["stop"] = (f"꺼낼 때의 검토 대상 묶음({head.get('batch_label')})과 "
                       f"지금({data.review_batch_label()})이 다릅니다. "
                       "묶음을 되돌리거나, 지금 묶음으로 다시 꺼내 검토하십시오.")
        return out

    was = {int(v["gid"]): v for v in (head.get("views") or []) if "gid" in v}
    was_cards = {(int(c["gid"]), str(c["key"])): c
                 for c in (head.get("cards") or []) if "gid" in c}

    seen: dict[int, dict] = {}

    def look(gid: int):
        """그 시야의 **지금** 모습. 한 번만 묻는다 (105)."""
        if gid not in seen:
            ctx = data.group_detail(slide.slug, gid) or {}
            seen[gid] = {"det": ctx.get("base_det"), "image": ctx.get("base_image")}
        return seen[gid]

    def row(kind, gid, token, what, edit, status="ok", why=""):
        out["rows"].append({"kind": kind, "gid": gid, "token": token,
                            "what": what, "status": status, "why": why,
                            "edit": edit})

    def guard(gid: int, whole: bool):
        """그 시야를 지금 짚을 수 있는가. `(status, why, 지금 모습)`.

        **`whole` 이 무엇을 재는지를 가른다.** 판 하나를 통째로 갈아치우는
        줄(`review`)은 지문이 없으면 아예 안 넣는다 — 무엇을 덮어쓰는지 모른 채
        갈아치우는 길을 남기지 않는다. 완료·코멘트처럼 **한 칸짜리 표시**는
        지문이 없어도 짚을 수 있다(층이 다르다 — 116).
        """
        now = look(gid)
        det = now["det"]
        if det is None:
            return "reject", "이 서버에 없는 시야입니다", now
        w = was.get(gid)
        if w is None:
            if whole:
                return ("reject", "번들에 이 시야의 지문이 없습니다 — 무엇을 "
                                  "덮어쓰는지 알 수 없습니다", now)
            return "ok", "", now
        if whole and w.get("keys") != keys_fp(det):
            return ("reject", "그 사이 검출이 다시 돌았습니다 — 후보가 달라져 "
                              "짚을 자리가 없습니다", now)
        if w.get("state") != state_fp(det):
            return ("conflict", "그 사이 온라인에서 이 시야를 만졌습니다 — "
                                "덮어쓰면 그 판단이 사라집니다", now)
        return "ok", "", now

    for e in res.get("review") or []:
        try:
            gid = int(e.get("gid"))
        except (TypeError, ValueError):
            continue
        status, why, now = guard(gid, whole=True)
        token = f"review:{gid}"
        if now["det"] is None:
            row("review", gid, token, "—", e, status, why)
            continue
        # **어느 판에 쓸 것인가까지 본다** (P09 1단계 · 116). 꺼낼 때의 판과
        # 지금 판이 다르면 그 교정은 남의 판으로 간다.
        if e.get("image") is not None and now["image"] is not None \
                and int(e["image"]) != int(now["image"]):
            status, why = "reject", "꺼낼 때와 다른 판이 열립니다"
        row("review", gid, token, _review_what(now["det"], e), e, status, why)

    for e in res.get("done") or []:
        try:
            gid = int(e.get("gid"))
        except (TypeError, ValueError):
            continue
        # **완료는 시야에 붙는 표시라 판의 교정과 층이 다르다** (116) —
        # 판이 달라졌어도 표시 하나는 짚을 수 있다.
        status, why, now = guard(gid, whole=False)
        det = now["det"]
        now_done = bool(det.get("review_done")) if det else False
        what = ("검토 완료로 표시" if e.get("done") else "검토 완료를 해제")
        if det is not None and now_done == bool(e.get("done")):
            what += " (이미 그렇습니다)"
        row("done", gid, f"done:{gid}", what, e, status, why)

    for e in res.get("note") or []:
        try:
            gid = int(e.get("gid"))
        except (TypeError, ValueError):
            continue
        status, why, now = guard(gid, whole=False)
        txt = (e.get("note") or "").strip()
        row("note", gid, f"note:{gid}", f"시야 코멘트 → {txt[:40] or '—'}",
            e, status, why)

    for e in res.get("catalog") or []:
        try:
            gid, key = int(e.get("gid")), str(e.get("key"))
        except (TypeError, ValueError):
            continue
        status, why, now = guard(gid, whole=False)
        token = f"cat:{gid}:{key}"
        det = now["det"]
        if det is None:
            row("catalog", gid, token, "—", e, "reject", why or "없는 시야입니다")
            continue
        cur = _cands_by_key(det).get(key)
        if cur is None:
            row("catalog", gid, token, "—", e, "reject",
                "그 개체가 지금 판에 없습니다")
            continue
        # **카드 하나의 지문이 따로 있으면 그것이 먼저다** — 저장 문이 개체
        # 하나라(`/catalog/save`) 충돌도 그 단위다. 같은 시야의 옆 개체를 누가
        # 만졌다고 이 카드까지 막을 이유가 없다.
        #
        # 검토기 번들에서 온 카드에는 그 지문이 없다(거기는 판 단위로 잰다) —
        # 그때는 위의 시야 지문을 그대로 쓴다.
        w = was_cards.get((gid, key))
        if w is not None:
            fp_now = _fp([cur.get("species") or "", cur.get("cls") or "",
                          cur.get("grade") or "", cur.get("pose") or "",
                          cur.get("note") or ""])
            if w.get("fp") != fp_now:
                status, why = "conflict", "그 사이 온라인에서 이 카드를 만졌습니다"
            else:
                status, why = "ok", ""
        row("catalog", gid, token, _cat_what(cur, e), e, status, why)

    out["n_ok"] = sum(1 for r in out["rows"] if r["status"] == "ok")
    out["n_conflict"] = sum(1 for r in out["rows"] if r["status"] == "conflict")
    out["n_reject"] = sum(1 for r in out["rows"] if r["status"] == "reject")
    return out


def apply_plan(res: dict, picks: set) -> dict:
    """고른 줄을 실제로 쓴다. **지문을 다시 잰다.**

    미리보기와 적용 사이에 누가 온라인에서 그 시야를 검토할 수 있다 — 그때
    미리보기의 판단을 그대로 쓰면 그 판단을 덮어쓴다. 그래서 `plan` 을 다시
    돌리고, 그 결과로 고른다.

    **한 트랜잭션으로 안 묶는다** (`_save_catalog_bulk` 와 같은 자리). 40줄 중
    하나가 걸렸다고 나머지 39줄을 되돌리면 사람은 무엇이 걸렸는지 모른 채
    전부 다시 한다.
    """
    from .views import _note, parse_review_payload

    p = plan(res)
    if p["stop"]:
        return {"stop": p["stop"], "done": [], "failed": []}

    ok, failed = [], []
    for r in p["rows"]:
        if r["token"] not in picks or r["status"] == "reject":
            continue
        gid, e = r["gid"], r["edit"]
        vp, why = data.find_viewpoint(slug=p["slide"].slug, gid=gid)
        if vp is None:
            failed.append({**r, "why": why})
            continue
        blocked = data.review_blocked(vp.slide)
        if blocked:
            failed.append({**r, "why": blocked})
            continue
        try:
            if r["kind"] == "review":
                f = parse_review_payload(e)
                data.save_review(vp, done=None, note=None,
                                 removed=f["removed"], accepted=f["accepted"],
                                 labels=f["labels"], image=f["image"],
                                 drawn=f["drawn"], edits=f["edits"])
            elif r["kind"] == "done":
                data.save_done(vp, bool(e.get("done")))
            elif r["kind"] == "note":
                data.save_note(vp, _note(e.get("note")))
            else:
                fields = {k: e[k] for k in ("species", "grade", "pose", "note")
                          if k in e and e[k] is not None}
                data.save_catalog_entry(vp, e.get("image"), str(e.get("key")),
                                        **fields)
        except ValueError as ex:
            failed.append({**r, "why": str(ex)})
            continue
        ok.append(r)
    return {"stop": "", "done": ok, "failed": failed}
