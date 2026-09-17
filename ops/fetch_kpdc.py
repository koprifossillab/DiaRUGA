#!/usr/bin/env python3
"""KPDC 에서 코어 지점의 메타데이터를 긁어 지점에 얹는다 (197).

    deploy/host/dbsync.sh fetch_kpdc.py
    deploy/host/dbrun.sh  fetch_kpdc.py --slide rs23_gc03_71cm     # 폴러가 부르는 꼴
    deploy/host/dbrun.sh  fetch_kpdc.py --missing --dry-run          # 아직 없는 지점 전부
    deploy/host/dbrun.sh  fetch_kpdc.py --locality RS21-GC02 --force # 있어도 다시

`deploy/poll_nas.sh` 가 그룹핑 뒤에 `--slide` 로 한 번 부른다 — 새 슬라이드의
지점이 KPDC 항목을 아직 안 갖고 있을 때만 긁는다. **실패해도 폴러는 안
멈춘다**(반입이 서는 조건이 아니다). 항목이 없거나(항차 뒤 반년쯤 지나야
등록된다) 사내망이 막혀 못 긁은 지점은 `--missing` 으로 나중에 다시 돈다.

**빈 칸만 채운다.** 사람이 넣은 좌표·수심·채취일은 안 덮는다 — 규칙은
`viewer/kpdc.py` 머리말. `--force` 도 그 규칙 안에서 다시 긁는 것이다(KPDC 쪽
항목이 갱신됐을 때 `kpdc_meta` 를 새로 받는 용도).

`dbtool` 문으로 돈다 — 뷰어 이미지라 Django 가 있고 torch 가 없다.
"""
import argparse
import os
import sys
from pathlib import Path

import django

# `ops/check_db.py` 와 같은 머리다. 컨테이너 안에서는 코드가 `/app` 이라
# `DIARUGA_APP` 을 봐야 한다.
APP = Path(os.environ.get("DIARUGA_APP")
          or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(APP / "web"))
sys.path.append(str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diarugaweb.settings")
django.setup()

from viewer import kpdc                                             # noqa: E402
from viewer.models import Locality, Slide                           # noqa: E402


def _targets(args):
    qs = Locality.objects.select_related("site").filter(kind="core")
    if args.slide:
        s = Slide.objects.filter(slug=args.slide).select_related(
            "sample__locality__site").first()
        if s is None:
            raise SystemExit(f"모르는 슬라이드: {args.slide}")
        if s.sample is None:
            print(f"  {args.slide}: 소속이 없다 — 지점을 모른다")
            return []
        loc = s.sample.locality
        if loc.kind != "core":
            print(f"  {loc}: 노두다 — KPDC 는 코어만 본다")
            return []
        return [loc]
    if args.locality:
        out = []
        for name in args.locality:
            site, _, code = name.partition("-")
            loc = qs.filter(site__code=site, code=code).first()
            if loc is None:
                raise SystemExit(f"모르는 지점: {name}")
            out.append(loc)
        return out
    if args.missing:
        return list(qs.filter(kpdc_id=""))
    return list(qs)                                                 # --all


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slide", help="이 슬라이드의 지점 하나")
    g.add_argument("--locality", nargs="+", metavar="SITE-LOC",
                   help="지점을 이름으로 (RS21-GC02 …)")
    g.add_argument("--missing", action="store_true",
                   help="kpdc_id 가 빈 코어 지점 전부")
    g.add_argument("--all", action="store_true", help="코어 지점 전부")
    ap.add_argument("--force", action="store_true",
                    help="이미 kpdc_id 가 있어도 다시 긁는다")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않는다")
    args = ap.parse_args()

    n_ok = n_skip = n_none = n_fail = 0
    for loc in _targets(args):
        name = f"{loc.site.code}-{loc.code}"
        if loc.kpdc_id and not args.force:
            print(f"  {name}: 이미 {loc.kpdc_id} — 건너뛴다 (--force 로 다시)")
            n_skip += 1
            continue
        try:
            meta = kpdc.scrape(name)
        except kpdc.KpdcError as e:
            print(f"  {name}: 못 긁었다 — {e}")
            n_fail += 1
            continue
        if meta is None:
            print(f"  {name}: KPDC 에 항목이 없다")
            n_none += 1
            continue
        changed = kpdc.apply(loc, meta)
        filled = [c for c in changed if not c.startswith("kpdc_")]
        print(f"  {name}: {meta['entry_id']} · {meta['title']}"
              f" · 첨부 {len(meta['files'])}개"
              + (f" · 채움 {', '.join(filled)}" if filled else " · 채울 빈 칸 없음")
              + (" (dry-run)" if args.dry_run else ""))
        if not args.dry_run:
            loc.save(update_fields=changed)
        n_ok += 1
    print(f"긁음 {n_ok} · 건너뜀 {n_skip} · 항목 없음 {n_none} · 실패 {n_fail}")
    # 항목이 없는 것은 실패가 아니다 — 아직 등록 전일 수 있다
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
