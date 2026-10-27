# The contract: what the site accepts

The site reads **one file** from the **latest GitHub Release** of this
repository: `call_forecast_d1_wd7_clear_creek.json`, checked against
`sha256sums.txt` from the same release. It validates the file against
`schema/call_forecast.schema.json` (the site holds its own copy; this one is
kept identical) and then applies the gate. No code from here runs there.

## The file

```json
{
  "schema_version": "1.0",
  "basin": "d1_wd7_clear_creek",
  "model": {"name": "snow-analog", "version": "v0.1.0", "repo": "crawforj/clear-creek-call-forecast",
            "git_sha": "abc1234", "authors": ["..."]},
  "issued_at": "2027-03-29T18:00:00Z",
  "data_through": "2027-03-28",
  "truth_table_sha256": "<sha256 of the call_truth_weekly.parquet it was built on>",
  "season_year": 2027, "season_start": "2027-04-01", "horizon_weeks": 31,
  "bands": [10000, 20000, 30000, 40000, 60000],
  "weeks": [
    {"week_index": 0, "week_start": "2027-04-01",
     "p_controlling_le": {"10000": 0.04, "20000": 0.11, "30000": 0.2, "40000": 0.3, "60000": 0.38},
     "p_free_river": 0.55}
  ],
  "season_min_admin_quantiles": {"q10": 7200, "q50": 15400, "q90": 41000},
  "skill": {"method": "leave-one-season-out hindcast over 21 usable seasons (2005-2025)",
            "n_seasons": 20, "bss_vs_climatology": 0.12, "bss_vs_persistence": 0.08,
            "brier": 0.17, "reliability": 0.01, "bootstrap_ci_bss_clim": [0.03, 0.21]},
  "caveats": ["paper water: a cutline of entitlements, not deliveries"]
}
```

`ccf emit` writes it; `ccf validate FILE` checks it the way the site will.

## The gate (every rule must pass; otherwise the previous accepted file stands)

1. `schema_version` is accepted (`1.0`); the structure matches the schema.
2. `basin == "d1_wd7_clear_creek"`; `bands` equal the truth table's `bands.json`.
3. `data_through` is within **14 days** of the day the site ingests; `issued_at` is not in the future.
4. `truth_table_sha256` names a weekly truth table the site published in the last **8 weeks**
   (the model was trained and scored on the site's own label).
5. `skill.bss_vs_climatology > 0` and `skill.bss_vs_persistence > 0`, and
   `skill.bootstrap_ci_bss_clim[0] > 0`.
6. Every probability in [0, 1]; non-decreasing across bands within a week;
   `p_free_river <= 1 - p(most junior band)`.
7. After acceptance the site **re-scores** the forecast every week against
   the truth table as the season fills in. A model whose live Brier skill
   against climatology is below zero over a complete season is **demoted**
   to the baseline; the card says so.

A refusal is written to the site as `d1_wd7_clear_creek.rejected.json` with
every reason, and the owner relays it on the PR or issue.

## Cadence

- Saturday: the site rebuilds the truth table (new `truth_table_sha256`).
- Monday: the site ingests the latest release and updates the ledger.
- Any time: a tag here builds a new release; the next Monday picks it up.

A forecast is **for a season**: `season_year`. Before April 1 the current
file is next season's outlook; during the season a re-issue (new tag) can
update it with in-season information.
