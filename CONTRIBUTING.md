# Contributing

Thanks for working on this. Three rules keep it honest.

## 1. One branch per change, reviewed before it lands

`main` is protected: changes arrive by pull request, CI must be green, and
the repository owner reviews (`.github/CODEOWNERS`). Fork or branch, either
is fine. Keep a PR to one idea: a feature, a model, a fix.

## 2. A model PR carries its receipt

Before you ask for review on a model, run

```bash
ccf hindcast --model <yours> --n-boot 2000 --out hindcast
```

and paste `hindcast/hindcast_<yours>.md` into the PR. The bar is the site's
gate, no more and no less:

- Brier skill **above zero against climatology** and **above zero against
  persistence**, leave-one-season-out over the usable seasons;
- the season-resampled 95% lower bound against climatology **above zero**.

A model that does not clear it is welcome as a **draft PR**: the hindcast
is still a finding, and "no detectable skill at this lead" is a result the
project wants written down. What is not welcome is a number that was fitted
on the season it was scored on. The harness prevents that for anything that
goes through it; do not go around it.

Never use information dated after the issue date as a feature. If a
feature is only known later in the season (peak SWE, for instance), say so
in its docstring and only use it for issue dates after it is known.

## 3. Label disagreements go to the label, not to the argument

If you think the truth table is wrong -- a call that should or should not
count, a season that should not be usable, a band that is the wrong
seniority -- open an issue titled `label: ...` with the week and the DWR
record. The site owner changes `call_truth.py` on hydrohistorian.com, a new
table is published, and both sides re-run. The gate compares
`truth_table_sha256`, so a forecast always says which label it was built on.

## Smaller things

- Python 3.10+; `pytest -q` must pass; keep dependencies to what
  `pyproject.toml` lists (ML extras go under `[ml]`).
- Say what a function does not know. Every output surface on the site
  carries its caveats; this code should hand them over, not hide them.
- Paper water: the target is an administrative cutline, not water delivered.
  Do not describe a forecast as "how much water you will get".
