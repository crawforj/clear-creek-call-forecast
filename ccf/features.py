"""Predictors known on an issue date. The one shipped here is snowpack:
the three SNOTEL sites that drain to Clear Creek, from the NRCS AWDB
service (no key). `data/snotel_daily_swe.csv` is the committed copy;
`scripts/fetch_snotel.py` refreshes it.

Add a predictor by adding a function that returns a DataFrame indexed by
season_year with one or more numeric columns, and never by reading
anything dated after the issue date. The hindcast harness only passes a
model the seasons it is allowed to see.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
SNOTEL_CSV = REPO / "data" / "snotel_daily_swe.csv"

SITES = {
    "602:CO:SNTL": "Loveland Basin (11,410 ft)",
    "335:CO:SNTL": "Berthoud Summit (11,300 ft)",
    "505:CO:SNTL": "Grizzly Peak (11,110 ft)",
}


def snotel_daily(path: Path = SNOTEL_CSV) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"])
    return d


def swe_on(month: int, day: int, path: Path = SNOTEL_CSV) -> pd.DataFrame:
    """Per season_year: SWE (inches) at each site on month/day, the mean
    across sites, and that mean as a percent of its median over the years
    with all three sites reporting."""
    d = snotel_daily(path)
    d = d[(d["date"].dt.month == month) & (d["date"].dt.day == day)].copy()
    d["season_year"] = d["date"].dt.year
    wide = d.pivot_table(index="season_year", columns="site", values="swe_in", aggfunc="first")
    wide["swe_mean_in"] = wide[[c for c in wide.columns if c in SITES]].mean(axis=1, skipna=False)
    med = wide["swe_mean_in"].median()
    wide["swe_pct_median"] = 100.0 * wide["swe_mean_in"] / med if med and med > 0 else float("nan")
    return wide


def april1_swe(path: Path = SNOTEL_CSV) -> pd.DataFrame:
    return swe_on(4, 1, path)


def peak_swe(path: Path = SNOTEL_CSV) -> pd.DataFrame:
    """Per season_year: the season's peak of the three-site mean SWE and the
    day it fell on. NOT known on April 1 -- usable only for issue dates after
    melt-out, or as a what-if."""
    d = snotel_daily(path)
    d["season_year"] = d["date"].dt.year
    m = d.groupby(["season_year", "date"])["swe_in"].mean().reset_index()
    idx = m.groupby("season_year")["swe_in"].idxmax()
    peak = m.loc[idx].set_index("season_year")
    return peak.rename(columns={"swe_in": "peak_swe_mean_in", "date": "peak_date"})
