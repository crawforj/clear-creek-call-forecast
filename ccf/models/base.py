"""What a model is, for the harness and the emitter.

A model sees `train`: the outcome table (ccf.truth.outcome_table) for the
seasons it may learn from, plus any features it asks for, restricted to
those seasons. It returns, for one target season, a probability per
(week_index, band) and optionally p_free_river. The harness never hands a
model its own target season; that is what makes the hindcast honest.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Prediction:
    season_year: int
    # probs[week_index][str(band)] -> probability that controlling_admin_combined <= band
    probs: dict[int, dict[str, float]]
    p_free: dict[int, float | None] = field(default_factory=dict)
    notes: dict = field(default_factory=dict)


class Model:
    name = "model"
    version = "0.0.0"
    #: feature frames this model wants, by name (see ccf.features); the
    #: harness passes them as `features[name]` restricted to allowed seasons
    requires: tuple[str, ...] = ()

    def fit(self, train: pd.DataFrame, bands: list[int], features: dict[str, pd.DataFrame] | None = None) -> "Model":
        return self

    def predict(self, season_year: int, bands: list[int], weeks: list[int],
                features: dict[str, pd.DataFrame] | None = None) -> Prediction:
        raise NotImplementedError

    def describe(self) -> str:
        return f"{self.name} {self.version}"
