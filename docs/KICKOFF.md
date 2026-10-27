# Kickoff: forecasting the call on Clear Creek

*For Ryan McClure, from John Crawford. Everything linked here is public
and needs no account.*

## What we are trying to do

Nobody forecasts river calls. NRCS forecasts volume, CBRFC forecasts flow,
DWR's Call Analysis tool only looks backward. What a ditch company or a
city actually plans around is the **administrative** variable: *when does
the river call past my priority, and how deep does the call go?* On Clear
Creek the record of that variable is clean enough from 2005 on to try.

The pilot: a forecast, per week of the season, of the probability that the
controlling call on Clear Creek sits at or senior to each of five cutlines.
It is shown on hydrohistorian.com's Clear Creek page **only if it beats the
site's own base rates** by a published rule. Right now that page shows the
base rates and says so.

## How the collaboration works

You never need access to the site, its server or its code. Three things
connect us:

1. **The label**, published by the site every Saturday with checksums:
   https://hydrohistorian.com/data#call-truth-clear_creek (`docs/TARGET.md`
   explains every column). The Division 1 bulk release is beside it (calls,
   gages, daily flow, diversions, rights, structures).
2. **This repository**: `crawforj/clear-creek-call-forecast`, Apache-2.0,
   public. You get write access; `main` is protected, so work on a branch
   and open a PR. The three baselines and the hindcast harness are here;
   `ccf hindcast --model snow-analog` runs in a minute.
3. **One data file**, `call_forecast_d1_wd7_clear_creek.json`, attached to a
   tagged release. The site fetches it on Mondays, checks it against a
   schema and a gate (`docs/CONTRACT.md`), and shows it or writes down why
   not. No code from here runs there.

"Is it better" is settled by the hindcast and the site's ledger, never by
argument. "Is the label right" is settled by changing the label (open an
issue titled `label: ...`), after which we both re-run.

## Where to start (an hour)

```bash
git clone https://github.com/crawforj/clear-creek-call-forecast
cd clear-creek-call-forecast && python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ccf fetch && ccf summary
ccf hindcast --model climatology
ccf hindcast --model snow-analog --out hindcast
```

Or open `notebooks/quickstart.ipynb` in Colab.

Then read `docs/TARGET.md` and look at `hindcast/hindcast_snow-analog.md`:
that is the bar.

## If you work in R

Nothing here requires Python. The label is Parquet and CSV over HTTPS:

```r
library(arrow); library(dplyr)
base <- "https://hydrohistorian.com/static/data/releases/call_truth/clear_creek/"
weekly <- read_parquet(url(paste0(base, "call_truth_weekly.parquet"), "rb"))
weekly %>% filter(usable) %>% group_by(week_index) %>%
  summarise(p_le_10000 = mean(!is.na(controlling_admin_combined) & controlling_admin_combined <= 10000))
```

The contract is a JSON file (`docs/CONTRACT.md`); `jsonlite::write_json`
produces it, and `ccf validate FILE` (or the GitHub Action on a PR) checks
it the way the site will. Score with the same rules: Brier score, skill
`1 - Brier/Brier_ref`, interval by resampling whole seasons. An R
implementation of the harness would be a welcome first PR in its own
right (`R/` directory, `scoringRules` or hand-rolled, your call).

## Where your knowledge matters most (no code needed)

These are open questions the site has published for an expert read. Your
answers change the label and the features:

1. **Is "the most senior call on the stream" the cutline a Clear Creek
   operator actually plans around**, or does the South Platte call reaching
   up dominate in practice? The truth table carries both columns.
2. **Which Clear Creek calls are routinely futile or protocol-driven**
   (*City of Golden v. Simpson*; the Vidler / Green Mountain protocol)? Should
   they be labelled, or excluded from the target?
3. **Are the bands right?** 10000 / 20000 / 30000 / 40000 / 60000 admin
   numbers (roughly: senior to 1877 / 1904 / 1932 / 1959 / 2014). Which
   seniorities do people on this stream care about?
4. **Structure 0700553 (admin 61358)**: the site calls that right curtailed
   on 92.6% of days where DWR's analysis says 81.3%. Which of us is applying
   a call DWR does not, and why? (And Clear Lake Ditch 0700707 on South
   Clear Creek, the weakest agreement on the stream.)
5. **What drives Clear Creek calls** in your experience: April 1 snowpack,
   the melt timing, Standley Lake and Clear Creek reservoir operations,
   exchanges, the Golden calls? Anything you name becomes a feature we can
   test.

## Ideas on the table, in rough order of promise

- April-1 and May-1 SWE analogs with **learned** weights (the shipped
  baseline uses uniform weights).
- A discrete-time hazard model of **call onset week** per band (seasons as
  rows, weeks as time; gradient boosting is enough at ~21 seasons; pool
  bands).
- The Idaho pattern: volume forecast (NRCS/CBRFC for Clear Creek at
  Golden) -> expected daily flow -> first day flow < senior demand -> onset.
- Persistence *within* a season: once the call sets, how long does it hold?
  Re-issuing mid-season is allowed.

## What "done" looks like

One model that passes the gate, shown on the Clear Creek page through a full
season (April-October 2027), with the ledger reporting its skill against
both baselines with an interval. If nothing passes, the published finding is
that Clear Creek calls are not forecastable from outside at this lead, which
is also worth knowing.
