"""로스해 확대 지도 — Natural Earth 1:10m 해안선·빙붕을 EPSG:3031 로 투영해
로스해 틀 안쪽만 잘라 SVG path 로 굽는다.

    curl -sSL -o ne_10m_land.geojson \\
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson
    curl -sSL -o ne_10m_antarctic_ice_shelves_polys.geojson \\
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_antarctic_ice_shelves_polys.geojson
    python3 build_map_ross.py coast ne_10m_land.geojson ne_10m_antarctic_ice_shelves_polys.geojson 1500
    python3 build_map_ross.py bathy 3000 ne_10m_bathymetry_K_200.geojson ne_10m_bathymetry_J_1000.geojson …

`bathy` 는 수심대(200 · 1000 · 2000 · 3000 · 4000 m — 파일 이름에서 읽는다)를
`BATHY = [(깊이, path), …]` 로 낸다. 각 다각형이 "그 깊이보다 깊은 바다" 라
얕은 것부터 차례로 겹쳐 그리면 색이 단계로 깊어진다. 바탕색이라 획이 없고
이음매도 문제가 안 되어 면만 낸다 — 허용오차도 해안선보다 성글게 준다.
**대략이다.** NE 의 수심은 1:10m 에서도 많이 일반화되어 있어 로스해 대륙붕의
은행·골(수백 m 규모)은 안 나온다 — 어디가 대륙붕이고 어디가 사면인지를 보는
바탕이지 계측이 아니다.

`build_map.py`(남극 전체)와 **같은 투영(EPSG:3031)·같은 단위(km)** 인데
**180° 돌려 놓았다.** 전체 지도는 0° 가 위라 로스해(180° 언저리)에서는 남극점이
위, 북쪽이 아래로 온다 — 빙붕이 위에 있고 빅토리아랜드가 오른쪽인 지도는
누구도 그렇게 보지 않는다. 좌표를 (x, y) → (−x, −y) 로 뒤집으면 중앙자오선이
180° 인 극구면투영이 되어 북쪽이 위·빅토리아랜드가 왼쪽·빙붕이 아래로 놓인다.
뷰어는 `_polar_xy` 값을 같은 식으로 뒤집어 마커를 찍고(`ross.to_xy`), 전체
지도 위의 틀 사각형은 뒤집기 전 좌표(`ross.FRAME`)로 그린다. 그 밖에 다른 것은
셋이다.

- **10m 자료다.** 50m 를 10 km 로 단순화한 전체 지도는 화면 폭 900 px 에
  9,200 km 를 담아 1 px 의 1/10 이었지만, 로스해 틀(1,500 km)에서는 같은 정점이
  6 px 마다 하나라 해안선이 각져 보인다
- **틀 밖은 버린다.** 남극 대륙 고리 하나가 10m 자료에서 정점 수만 개라 그대로
  단순화하면 HTML 이 무거워진다. 서덜랜드-호지먼으로 틀(여유를 조금 둔 사각형)에
  자르고 나서 단순화한다 — 잘린 자리에 틀 가장자리를 따라가는 변이 생기지만
  SVG 쪽 clipPath 가 틀 안쪽만 보이게 해서 화면에는 안 나온다
- **빙붕을 따로 낸다.** NE 의 `land` 는 남극에서 빙붕 앞면을 해안선으로 삼는다
  (로스 빙붕까지 육지다). 시료가 앉는 바다와 빙붕의 경계가 곧 빙붕 앞면이고
  그 안쪽이 접지된 육지인지 떠 있는 얼음인지가 시추 자료를 읽을 때 뜻이
  있어서 `ice_shelves_polys` 를 육지 위에 다른 색으로 얹는다

**면과 선을 따로 낸다** (`LAND`/`LAND_LINE` · `SHELF`/`SHELF_LINE`). NE 자료는
다각형을 180° 자오선에서 갈라 놓아, 면에 획을 두르면 **로스 빙붕 한가운데로
세로선이 지나간다** — 시료가 앉는 바로 그 자리다. 자른 사각형의 가장자리도
같은 종류의 가짜 변이다. 면은 획 없이 채우고, 선은 그 두 자리에 놓인 변을
뺀 열린 polyline 으로 따로 긋는다.

**나온 path 를 파이썬 소스에 넣을 때 줄바꿈이 좌표 한가운데 떨어지면 안 된다.**
서브패스(`M`)마다 한 줄씩 쓴다 — devlog 021 에서 백지 지도로 당했다.
"""
import json
import math
import re
import sys

import proj

# 로스해 틀 — **돌리기 전** 전체 지도 좌표(km · SVG 방향)다. `web/viewer/ross.py`
# 의 FRAME 과 같은 값이어야 한다 — 여기서 자른 것보다 화면이 넓으면 가장자리가
# 빈다.
FRAME = (-850, 950, 1500, 1200)
# 자르는 사각형은 틀보다 조금 넓게 — 단순화가 가장자리 정점을 옮겨도 틀 안이
# 비지 않게. clipPath 가 틀에서 다시 자른다.
PAD = 30


def simplify(pts, tol):
    """Douglas-Peucker. build_map.py 와 같은 구현이다."""
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    worst, wi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (abs(dy * px - dx * py + bx * ay - by * ax) / n) if n \
            else math.hypot(px - ax, py - ay)
        if d > worst:
            worst, wi = d, i
    if worst <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:wi + 1], tol)[:-1] + simplify(pts[wi:], tol)


def clip_rect(pts, x0, y0, x1, y1):
    """서덜랜드-호지먼 — 다각형을 볼록한 창(여기서는 사각형)에 자른다.

    변 넷에 차례로 자른다. 창 밖의 정점은 버리고 창 경계를 넘는 변은 교점으로
    바꾼다. 오목한 다각형(해안선이 그렇다)도 사각형 창에는 문제없이 잘린다 —
    다만 창 밖에서 갈라진 조각이 창 가장자리를 따라 이어진 한 고리로 나온다.
    화면에서는 그 변이 clipPath 아래 숨는다.
    """
    def inside(p, edge):
        k, v, sign = edge
        return sign * (p[k] - v) >= 0

    def cross(a, b, edge):
        k, v, _ = edge
        t = (v - a[k]) / (b[k] - a[k])
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

    out = pts
    for edge in ((0, x0, 1), (0, x1, -1), (1, y0, 1), (1, y1, -1)):
        if not out:
            return []
        src, out = out, []
        prev = src[-1]
        for cur in src:
            if inside(cur, edge):
                if not inside(prev, edge):
                    out.append(cross(prev, cur, edge))
                out.append(cur)
            elif inside(prev, edge):
                out.append(cross(prev, cur, edge))
            prev = cur
    return out


def rings(geom):
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    return [r for poly in geom["coordinates"] for r in poly]


def is_seam(a, b, x0, y0, x1, y1, eps=500.0):
    """이 변이 180° 자오선(x = 0) 이나 자른 사각형의 가장자리에 놓였는가 (m).

    투영 오차로 정확히 0 은 아니라서 반 km 안이면 같은 자리로 본다.
    """
    def on(k, v):
        return abs(a[k] - v) < eps and abs(b[k] - v) < eps
    return on(0, 0) or on(0, x0) or on(0, x1) or on(1, y0) or on(1, y1)


def outline(ring, x0, y0, x1, y1):
    """고리를 이음매를 뺀 열린 polyline 들로 가른다."""
    runs, cur = [], [ring[0]]
    pts = ring + [ring[0]]
    for a, b in zip(pts, pts[1:]):
        if is_seam(a, b, x0, y0, x1, y1):
            if len(cur) > 1:
                runs.append(cur)
            cur = [b]
        else:
            cur.append(b)
    if len(cur) > 1:
        runs.append(cur)
    return runs


def bake(src, tol_m, what):
    x0 = (FRAME[0] - PAD) * 1000
    y0 = (FRAME[1] - PAD) * 1000
    x1 = (FRAME[0] + FRAME[2] + PAD) * 1000
    y1 = (FRAME[1] + FRAME[3] + PAD) * 1000
    d = json.load(open(src))
    out = []
    raw = kept = 0
    for f in d["features"]:
        for ring in rings(f["geometry"]):
            if not ring or min(p[1] for p in ring) > -60:   # 남극권 밖은 버린다
                continue
            # 투영하고 y 를 SVG 방향으로 뒤집는다 — 자르기도 그 좌표에서 한다
            xy = [(x, -y) for x, y in (proj.fwd(lon, lat) for lon, lat in ring)]
            xy = clip_rect(xy, x0, y0, x1, y1)
            if len(xy) < 4:
                continue
            raw += len(xy)
            s = simplify(xy, tol_m)
            if len(s) < 4:
                continue
            kept += len(s)
            out.append(s)

    # km 로 줄이고 **180° 돌린다** (머리말). 이음매 판정은 돌리기 전 좌표에서
    # 했으므로 여기서만 부호를 뒤집는다
    def sv(p):
        return f"{-p[0] / 1000:.0f},{-p[1] / 1000:.0f}"

    fills = ["M" + "L".join(sv(p) for p in r) + "Z" for r in out]
    lines = ["M" + "L".join(sv(p) for p in run)
             for r in out for run in outline(r, x0, y0, x1, y1)]
    sys.stderr.write(f"{what}: 고리 {len(out)}개 · 정점(자른 뒤) {raw} → {kept}"
                     f" · 선 {len(lines)}개\n")
    return fills, lines


def _print(name, paths):
    print(f"{name} = (")
    for p in paths:
        print(f'    "{p}"')
    print(")\n")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "coast":
        land, shelf, tol = sys.argv[2], sys.argv[3], float(sys.argv[4])
        for name, src in (("LAND", land), ("SHELF", shelf)):
            fills, lines = bake(src, tol, name)
            _print(name, fills)
            _print(name + "_LINE", lines)
    elif mode == "bathy":
        tol, srcs = float(sys.argv[2]), sys.argv[3:]
        bands = []
        for src in srcs:
            m = re.search(r"_([A-L])_(\d+)\.geojson$", src)
            if not m:
                sys.exit(f"수심을 이름에서 못 읽는다: {src}")
            fills, _ = bake(src, tol, f"bathy {m.group(2)} m")
            bands.append((int(m.group(2)), fills))
        bands.sort()
        print("BATHY = [")
        for depth, fills in bands:
            print(f"    ({depth}, (")
            for p in fills:
                print(f'        "{p}"')
            print("    )),")
        print("]\n")
    else:
        sys.exit("모드는 coast 또는 bathy")
