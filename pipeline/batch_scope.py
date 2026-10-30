#!/usr/bin/env python3
"""어느 묶음이 어느 **권역**을 보는가 — 규칙은 여기 하나뿐이다 (2026-08-26).

검출 방침이 권역마다 갈렸다(사용자 2026-08-26): **남극은 YOLO 로 학습시키고,
한국(BP)은 SAM 으로만 본다.** 그런데 폴러는 조리법이 적힌 묶음마다 **새 슬라이드
전부**를 돌아서, 방침을 말로만 정해 두면 자료가 들어오는 순간 조용히 어겨진다 —
실제로 한국 BP 두 슬라이드에 `yolo-3차` 검출이 467건 들어와 있었다.

그래서 묶음이 **자기가 보는 권역**을 조리법에 적는다.

    recipe = {"backend": "yolo", ..., "areas": ["ant"]}

- **`areas` 가 없으면 전부 본다.** 옛 묶음은 아무것도 안 바뀐다
- `Site.area` 의 값을 그대로 쓴다 (`ant`·`kr`)

**`segment_diatoms.py` 가 스스로 거부한다.** 폴러에서만 거르면 손으로 부를 때
새고, `poll_nas.sh` 는 슬라이드의 권역을 모른다(`pending_slides.py` 가 슬러그만
준다). 검출을 실제로 내는 자리에 두면 **폴러로 부르든 손으로 부르든 같다.**

## 권역을 못 읽으면 건너뛴다

소속을 잃은 슬라이드는 권역이 없다(`check_db.py` 7번이 세는 그 상태다).
그때 **거르는 쪽으로 넘어진다** — 방침을 지키자고 둔 문이 "모르겠으면 통과"
이면 문이 아니다. 대신 **말하고 건너뛴다**(조용히 빠지면 "왜 이 슬라이드만
비어 있나" 를 나중에 묻게 된다).

## 관찰 이름표로도 뺀다 — `exclude_obs` (P29 6절 5 · 248)

    recipe = {..., "areas": ["ant"], "exclude_obs": ["Smear"]}

**권역만으로는 RS21 Smear 가 통과한다** — 남극 시료인데 SAM 으로만 센다(사용자 10-21). 그래서
관찰 이름표(`Slide.obs_label`)로도 뺀다. 이름표는 대소문자·앞뒤 공백을 안 가린다.

**이름표를 모르면 거른다** — 권역과 같은 원칙이다. 다만 **이름표가 없는 관찰(`""`)은 "모름" 이
아니라 "이름표 없음" 이라 통과한다** — 대부분의 관찰이 그렇다. 부르는 쪽이 이름표를 안 넘기면
(`obs_label` 을 빠뜨리면) 모르는 것으로 친다 — 넘기는 것을 잊은 자리가 조용히 통과시키지 않게.

Django 를 부르지 않는다 — `naming.py`·`judge.py` 와 같은 자리다. 부르는 쪽이
조리법 dict 와 권역 문자열·관찰 이름표를 준다.
"""
from __future__ import annotations

KEY = "areas"
EXCLUDE_OBS = "exclude_obs"
_UNKNOWN = object()          # 이름표를 안 넘겼다 — 모르는 것으로 친다


def allowed_areas(recipe: dict | None) -> list[str] | None:
    """이 조리법이 보는 권역들. **`None` 이면 전부 본다.**"""
    if not recipe:
        return None
    raw = recipe.get(KEY)
    if raw is None:
        return None
    if isinstance(raw, str):                    # "ant" · "ant,kr" 도 받는다
        raw = [x for x in (s.strip() for s in raw.split(",")) if x]
    areas = [str(x).strip() for x in raw if str(x).strip()]
    # **빈 목록은 "전부" 가 아니다** — 아무것도 안 본다는 뜻이다. 비어 버린
    # 값이 조용히 "전부" 로 읽히면 막으려던 것이 그대로 통과한다.
    return areas


def excluded_obs(recipe: dict | None) -> list[str]:
    """이 조리법이 빼는 관찰 이름표들(소문자). 없으면 빈 목록."""
    raw = (recipe or {}).get(EXCLUDE_OBS) or []
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(x).strip().lower() for x in raw if str(x).strip()]


def restricts(recipe: dict | None) -> bool:
    """이 조리법이 슬라이드를 가르는가 — 권역이든 이름표든. 안 가르면 물을 것이 없다."""
    return allowed_areas(recipe) is not None or bool(excluded_obs(recipe))


def _area_ok(recipe, area) -> bool:
    areas = allowed_areas(recipe)
    if areas is None:
        return True
    if not area:
        return False                            # 권역을 모르면 거른다 (머리말)
    return area in areas


def _obs_ok(recipe, obs_label) -> bool:
    ex = excluded_obs(recipe)
    if not ex:
        return True
    if obs_label is _UNKNOWN or obs_label is None:
        return False                            # 이름표를 모르면 거른다 (머리말)
    return str(obs_label).strip().lower() not in ex


def allows(recipe: dict | None, area: str | None, obs_label=_UNKNOWN) -> bool:
    """그 슬라이드(권역 · 관찰 이름표)를 이 묶음이 도는가.

    `obs_label` 은 `Slide.obs_label` 그대로 준다 — 이름표가 없으면 `""`. 조리법이 이름표를 안
    가르면 안 줘도 된다.
    """
    return _area_ok(recipe, area) and _obs_ok(recipe, obs_label)


def why(recipe: dict | None, area: str | None, label: str = "",
        obs_label=_UNKNOWN) -> str:
    """건너뛰는 이유 한 줄. 도는 경우에는 빈 문자열."""
    if allows(recipe, area, obs_label):
        return ""
    who = f"묶음 '{label}'" if label else "이 묶음"
    if _area_ok(recipe, area):                  # 권역은 맞다 — 이름표에서 걸렸다
        ex = "·".join(excluded_obs(recipe))
        if obs_label is _UNKNOWN or obs_label is None:
            return (f"{who} 은 관찰 이름표 {ex} 를 뺀다 — 이 슬라이드는 **이름표를 알 수 "
                    f"없다**. 건너뛴다")
        return f"{who} 은 관찰 이름표 {ex} 를 뺀다 — 이 슬라이드는 {obs_label} 다. 건너뛴다"
    areas = allowed_areas(recipe) or []
    scope = "·".join(areas) if areas else "(아무 권역도 아니다)"
    if not area:
        return (f"{who} 은 권역 {scope} 만 본다 — 이 슬라이드는 **권역을 알 수 "
                f"없다**(소속이 없다). 건너뛴다")
    return f"{who} 은 권역 {scope} 만 본다 — 이 슬라이드는 {area} 다. 건너뛴다"


def label_for_plan(recipe: dict | None) -> str:
    """사람이 읽는 표에 적을 한 조각."""
    areas = allowed_areas(recipe)
    out = ("권역 전부" if areas is None
           else "권역 " + ("·".join(areas) if areas else "없음"))
    ex = excluded_obs(recipe)
    return out + (f" · 이름표 {'·'.join(ex)} 빼고" if ex else "")
