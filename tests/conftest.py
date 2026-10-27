"""A synthetic truth table in the exact shape hydrohistorian publishes, so
the harness, the emitter and the CLI are tested without the network."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BANDS = [10000, 20000, 30000, 40000, 60000]
WEEKS = 31


def make_weekly(seasons: dict[int, dict[int, float | None]], usable: dict[int, bool] | None = None) -> pd.DataFrame:
    rows = []
    for y, weeks in seasons.items():
        first = pd.Timestamp(f"{y}-04-01")
        for w in range(WEEKS):
            c = weeks.get(w)
            rows.append({"season_year": y, "week_index": w,
                         "week_start": (first + pd.Timedelta(weeks=w)).strftime("%Y-%m-%d"), "days": 7,
                         "controlling_admin_stream": c, "controlling_admin_mainstem": np.nan,
                         "controlling_admin_combined": np.nan if c is None else float(c),
                         "mainstem_unjudged_admin": np.nan, "days_under_call": 0 if c is None else 7,
                         "is_free_river": c is None, "season_complete": True,
                         "usable": (usable or {}).get(y, True), "label_basis": "stream-identity"})
    return pd.DataFrame(rows)


def snowy_seasons(n: int = 12, start: int = 2010) -> tuple[dict, pd.DataFrame]:
    """Seasons whose call pattern follows a (fake) April-1 SWE: low snow ->
    an early, deep call; high snow -> a late, shallow one. Returns the
    seasons dict and a matching april1_swe feature frame."""
    out, swe = {}, []
    for i in range(n):
        y = start + i
        pct = 60 + (i * 37) % 90  # 60..149, scrambled
        swe.append({"season_year": y, "swe_pct_median": float(pct), "swe_mean_in": pct / 10})
        weeks = {}
        onset = 6 if pct < 90 else (10 if pct < 120 else 14)
        depth = 8000.0 if pct < 90 else (15000.0 if pct < 120 else 35000.0)
        for w in range(onset, 26):
            weeks[w] = depth
        out[y] = weeks
    return out, pd.DataFrame(swe).set_index("season_year")


@pytest.fixture
def truth_dir(tmp_path) -> Path:
    seasons, _ = snowy_seasons()
    weekly = make_weekly(seasons)
    d = tmp_path / "truth"
    d.mkdir()
    weekly.to_parquet(d / "call_truth_weekly.parquet", index=False)
    sha = hashlib.sha256((d / "call_truth_weekly.parquet").read_bytes()).hexdigest()
    m = {"slug": "d1_wd7_clear_creek", "basin": "clear_creek", "stream": "CLEAR CREEK", "mainstem": "SOUTH PLATTE RIVER",
         "bands": BANDS, "season_start": "04-01", "season_weeks": WEEKS, "week_index_base": 0,
         "data_through": "2026-10-31", "built_at": "2026-11-01T06:40:00-06:00", "first_stream_call_year": 2010,
         "caveats": ["Paper water."], "files": [{"path": "call_truth_weekly.parquet", "sha256": sha}]}
    (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return d


@pytest.fixture
def swe_features() -> dict[str, pd.DataFrame]:
    _, f = snowy_seasons()
    return {"april1_swe": f}
