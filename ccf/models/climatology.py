"""Baseline 1: climatology. Per week and band, the share of training
seasons in which the cutline sat at or senior to the band. This is what
hydrohistorian.com shows until a model beats it, computed by the same
rule (call_forecast.climatology on the site)."""
from __future__ import annotations

import pandas as pd

from .base import Model, Prediction


class Climatology(Model):
    name = "climatology"
    version = "1.0"

    def fit(self, train: pd.DataFrame, bands: list[int], features=None) -> "Climatology":
        self._by_week = {}
        for w, g in train.groupby("week_index"):
            self._by_week[int(w)] = {
                "probs": {str(int(b)): float(g[f"le_{int(b)}"].mean()) for b in bands},
                "free": float(g["free"].mean()), "n": int(len(g)),
            }
        return self

    def predict(self, season_year: int, bands: list[int], weeks: list[int], features=None) -> Prediction:
        probs = {w: dict(self._by_week[w]["probs"]) for w in weeks if w in self._by_week}
        free = {w: self._by_week[w]["free"] for w in weeks if w in self._by_week}
        return Prediction(season_year, probs, free, {"n_train_seasons": {w: self._by_week[w]["n"] for w in probs}})
