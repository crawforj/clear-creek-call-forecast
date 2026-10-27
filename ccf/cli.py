"""Command line.

    ccf fetch                         # download the truth table into the cache
    ccf summary                       # seasons, base rates, first-call weeks
    ccf hindcast [--model NAME] [--n-boot N] [--out dir]
    ccf emit --model NAME --version vX.Y.Z [--authors "A, B"] [--out dir]
    ccf validate FILE                 # schema + the site's rules

`--truth DIR` on any command reads a local copy of the release instead of
fetching (a test fixture, or a downloaded folder).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from . import SLUG, __version__, data, emit, features as feat, hindcast, truth
from .models import REGISTRY, Climatology


def _truth(args):
    if args.truth:
        return data.load_local_truth(Path(args.truth))
    return data.truth_table()


def _features():
    try:
        return {"april1_swe": feat.april1_swe()}
    except Exception as e:  # noqa: BLE001
        print(f"[ccf] features unavailable: {e}", file=sys.stderr)
        return {}


def _model(name: str):
    try:
        return REGISTRY[name]
    except KeyError:
        raise SystemExit(f"unknown model {name!r}; known: {', '.join(REGISTRY)}")


def cmd_fetch(args):
    m, weekly, daily = data.truth_table()
    print(f"truth table for {m.get('stream')} built {m.get('built_at')}, data through {m.get('data_through')}, "
          f"{len(weekly):,} season-weeks, {len(daily):,} days, sha {data.truth_sha(m)[:12]}...")


def cmd_summary(args):
    m, weekly, _ = _truth(args)
    bands = [int(b) for b in m["bands"]]
    s = truth.season_summary(weekly)
    print(s.to_string(index=False))
    u = truth.outcome_table(weekly, bands)
    print("\nbase rate per band over usable seasons (share of season-weeks with the cutline at or senior to the band):")
    for b in bands:
        print(f"  <= {b:>6,}: {u[f'le_{b}'].mean():.3f}")
    print(f"  free river: {u['free'].mean():.3f}")


def cmd_hindcast(args):
    m, weekly, _ = _truth(args)
    bands = [int(b) for b in m["bands"]]
    cls = _model(args.model)
    sk = hindcast.run(weekly, bands, cls, features=_features() if cls.requires else None, n_boot=args.n_boot)
    print(sk["verdict"])
    if args.out:
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        (out / f"hindcast_{args.model}.json").write_text(json.dumps(sk, indent=1), encoding="utf-8")
        (out / f"hindcast_{args.model}.md").write_text(hindcast.report_markdown(args.model, sk, bands), encoding="utf-8")
        print(f"wrote {out / f'hindcast_{args.model}.md'}")
    return 0 if sk.get("n_pairs") else 1


def cmd_emit(args):
    m, weekly, _ = _truth(args)
    bands = [int(b) for b in m["bands"]]
    cls = _model(args.model)
    feats = _features() if cls.requires else None
    sk = hindcast.run(weekly, bands, cls, features=feats, n_boot=args.n_boot)
    today = _dt.date.fromisoformat(args.today) if args.today else _dt.date.today()
    season = args.season or emit.season_for(today, m["season_start"], int(m.get("season_weeks", 31)))
    table = truth.outcome_table(weekly, bands)
    model = cls()
    model.fit(table, bands, feats)
    pred = model.predict(season, bands, list(range(truth.SEASON_WEEKS)), feats)
    authors = [a.strip() for a in (args.authors or "").split(",") if a.strip()]
    payload = emit.build_payload(model, pred, m, sk, args.version, authors=authors, today=today)
    problems = emit.validate(payload)
    files = emit.write_release(payload, hindcast.report_markdown(args.model, sk, bands), Path(args.out))
    for p in files:
        print(f"wrote {p}")
    if problems:
        print("The site would REFUSE this file:")
        for p in problems:
            print(f"  - {p}")
        return 2 if args.strict else 0
    print("validates: the site's schema and gate rules pass on the stated hindcast")
    return 0


def cmd_validate(args):
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    problems = emit.validate(payload)
    for p in problems:
        print(f"- {p}")
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ccf", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"ccf {__version__} ({SLUG})")
    ap.add_argument("--truth", default=None, help="local folder holding manifest.json + call_truth_weekly.parquet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    h = sub.add_parser("hindcast"); h.set_defaults(fn=cmd_hindcast)
    h.add_argument("--model", default="climatology"); h.add_argument("--n-boot", type=int, default=2000); h.add_argument("--out", default=None)
    e = sub.add_parser("emit"); e.set_defaults(fn=cmd_emit)
    e.add_argument("--model", required=True); e.add_argument("--version", required=True)
    e.add_argument("--authors", default=None); e.add_argument("--out", default="dist")
    e.add_argument("--n-boot", type=int, default=2000); e.add_argument("--season", type=int, default=None)
    e.add_argument("--today", default=None); e.add_argument("--strict", action="store_true", help="exit 2 when the site would refuse the file")
    v = sub.add_parser("validate"); v.set_defaults(fn=cmd_validate); v.add_argument("file")
    args = ap.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
