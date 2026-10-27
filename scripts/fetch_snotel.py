"""Refresh data/snotel_daily_swe.csv from the NRCS AWDB service (no key).

    python scripts/fetch_snotel.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ccf.features import SITES, SNOTEL_CSV  # noqa: E402

URL = ("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"
       "?stationTriplets={triplets}&elements=WTEQ&duration=DAILY&beginDate=1979-01-01"
       "&endDate={end}&periodRef=END&centralTendencyType=NONE&returnFlags=false"
       "&returnOriginalValues=false&returnSuspectData=false")


def main() -> int:
    import datetime as dt
    url = URL.format(triplets=",".join(SITES), end=dt.date.today().isoformat())
    r = requests.get(url, timeout=120, headers={"User-Agent": "clear-creek-call-forecast"})
    r.raise_for_status()
    rows = []
    for s in r.json():
        for v in (s.get("data") or [{}])[0].get("values") or []:
            if v.get("value") is not None:
                rows.append((v["date"], s["stationTriplet"], v["value"]))
    rows.sort()
    with open(SNOTEL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "site", "swe_in"])
        w.writerows(rows)
    print(f"wrote {len(rows):,} rows to {SNOTEL_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
