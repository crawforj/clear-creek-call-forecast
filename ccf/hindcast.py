"""The leave-one-season-out hindcast: every usable season forecast from the
other seasons only, scored by Brier against the two baselines by the same
rules the site uses, with a season-resampled bootstrap interval.

This is the receipt a model PR must carry, and the `skill` block the
site's gate reads. The scoring functions mirror hydrohistorian's skill.py
(Brier score, Brier skill score, season-block bootstrap) so a number
computed here means the same thing on the site.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Sequence

import pandas as pd

from .models import Climatology, Model, Persistence
from .truth import outcome_table, usable_seasons, SEASON_WEEKS


# ---------------------------------------------------------------------------
# Proper scores (same definitions as the site)


def brier(forecasts: Sequence[float], outcomes: Sequence[bool]) -> float | None:
    pairs = [(float(f), bool(o)) for f, o in zip(forecasts, outcomes) if f is not None and o is not None]
    if not pairs:
        return None
    return sum((f - (1.0 if o else 0.0)) ** 2 for f, o in pairs) / len(pairs)


def brier_skill(forecasts, reference, outcomes) -> float | None:
    ours, theirs = brier(forecasts, outcomes), brier(reference, outcomes)
    if ours is None or theirs is None:
        return None
    if theirs == 0:
        return 0.0 if ours == 0 else float("-inf")
    return 1.0 - ours / theirs


def bootstrap_skill(forecasts, reference, outcomes, seasons, n_boot: int = 2000, seed: int = 0,
                    alpha: float = 0.05) -> dict:
    """Resample whole seasons (weeks within a season are dependent)."""
    by: dict = defaultdict(list)
    for f, r, o, s in zip(forecasts, reference, outcomes, seasons):
        if f is None or r is None or o is None:
            continue
        by[s].append((float(f), float(r), bool(o)))
    labels = sorted(by)
    point = brier_skill(forecasts, reference, outcomes)
    if len(labels) < 2:
        return {"skill": point, "lo": None, "hi": None, "n_seasons": len(labels), "n_boot": 0}
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        pick = [labels[rng.randrange(len(labels))] for _ in labels]
        f, r, o = [], [], []
        for s in pick:
            for a, b, c in by[s]:
                f.append(a); r.append(b); o.append(c)
        v = brier_skill(f, r, o)
        if v is not None and math.isfinite(v):
            draws.append(v)
    if not draws:
        return {"skill": point, "lo": None, "hi": None, "n_seasons": len(labels), "n_boot": 0}
    draws.sort()
    lo = draws[int((alpha / 2) * len(draws))]
    hi = draws[min(len(draws) - 1, int((1 - alpha / 2) * len(draws)))]
    return {"skill": point, "lo": lo, "hi": hi, "n_seasons": len(labels), "n_boot": len(draws),
            "beats_reference": bool(lo > 0)}


def reliability(forecasts, outcomes, n_bins: int = 5) -> list[dict]:
    bins: dict[int, list] = defaultdict(list)
    for f, o in zip(forecasts, outcomes):
        if f is None:
            continue
        bins[min(int(float(f) * n_bins), n_bins - 1)].append((float(f), bool(o)))
    out = []
    for i in range(n_bins):
        g = bins.get(i, [])
        out.append({"bin": f"{i / n_bins:.1f}-{(i + 1) / n_bins:.1f}", "n": len(g),
                    "mean_forecast": round(sum(f for f, _ in g) / len(g), 3) if g else None,
                    "observed": round(sum(1 for _, o in g if o) / len(g), 3) if g else None})
    return out


# ---------------------------------------------------------------------------
# The harness


def _restrict(features: dict[str, pd.DataFrame] | None, allowed: set[int]) -> dict[str, pd.DataFrame] | None:
    """A model fitting on seasons S may only see feature rows for S. (It may
    see the TARGET season's own features at predict time -- that is the
    issue-date information -- which the harness passes separately.)"""
    if not features:
        return features
    return {k: v[v.index.isin(allowed)] for k, v in features.items()}


def _predict_season(model_cls, kwargs: dict, train: pd.DataFrame, y: int, bands: list[int],
                    weeks: list[int], features) -> dict[int, dict[str, float]]:
    m = model_cls(**kwargs) if kwargs else model_cls()
    m.fit(train, bands, _restrict(features, set(train["season_year"])))
    allowed = set(train["season_year"]) | {y}
    return m.predict(y, bands, weeks, _restrict(features, allowed)).probs


def run(weekly: pd.DataFrame, bands: list[int], model_cls: type[Model], model_kwargs: dict | None = None,
        features: dict[str, pd.DataFrame] | None = None, n_boot: int = 2000, seed: int = 0) -> dict:
    """Leave-one-season-out over every usable season. Returns the skill
    block the site's gate reads plus per-band and per-season detail."""
    table = outcome_table(weekly, bands)
    years = usable_seasons(weekly)
    weeks = list(range(SEASON_WEEKS))
    rows = []  # (season, week, band, f, clim, pers, outcome)
    per_season: dict[int, dict] = {}
    for y in years:
        train = table[table["season_year"] != y]
        truth = table[table["season_year"] == y].set_index("week_index")
        try:
            ours = _predict_season(model_cls, model_kwargs or {}, train, y, bands, weeks, features)
        except Exception as e:  # a model that cannot forecast a season forfeits it, visibly
            per_season[y] = {"error": f"{type(e).__name__}: {e}"}
            continue
        clim = _predict_season(Climatology, {}, train, y, bands, weeks, None)
        pers = _predict_season(Persistence, {}, train, y, bands, weeks, None)
        n = 0
        for w in weeks:
            if w not in truth.index or w not in ours or w not in clim:
                continue
            for b in bands:
                k = str(int(b))
                pf, pc = ours[w].get(k), clim[w].get(k)
                pp = pers.get(w, {}).get(k)
                if pf is None or pc is None or pp is None:
                    continue
                rows.append((y, w, b, float(pf), float(pc), float(pp), bool(truth.loc[w, f"le_{int(b)}"])))
                n += 1
        per_season[y] = {"n_pairs": n}
    if not rows:
        return {"method": "leave-one-season-out", "n_seasons": 0, "n_pairs": 0,
                "bss_vs_climatology": None, "bss_vs_persistence": None,
                "bootstrap_ci_bss_clim": [None, None], "per_season": per_season,
                "verdict": "nothing could be scored"}
    f = [r[3] for r in rows]; c = [r[4] for r in rows]; p = [r[5] for r in rows]
    o = [r[6] for r in rows]; s = [r[0] for r in rows]
    bc = bootstrap_skill(f, c, o, s, n_boot=n_boot, seed=seed)
    bp = bootstrap_skill(f, p, o, s, n_boot=n_boot, seed=seed)
    per_band = {}
    for b in bands:
        sub = [r for r in rows if r[2] == b]
        fb = [r[3] for r in sub]; cb = [r[4] for r in sub]; pb = [r[5] for r in sub]; ob = [r[6] for r in sub]
        per_band[str(int(b))] = {"n": len(sub), "brier": _r(brier(fb, ob)),
                                 "bss_vs_climatology": _r(brier_skill(fb, cb, ob)),
                                 "bss_vs_persistence": _r(brier_skill(fb, pb, ob)),
                                 "base_rate": _r(sum(ob) / len(ob)) if ob else None}
    for y in years:
        sub = [r for r in rows if r[0] == y]
        if sub and "error" not in per_season.get(y, {}):
            per_season[y].update({"brier": _r(brier([r[3] for r in sub], [r[6] for r in sub])),
                                  "bss_vs_climatology": _r(brier_skill([r[3] for r in sub], [r[4] for r in sub], [r[6] for r in sub]))})
    skill_block = {
        "method": f"leave-one-season-out hindcast over {len(years)} usable seasons ({years[0]}-{years[-1]})",
        "n_seasons": int(bc["n_seasons"]), "n_pairs": len(rows),
        "brier": _r(brier(f, o)), "brier_climatology": _r(brier(c, o)), "brier_persistence": _r(brier(p, o)),
        "bss_vs_climatology": _r(bc["skill"]), "bss_vs_persistence": _r(bp["skill"]),
        "bootstrap_ci_bss_clim": [_r(bc["lo"]), _r(bc["hi"])],
        "bootstrap_ci_bss_pers": [_r(bp["lo"]), _r(bp["hi"])],
        "reliability": _r(_reliability_term(f, o)),
        "reliability_table": reliability(f, o),
        "per_band": per_band, "per_season": per_season,
    }
    skill_block["passes_gate"] = bool(
        (skill_block["bss_vs_climatology"] or 0) > 0 and (skill_block["bss_vs_persistence"] or 0) > 0
        and (skill_block["bootstrap_ci_bss_clim"][0] or 0) > 0)
    skill_block["verdict"] = _verdict(skill_block)
    return skill_block


def _reliability_term(forecasts, outcomes, n_bins: int = 10) -> float | None:
    """The reliability term of the Murphy decomposition: mean squared gap
    between forecast and observed frequency per bin. 0 = perfectly calibrated."""
    bins: dict[int, list] = defaultdict(list)
    for f, o in zip(forecasts, outcomes):
        bins[min(int(float(f) * n_bins), n_bins - 1)].append((float(f), bool(o)))
    n = sum(len(g) for g in bins.values())
    if not n:
        return None
    total = 0.0
    for g in bins.values():
        fm = sum(f for f, _ in g) / len(g)
        om = sum(1 for _, o in g if o) / len(g)
        total += len(g) * (fm - om) ** 2
    return total / n


def _verdict(sk: dict) -> str:
    bc, lo, hi = sk["bss_vs_climatology"], sk["bootstrap_ci_bss_clim"][0], sk["bootstrap_ci_bss_clim"][1]
    bp = sk["bss_vs_persistence"]
    if bc is None:
        return "Nothing could be scored."
    if sk["passes_gate"]:
        return (f"PASSES the site's gate: skill {bc:+.3f} vs climatology (95% CI {lo:+.3f} to {hi:+.3f}) "
                f"and {bp:+.3f} vs persistence over {sk['n_seasons']} seasons.")
    parts = []
    if not bc > 0:
        parts.append(f"not better than climatology ({bc:+.3f})")
    elif lo is None or not lo > 0:
        parts.append(f"better than climatology ({bc:+.3f}) but the interval straddles zero ({lo} to {hi})")
    if bp is not None and not bp > 0:
        parts.append(f"not better than persistence ({bp:+.3f})")
    return "Does NOT pass the gate: " + "; ".join(parts) + f" over {sk['n_seasons']} seasons."


def _r(x, nd: int = 4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    return round(float(x), nd)


def report_markdown(name: str, sk: dict, bands: list[int]) -> str:
    lines = [f"# Hindcast report: {name}", "", f"{sk['method']}.", "", f"**{sk['verdict']}**", "",
             "| | Brier | skill vs climatology | skill vs persistence |", "|---|---|---|---|",
             f"| all bands | {sk['brier']} | {sk['bss_vs_climatology']} (CI {sk['bootstrap_ci_bss_clim'][0]} to {sk['bootstrap_ci_bss_clim'][1]}) | {sk['bss_vs_persistence']} (CI {sk['bootstrap_ci_bss_pers'][0]} to {sk['bootstrap_ci_bss_pers'][1]}) |"]
    for b in bands:
        pb = sk["per_band"].get(str(int(b))) or {}
        lines.append(f"| band <= {b:,} (base rate {pb.get('base_rate')}) | {pb.get('brier')} | {pb.get('bss_vs_climatology')} | {pb.get('bss_vs_persistence')} |")
    lines += ["", f"Reliability term {sk['reliability']} (0 = calibrated). Climatology's own Brier: {sk['brier_climatology']}; persistence's: {sk['brier_persistence']}.", "",
              "| forecast bin | n | mean forecast | observed |", "|---|---|---|---|"]
    lines += [f"| {r['bin']} | {r['n']} | {r['mean_forecast']} | {r['observed']} |" for r in sk["reliability_table"]]
    lines += ["", "| season | pairs | Brier | skill vs climatology |", "|---|---|---|---|"]
    for y, r in sorted(sk["per_season"].items()):
        lines.append(f"| {y} | {r.get('n_pairs', '')} | {r.get('brier', '')} | {r.get('bss_vs_climatology', r.get('error', ''))} |")
    return "\n".join(lines) + "\n"
