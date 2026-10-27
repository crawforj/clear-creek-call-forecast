"""The target, read exactly as the site defines it. Nothing here recomputes
a label; it only reads the published table and turns it into outcomes.

A forecast states, per season week and per band B, the probability that
``controlling_admin_combined <= B`` -- that the most senior applied call
sits at or senior to admin number B, so every right junior to B on the
stream below the calling point is out of priority. Free river is "no" for
every band.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEASON_WEEKS = 31  # week 0 begins April 1


def outcome(combined, band: int) -> bool:
    try:
        return bool(not pd.isna(combined) and float(combined) <= float(band))
    except (TypeError, ValueError):
        return False


def usable_seasons(weekly: pd.DataFrame) -> list[int]:
    u = weekly[weekly["usable"].astype(bool)]
    return sorted(int(y) for y in set(u["season_year"]))


def outcome_table(weekly: pd.DataFrame, bands: list[int]) -> pd.DataFrame:
    """One row per (season_year, week_index) of a usable season, one boolean
    column per band named 'le_<band>', plus 'free'."""
    u = weekly[weekly["usable"].astype(bool)].copy()
    for b in bands:
        u[f"le_{int(b)}"] = [outcome(c, b) for c in u["controlling_admin_combined"]]
    u["free"] = u["is_free_river"].astype(bool)
    return u[["season_year", "week_index", "week_start"] + [f"le_{int(b)}" for b in bands] + ["free"]].reset_index(drop=True)


def season_summary(weekly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y, g in weekly.groupby("season_year"):
        comb = g["controlling_admin_combined"].dropna()
        called = g[~g["is_free_river"].astype(bool)]
        rows.append({"season_year": int(y), "usable": bool(g["usable"].all()),
                     "weeks_under_call": int(len(called)),
                     "first_call_week": int(called["week_index"].min()) if len(called) else None,
                     "season_min_admin": float(comb.min()) if len(comb) else np.nan})
    return pd.DataFrame(rows)
