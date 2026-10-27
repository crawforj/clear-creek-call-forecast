# The target: what a Clear Creek call forecast predicts

## One sentence

Per week of the administration season, the probability that the
**controlling admin number** on Clear Creek -- the most senior call in
force that reaches the district -- is **at or senior to** each of five
cutlines, so that every right junior to that cutline, on the stream below
the calling point, is out of priority.

## The label (what the site publishes and scores against)

hydrohistorian.com builds a **call truth table** every week from DWR's call
record and publishes it with checksums:
https://hydrohistorian.com/data#call-truth-clear_creek

`call_truth_weekly.parquet`, one row per `(season_year, week_index)`:

| column | meaning |
|---|---|
| `week_index` | 0 = the week beginning **April 1**; 31 weeks a season (through early November) |
| `controlling_admin_stream` | weekly minimum of the most senior admin number calling **on Clear Creek**; empty = no call on the stream |
| `controlling_admin_mainstem` | weekly minimum of the most senior call on **another stream** (in practice the South Platte) that DWR's set comments say reaches District 7; empty = none judged |
| **`controlling_admin_combined`** | `min(stream, mainstem)` -- **this is the target** |
| `mainstem_unjudged_admin` | calls on other streams that could not be judged either way; informational, never applied |
| `is_free_river` | true only when every day of the week had no applied call |
| `usable` | the season is complete and on/after the first recorded call on the stream (2005): a season a model may be scored on |

`call_truth_daily.parquet` has the same at daily resolution plus
`controlling_call_mile`, `controlling_call_wdid`, `controlling_call_name`
(which call controls and where it sits: DWR stream mile, measured from the
mouth; a call reaches only structures at a *larger* mile).

### Why stream-level and not per-structure

DWR only began routinely stating affected districts in set comments around
2015. A per-structure label ("was Farmers Highline curtailed this week?")
is therefore unjudgeable for most seasons before then, and the site's own
`call_climate.py` declined to fit a model on it. A call **on** Clear Creek
needs no such judgement: its own `waterSourceName` says where it is, and
tributary calls appear in the Division 1 record from about 2004. That gives
~21 usable seasons instead of ~8. Curtailment is monotone in priority, so
any structure's status follows by comparing its admin number to the cutline
(upstream of the calling point).

### The bands

`bands.json`: **10000, 20000, 30000, 40000, 60000**. An admin number's
integer part is days since 1849-12-31 for the controlling date, so
`<= 10000` means "a call senior to roughly May 1877" -- the 1859-1874
ditches (Farmers Highline, Rocky Mountain, Church, Welch, Agricultural) sit
well inside it. A forecast must state probabilities for exactly these
bands; the site compares them to its `bands.json` and refuses a mismatch.
If the bands are the wrong seniorities for this stream, say so
(`CONTRIBUTING.md` rule 3) -- they can change, on both sides at once.

## The outcome a probability refers to

For band B, season y, week w: `outcome = controlling_admin_combined <= B`.
Free river is `false` for every band. Probabilities must be
**non-decreasing across bands within a week** (a cutline at or senior to
10000 is necessarily at or senior to 20000). `p_free_river` is optional and
must not exceed `1 - p(<= 60000)`.

## What a forecast must beat

Two baselines, both computed from the truth table by the same code on both
sides (`ccf/models/`, `hydrohistorian call_forecast.py`):

- **climatology**: per week and band, the share of the *other* usable
  seasons with the outcome true;
- **persistence**: the previous usable season's outcomes as 0/1.

Scored leave-one-season-out by **Brier score**; skill is `1 - Brier /
Brier_reference`; the interval resamples whole seasons (weeks within a
season are not independent). The gate: skill > 0 against both, lower bound
of the climatology interval > 0.

## Caveats the site prints beside any number (carry them)

- **Paper water.** A cutline is a decreed-entitlement boundary. Augmentation
  plans, exchanges, substitute supply plans and futile-call rulings let a
  structure lawfully divert while out of priority; none is in the label.
- A call reaches only **upstream** of its calling point.
- The mainstem column applies another stream's call only when DWR's set
  comments name District 7, which DWR did sparsely before ~2015: that
  column understates early-season mainstem administration.
- Seasons before 2005 are **unrecorded, not free**.
- Day boundaries are America/Denver midnight.

## Things the record suggests, for a modeller

- Clear Creek's seniors are 1859-1874 ditches around Golden; Golden's own
  rights trace to a 1966 change decree; *City of Golden v. Simpson* (2002)
  and the Vidler / Green Mountain "protocol" dispute explain call
  lengthening that is not hydrologic.
- The South Platte compact call (1897 priority, Apr 1-Oct 15, Julesburg
  < 120 cfs) curtails District 64 only. It is not a Clear Creek driver.
- Snowpack: Loveland Basin (602), Berthoud Summit (335), Grizzly Peak (505)
  are the SNOTEL sites that drain to Clear Creek; `data/snotel_daily_swe.csv`.
- Flow: Clear Creek at Golden (DWR CLEGOLCO, USGS 06719505) is the index
  gage; the Division 1 release carries its daily record.
- The site's own existing outlook uses flow-state analogs at the as-of date
  and has not been shown to beat climatology (hydrohistorian /trust#limits,
  `outlook-no-skill`). That is the state of the art to improve on.
