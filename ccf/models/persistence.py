"""Baseline 2: persistence. What the most recent training season before
the target did, as 0/1. Deliberately naive: a model that cannot beat 'same
as last year' has learned nothing about this year."""
from __future__ import annotations

import pandas as pd

from .base import Model, Prediction


class Persistence(Model):
    name = "persistence"
    version = "1.0"

    def fit(self, train: pd.DataFrame, bands: list[int], features=None) -> "Persistence":
        self._train = train
        return self

    def predict(self, season_year: int, bands: list[int], weeks: list[int], features=None) -> Prediction:
        prior = sorted(y for y in set(self._train["season_year"]) if y < season_year)
        if not prior:
            return Prediction(season_year, {}, {}, {"reason": "no earlier season to persist"})
        g = self._train[self._train["season_year"] == prior[-1]].set_index("week_index")
        probs = {w: {str(int(b)): float(g.loc[w, f"le_{int(b)}"]) for b in bands} for w in weeks if w in g.index}
        free = {w: float(g.loc[w, "free"]) for w in weeks if w in g.index}
        return Prediction(season_year, probs, free, {"persisted_season": prior[-1]})
