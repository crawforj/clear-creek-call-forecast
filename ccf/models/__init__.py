"""Models. Each one implements `Model` (base.py): fit on the seasons it is
allowed to see, predict probabilities for one season. The three here are
the BASELINES a contributed model must beat; put yours beside them.
"""
from .base import Model, Prediction
from .climatology import Climatology
from .persistence import Persistence
from .analog import SnowAnalog

REGISTRY: dict[str, type[Model]] = {
    "climatology": Climatology,
    "persistence": Persistence,
    "snow-analog": SnowAnalog,
}

__all__ = ["Model", "Prediction", "Climatology", "Persistence", "SnowAnalog", "REGISTRY"]
