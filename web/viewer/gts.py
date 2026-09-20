"""국제 층서 연대표(ICS · IUGS) — 기준면 그림의 왼쪽 축 (209).

International Commission on Stratigraphy, *International Chronostratigraphic
Chart* v2023/09 (Cohen et al. 2013, updated) 의 신생대 부분을 **절(stage)**
까지 옮겼다. 색은 같은 표의 CGMW 공식 RGB 다 — 밝은·어두운 테마를 가리지
않고 그대로 쓴다(지질도·층서표의 관례라 바꾸면 못 알아본다). 글자는 그
위에 늘 어두운 색이다.

**DB 가 아니라 코드다** — `mis.py`·`antarctica.py` 와 같은 자리. 바뀌지
않는 참조표이고 그림의 눈금으로만 쓴다. 기준면 연령은 문헌마다 시간척도가
달라(Berggren 1985·1995 · Gradstein 2004 · GTS2012) 이 표의 경계와 수십만
년 어긋날 수 있다 — `mis.py` 머리말과 같은 사정이라 **값으로 환산하지
않는다.**

한글 이름은 대한지질학회 표기(절 이름은 음역 + 절)이고 마우스 설명에만 든다.
"""
from __future__ import annotations

# (영문, 한글, 상한 Ma, 하한 Ma, 색). 젊은 쪽부터. 66 Ma(신생대 하한)까지
PERIODS: tuple[tuple[str, str, float, float, str], ...] = (
    ("Quaternary", "제4기", 0.0, 2.58, "#f9f97f"),
    ("Neogene", "네오기", 2.58, 23.03, "#ffe619"),
    ("Paleogene", "팔레오기", 23.03, 66.0, "#fd9a52"),
)
EPOCHS: tuple[tuple[str, str, float, float, str], ...] = (
    ("Holocene", "홀로세", 0.0, 0.0117, "#fef2e0"),
    ("Pleistocene", "플라이스토세", 0.0117, 2.58, "#fff2ae"),
    ("Pliocene", "플라이오세", 2.58, 5.333, "#ffff99"),
    ("Miocene", "마이오세", 5.333, 23.03, "#ffff00"),
    ("Oligocene", "올리고세", 23.03, 33.9, "#fec07a"),
    ("Eocene", "에오세", 33.9, 56.0, "#fdb46c"),
    ("Paleocene", "팔레오세", 56.0, 66.0, "#fda75f"),
)
STAGES: tuple[tuple[str, str, float, float, str], ...] = (
    ("Meghalayan", "메갈라야절", 0.0, 0.0042, "#fdf9ee"),
    ("Northgrippian", "노스그리피절", 0.0042, 0.0082, "#fdf7e7"),
    ("Greenlandian", "그린란드절", 0.0082, 0.0117, "#fdf5e0"),
    # 후기 플라이스토세는 절 이름이 아직 없다(ICS 가 `Upper` 로 둔다)
    ("Upper", "후기 플라이스토세", 0.0117, 0.129, "#fff2d3"),
    ("Chibanian", "지바절", 0.129, 0.774, "#fff2c7"),
    ("Calabrian", "칼라브리아절", 0.774, 1.8, "#fff2ba"),
    ("Gelasian", "젤라절", 1.8, 2.58, "#ffedb3"),
    ("Piacenzian", "피아첸차절", 2.58, 3.6, "#ffffbf"),
    ("Zanclean", "잔클레절", 3.6, 5.333, "#ffffb3"),
    ("Messinian", "메시나절", 5.333, 7.246, "#ffff73"),
    ("Tortonian", "토르토나절", 7.246, 11.63, "#ffff66"),
    ("Serravallian", "세라발레절", 11.63, 13.82, "#ffff59"),
    ("Langhian", "랑게절", 13.82, 15.98, "#ffff4d"),
    ("Burdigalian", "부르디갈라절", 15.98, 20.44, "#ffff41"),
    ("Aquitanian", "아키텐절", 20.44, 23.03, "#ffff33"),
    ("Chattian", "샤트절", 23.03, 27.82, "#fee6aa"),
    ("Rupelian", "루펠절", 27.82, 33.9, "#fed99a"),
    ("Priabonian", "프리아보나절", 33.9, 37.71, "#fdcda1"),
    ("Bartonian", "바턴절", 37.71, 41.2, "#fdc091"),
    ("Lutetian", "루테티아절", 41.2, 47.8, "#fcb482"),
    ("Ypresian", "이프르절", 47.8, 56.0, "#fca773"),
    ("Thanetian", "타네트절", 56.0, 59.2, "#fdbf6f"),
    ("Selandian", "셀란절", 59.2, 61.6, "#febf65"),
    ("Danian", "다니아절", 61.6, 66.0, "#fdb462"),
)
COLUMNS = (("period", "기", PERIODS), ("epoch", "세", EPOCHS), ("stage", "절", STAGES))
MAX_MA = 66.0


def bands(max_ma: float) -> list[dict]:
    """`max_ma` 까지의 기·세·절 — 축에 걸리는 것만, 끝은 축에서 자른다."""
    out = []
    for col, _label, rows in COLUMNS:
        for name, ko, top, base, color in rows:
            if top >= max_ma:
                break
            out.append({"col": col, "name": name, "ko": ko, "color": color,
                        "top_ma": top, "base_ma": min(base, max_ma),
                        # 축에서 자르기 전의 하한 — 띠를 눌러 그 절로 좁힐 때의 값(210)
                        "full_base_ma": base, "cut": base > max_ma})
    return out


def label_for(name: str, height_px: float, char_px: float = 5.2, pad: float = 6.0) -> str:
    """세로로 눕힌 글자가 띠 안에 드는가 — 전체 이름 → 세 글자 약자 → 빈 칸.
    빈 칸이어도 마우스 설명(`<title>`)에는 전체 이름이 있다."""
    if len(name) * char_px + pad <= height_px:
        return name
    short = name[:3] + "."
    if len(short) * char_px + pad <= height_px:
        return short
    return ""
