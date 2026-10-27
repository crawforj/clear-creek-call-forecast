"""Baseline 3: snow analogs. The k training seasons whose April 1 SWE
(three-site mean, percent of median) is nearest the target season's, with
each week's probability the share of those analogs in which the cutline
sat at or senior to the band.

This is the ESP-style analog idea hydrohistorian.com already uses for its
curtailment outlook (there, on streamflow state at the as-of date rather
than snowpack), ported here as the reference a snow-driven model should
first beat. Uniform weights on purpose: learned analog weights are an
obvious next step and belong in a contributed model.
"""
from __future__ import annotations

import pandas as pd

from .base import Model, Prediction


class SnowAnalog(Model):
    name = "snow-analog"
    version = "1.0"
    requires = ("april1_swe",)

    def __init__(self, k: int = 5, column: str = "swe_pct_median"):
        self.k = int(k)
        self.column = column

    def fit(self, train: pd.DataFrame, bands: list[int], features=None) -> "SnowAnalog":
        self._train = train
        f = (features or {}).get("april1_swe")
        if f is None:
            raise ValueError("snow-analog needs features['april1_swe'] (ccf.features.april1_swe)")
        self._state = f[self.column].dropna()
        return self

    def predict(self, season_year: int, bands: list[int], weeks: list[int], features=None) -> Prediction:
        f = (features or {}).get("april1_swe")
        if f is None or season_year not in f.index or pd.isna(f.loc[season_year, self.column]):
            return Prediction(season_year, {}, {}, {"reason": f"no {self.column} for {season_year}"})
        target = float(f.loc[season_year, self.column])
        candidates = self._state[self._state.index.isin(set(self._train["season_year"]))]
        candidates = candidates[candidates.index != season_year]
        if candidates.empty:
            return Prediction(season_year, {}, {}, {"reason": "no analog candidates"})
        nearest = (candidates - target).abs().sort_values().head(self.k)
        analogs = list(nearest.index)
        g = self._train[self._train["season_year"].isin(analogs)]
        probs, free = {}, {}
        for w, gw in g.groupby("week_index"):
            if int(w) not in weeks:
                continue
            probs[int(w)] = {str(int(b)): float(gw[f"le_{int(b)}"].mean()) for b in bands}
            free[int(w)] = float(gw["free"].mean())
        return Prediction(season_year, probs, free,
                          {"analogs": [int(a) for a in analogs], "target_state": target,
                           "analog_states": {int(a): float(self._state.loc[a]) for a in analogs}})
