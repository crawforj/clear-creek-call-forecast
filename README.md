# clear-creek-call-forecast

Forecasting the **controlling river call** on Clear Creek (Colorado Water
Division 1, Water District 7): per week of the administration season, the
probability that the most senior call in force sits at or senior to each of
five admin-number cutlines. Built on the call truth table that
[hydrohistorian.com](https://hydrohistorian.com) publishes, and scored by
the same rules the site scores by. A forecast that beats the site's
baselines is shown on the
[Clear Creek district page](https://hydrohistorian.com/basin/d1_wd7_clear_creek?tab=drought#call-outlook).

Nobody has published a method for forecasting Colorado calls. This
repository is where one gets built in the open.

## How it fits together

```
hydrohistorian.com  --publishes-->  call truth table + Division 1 release   (HTTPS, checksummed)
      ^                                        |
      |                                        v
  weekly job fetches the LATEST          this repo: features -> model -> hindcast -> emit
  tagged release's JSON, validates,            |
  gates on skill, shows or refuses   <-- GitHub Release: call_forecast_d1_wd7_clear_creek.json
```

No code from this repository runs on the site. The contract is one data
file, `schema/call_forecast.schema.json`, and a gate (`docs/CONTRACT.md`).

## Quick start

```bash
git clone https://github.com/crawforj/clear-creek-call-forecast
cd clear-creek-call-forecast
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

ccf fetch                      # the truth table, into ~/.cache/clear-creek-call-forecast
ccf summary                    # seasons, base rates, first-call weeks
ccf hindcast --model climatology
ccf hindcast --model snow-analog --out hindcast
```

Or open `notebooks/quickstart.ipynb` (runs in Colab: it only needs HTTPS).

## What is here

| path | what |
|---|---|
| `docs/TARGET.md` | **read first**: what the label is and what a forecast must state |
| `docs/CONTRACT.md` | the JSON the site accepts and the gate it applies |
| `docs/KICKOFF.md` | where to start if you are joining the project |
| `ccf/data.py` | fetch the published releases, checksum-checked |
| `ccf/truth.py` | the label as outcomes per (season, week, band) |
| `ccf/features.py` | predictors known on an issue date (SNOTEL SWE shipped; add yours) |
| `ccf/models/` | the three **baselines** a model must beat: climatology, persistence, snow analogs |
| `ccf/hindcast.py` | leave-one-season-out harness, Brier skill, season-bootstrap interval |
| `ccf/emit.py` | writes the release file and validates it against the schema and the gate |
| `data/snotel_daily_swe.csv` | daily SWE at Loveland Basin, Berthoud Summit, Grizzly Peak (NRCS AWDB) |

## Adding a model

1. Put a class in `ccf/models/yours.py` implementing `Model` (`fit`, `predict`;
   name any feature frames you need in `requires`). Register it in `ccf/models/__init__.py`.
2. Run `ccf hindcast --model yours --out hindcast` and read the verdict. The
   harness never lets a season see itself.
3. Open a PR with the hindcast report. `CONTRIBUTING.md` has the rule: a model
   PR shows Brier skill above zero against **both** climatology and
   persistence, with the season-resampled lower bound above zero, or it is a
   draft.
4. When it is merged and chosen, a tag `vX.Y.Z` builds the release the site reads.

## Data sources you can use without asking anyone

- The truth table and Division 1 release: https://hydrohistorian.com/data
- DWR CDSS REST (your own free key): `administrativecalls/historical`, `callanalysisbywdid`
- NRCS AWDB (no key): the three SNOTEL sites above
- USGS 06719505 Clear Creek at Golden; CBRFC forecast point GLDC2

## License

Apache-2.0. See `NOTICE` for what was ported from the site.
