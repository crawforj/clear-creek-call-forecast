from __future__ import annotations

import json

import pandas as pd
import pytest

from ccf import cli, data, emit, hindcast, truth
from ccf.models import Climatology, Persistence, SnowAnalog
from conftest import BANDS, make_weekly, snowy_seasons


def test_outcome_table_reads_the_label_without_recomputing_it():
    weekly = make_weekly({2020: {5: 15000.0, 6: None}, 2021: {5: 8000.0}}, usable={2021: False})
    t = truth.outcome_table(weekly, BANDS)
    assert set(t["season_year"]) == {2020}, "unusable seasons are left out"
    row = t[t["week_index"] == 5].iloc[0]
    assert bool(row["le_10000"]) is False and bool(row["le_20000"]) is True and bool(row["free"]) is False
    assert bool(t[t["week_index"] == 6].iloc[0]["free"]) is True


def test_climatology_and_persistence_are_what_they_say():
    seasons, _ = snowy_seasons(6)
    table = truth.outcome_table(make_weekly(seasons), BANDS)
    train = table[table["season_year"] != 2015]
    c = Climatology().fit(train, BANDS).predict(2015, BANDS, list(range(31)))
    assert 0.0 <= c.probs[12]["20000"] <= 1.0 and c.notes["n_train_seasons"][12] == 5
    p = Persistence().fit(train, BANDS).predict(2015, BANDS, list(range(31)))
    assert p.notes["persisted_season"] == 2014
    assert set(p.probs[12].values()) <= {0.0, 1.0}


def test_snow_analog_picks_the_nearest_seasons_by_swe(swe_features):
    seasons, f = snowy_seasons()
    table = truth.outcome_table(make_weekly(seasons), BANDS)
    train = table[table["season_year"] != 2012]
    m = SnowAnalog(k=3).fit(train, BANDS, swe_features)
    pred = m.predict(2012, BANDS, list(range(31)), swe_features)
    assert len(pred.notes["analogs"]) == 3 and 2012 not in pred.notes["analogs"]
    target = f.loc[2012, "swe_pct_median"]
    gaps = sorted(abs(f.loc[y, "swe_pct_median"] - target) for y in f.index if y != 2012)
    assert sorted(abs(v - target) for v in pred.notes["analog_states"].values()) == gaps[:3]


def test_the_harness_never_lets_a_season_see_itself(monkeypatch):
    seasons, _ = snowy_seasons(8)
    weekly = make_weekly(seasons)
    seen = []
    orig = Climatology.fit

    def spy(self, train, bands, features=None):
        seen.append(set(train["season_year"]))
        return orig(self, train, bands, features)
    monkeypatch.setattr(Climatology, "fit", spy)
    sk = hindcast.run(weekly, BANDS, Climatology, n_boot=50)
    years = truth.usable_seasons(weekly)
    # one fit per held-out season for the model AND one for the climatology reference
    assert len(seen) == 2 * len(years)
    for y, s in zip([y for y in years for _ in (0, 1)], seen):
        assert y not in s
    assert sk["n_seasons"] == len(years) - 1, "the first season has no persistence reference"
    assert abs(sk["bss_vs_climatology"]) < 1e-9, "climatology scored against itself is zero skill"
    assert sk["passes_gate"] is False and "NOT pass" in sk["verdict"]


def test_a_snow_driven_model_beats_the_baselines_when_snow_drives_the_calls(swe_features):
    seasons, _ = snowy_seasons(12)
    weekly = make_weekly(seasons)
    sk = hindcast.run(weekly, BANDS, SnowAnalog, {"k": 3}, features=swe_features, n_boot=200)
    assert sk["bss_vs_climatology"] > 0 and sk["bss_vs_persistence"] > 0
    assert sk["bootstrap_ci_bss_clim"][0] > 0
    assert sk["passes_gate"] is True and sk["verdict"].startswith("PASSES")
    assert set(sk["per_band"]) == {str(b) for b in BANDS}
    md = hindcast.report_markdown("snow-analog", sk, BANDS)
    assert "PASSES" in md and "| band <= 10,000" in md


def test_emit_writes_a_file_the_site_schema_accepts(truth_dir, swe_features, tmp_path):
    m, weekly, _ = data.load_local_truth(truth_dir)
    sk = hindcast.run(weekly, BANDS, SnowAnalog, {"k": 3}, features=swe_features, n_boot=100)
    table = truth.outcome_table(weekly, BANDS)
    model = SnowAnalog(k=3).fit(table, BANDS, swe_features)
    # 2021 is in the fixture's feature frame; a real emit uses next season's April-1 SWE
    pred = model.predict(2021, BANDS, list(range(31)), swe_features)
    payload = emit.build_payload(model, pred, m, sk, "v0.1.0", authors=["Test Author"])
    problems = emit.validate(payload)
    assert [p for p in problems if "jsonschema not installed" not in p] == [], problems
    assert payload["truth_table_sha256"] == m["files"][0]["sha256"]
    assert payload["season_year"] == 2021 and payload["horizon_weeks"] == 31
    for w in payload["weeks"]:
        vals = [w["p_controlling_le"][str(b)] for b in BANDS]
        assert vals == sorted(vals), "monotone across bands"
        assert w["p_free_river"] is None or w["p_free_river"] <= 1 - vals[-1] + 1e-9
    files = emit.write_release(payload, "# report", tmp_path / "dist")
    sums = (tmp_path / "dist" / "sha256sums.txt").read_text()
    assert "call_forecast_d1_wd7_clear_creek.json" in sums and "hindcast_report.md" in sums
    assert len(sums.splitlines()) == 2


def test_validate_flags_what_the_site_would_refuse(truth_dir, swe_features):
    m, weekly, _ = data.load_local_truth(truth_dir)
    sk = hindcast.run(weekly, BANDS, Climatology, n_boot=50)
    table = truth.outcome_table(weekly, BANDS)
    model = Climatology().fit(table, BANDS)
    payload = emit.build_payload(model, model.predict(2022, BANDS, list(range(31))), m, sk, "v0.0.1")
    problems = emit.validate(payload)
    assert any("bss_vs_climatology is not > 0" in p for p in problems)


def test_season_for_rolls_after_the_31_week_season():
    import datetime as dt
    assert emit.season_for(dt.date(2026, 11, 2)) == 2026
    assert emit.season_for(dt.date(2026, 11, 10)) == 2027
    assert emit.season_for(dt.date(2027, 2, 1)) == 2027


def test_cli_summary_and_hindcast_run_offline(truth_dir, tmp_path, capsys):
    assert cli.main(["--truth", str(truth_dir), "summary"]) == 0
    out = capsys.readouterr().out
    assert "base rate per band" in out and "2010" in out
    assert cli.main(["--truth", str(truth_dir), "hindcast", "--model", "climatology", "--n-boot", "50",
                     "--out", str(tmp_path / "h")]) == 0
    assert (tmp_path / "h" / "hindcast_climatology.md").exists()


def test_sha_check_refuses_a_tampered_download(tmp_path, monkeypatch):
    class R:
        status_code = 200
        def raise_for_status(self): pass
        def iter_content(self, n): yield b"tampered"
    monkeypatch.setattr(data.requests, "get", lambda *a, **k: R())
    with pytest.raises(ValueError, match="checksum"):
        data.fetch_file("https://x/static/data/releases/call_truth/clear_creek/", "call_truth_weekly.parquet", "0" * 64, cache=tmp_path)
