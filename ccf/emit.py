"""Write the forecast file the site ingests, in the shape the site's schema
demands, with the hindcast's skill block inside it. Validates against
schema/call_forecast.schema.json (jsonschema) and against the site's own
structural rules re-implemented here (so CI fails before the site would
refuse).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
from pathlib import Path

from . import ASSET_NAME, SLUG
from .models import Model
from .truth import SEASON_WEEKS

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "schema" / "call_forecast.schema.json"


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=10, cwd=REPO).stdout.strip() or None
    except Exception:
        return None


def season_for(today: _dt.date, season_start_mmdd: str = "04-01", season_weeks: int = SEASON_WEEKS) -> int:
    mm, dd = (int(x) for x in season_start_mmdd.split("-"))
    start = _dt.date(today.year, mm, dd)
    end = start + _dt.timedelta(weeks=season_weeks)
    return today.year + 1 if today >= end else today.year


def build_payload(model: Model, prediction, manifest: dict, skill: dict, version: str,
                  authors: list[str] | None = None, data_through: str | None = None,
                  caveats: list[str] | None = None, today: _dt.date | None = None) -> dict:
    today = today or _dt.date.today()
    bands = [int(b) for b in manifest["bands"]]
    start = _dt.date.fromisoformat(f"{prediction.season_year}-{manifest['season_start']}")
    weeks = []
    for w in sorted(prediction.probs):
        probs = {str(b): _clip(prediction.probs[w].get(str(b))) for b in bands}
        if any(v is None for v in probs.values()):
            continue
        # enforce monotone across bands (a cutline at or senior to a senior band is at or senior to a junior one)
        running = 0.0
        for b in bands:
            running = max(running, probs[str(b)])
            probs[str(b)] = round(running, 4)
        pf = prediction.p_free.get(w)
        pf = None if pf is None else round(min(_clip(pf), 1.0 - probs[str(bands[-1])]), 4)
        weeks.append({"week_index": int(w), "week_start": (start + _dt.timedelta(weeks=int(w))).isoformat(),
                      "p_controlling_le": probs, "p_free_river": pf})
    sk = {k: v for k, v in skill.items() if k not in ("per_season", "reliability_table")}
    return {
        "schema_version": "1.0", "basin": manifest.get("slug", SLUG),
        "model": {"name": model.name, "version": version, "repo": "crawforj/clear-creek-call-forecast",
                  "git_sha": git_sha(), "authors": authors or []},
        "issued_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "data_through": data_through or manifest["data_through"],
        "truth_table_sha256": next((f["sha256"] for f in manifest["files"] if f["path"] == "call_truth_weekly.parquet"), ""),
        "season_year": int(prediction.season_year), "season_start": start.isoformat(),
        "horizon_weeks": len(weeks), "bands": bands, "weeks": weeks,
        "skill": sk,
        "caveats": list(caveats or manifest.get("caveats") or []),
    }


def _clip(v):
    if v is None:
        return None
    return max(0.0, min(1.0, float(v)))


def validate(payload: dict) -> list[str]:
    """Schema plus the site's structural rules. Empty = fine."""
    problems: list[str] = []
    try:
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        for err in sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=str):
            problems.append(f"schema: {err.message}")
    except ImportError:
        problems.append("jsonschema not installed; schema not checked")
    bands = payload.get("bands") or []
    for w in payload.get("weeks") or []:
        probs = w.get("p_controlling_le") or {}
        if set(probs) != {str(b) for b in bands}:
            problems.append(f"week {w.get('week_index')}: p_controlling_le keys != bands")
            continue
        prev = -1.0
        for b in bands:
            if probs[str(b)] + 1e-9 < prev:
                problems.append(f"week {w.get('week_index')}: probabilities decrease at band {b}")
                break
            prev = probs[str(b)]
        pf = w.get("p_free_river")
        if pf is not None and pf > 1 - probs[str(bands[-1])] + 1e-9:
            problems.append(f"week {w.get('week_index')}: p_free_river exceeds 1 - p(most junior band)")
    sk = payload.get("skill") or {}
    if not (sk.get("bss_vs_climatology") or 0) > 0:
        problems.append("gate: bss_vs_climatology is not > 0 (the site will refuse this)")
    if not (sk.get("bss_vs_persistence") or 0) > 0:
        problems.append("gate: bss_vs_persistence is not > 0 (the site will refuse this)")
    ci = sk.get("bootstrap_ci_bss_clim") or [None, None]
    if ci[0] is None or not ci[0] > 0:
        problems.append("gate: bootstrap lower bound vs climatology is not > 0 (the site will refuse this)")
    return problems


def write_release(payload: dict, report_md: str, out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    asset = out_dir / ASSET_NAME
    asset.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    report = out_dir / "hindcast_report.md"
    report.write_text(report_md, encoding="utf-8")
    sums = out_dir / "sha256sums.txt"
    lines = []
    for p in (asset, report):
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [asset, report, sums]
