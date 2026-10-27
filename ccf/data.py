"""Fetching the site's published data, checksum-checked, into a local cache.

Everything here is a plain HTTPS GET of a static file. No key, no login.
The manifest lists every file with its SHA-256; a file that does not match
is refused, never used.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import requests

from . import TRUTH_URL, DIV1_URL

CACHE = Path(os.environ.get("CCF_CACHE", Path.home() / ".cache" / "clear-creek-call-forecast"))
UA = {"User-Agent": "clear-creek-call-forecast (github.com/crawforj/clear-creek-call-forecast)"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_manifest(url_prefix: str = TRUTH_URL, timeout: float = 30.0) -> dict:
    r = requests.get(url_prefix + "manifest.json", timeout=timeout, headers=UA)
    r.raise_for_status()
    return r.json()


def fetch_file(url_prefix: str, path: str, expected_sha: str | None, cache: Path | None = None,
               timeout: float = 120.0) -> Path:
    """Download one release file into the cache unless the cached copy
    already matches the expected checksum."""
    cache = Path(cache or CACHE)
    sub = url_prefix.rstrip("/").split("/releases/")[-1]
    dest = cache / sub / path
    if dest.exists() and expected_sha and sha256(dest) == expected_sha:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url_prefix + path, timeout=timeout, headers=UA, stream=True)
    r.raise_for_status()
    tmp = dest.with_name(dest.name + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    if expected_sha and sha256(tmp) != expected_sha:
        tmp.unlink()
        raise ValueError(f"{path}: checksum mismatch against the manifest; refusing to use it")
    tmp.replace(dest)
    return dest


def truth_table(cache: Path | None = None, url_prefix: str = TRUTH_URL) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """(manifest, weekly, daily) for the Clear Creek call truth table."""
    m = fetch_manifest(url_prefix)
    shas = {f["path"]: f["sha256"] for f in m["files"]}
    weekly = pd.read_parquet(fetch_file(url_prefix, "call_truth_weekly.parquet", shas.get("call_truth_weekly.parquet"), cache))
    daily = pd.read_parquet(fetch_file(url_prefix, "call_truth_daily.parquet", shas.get("call_truth_daily.parquet"), cache))
    return m, weekly, daily


def truth_sha(manifest: dict) -> str | None:
    for f in manifest.get("files") or []:
        if f.get("path") == "call_truth_weekly.parquet":
            return f.get("sha256")
    return None


def div1_table(table: str, cache: Path | None = None) -> pd.DataFrame:
    """One table of the Division 1 bulk release (calls, gages, streamflow_daily,
    diversions, structures, water_rights, ...). See the release README."""
    m = fetch_manifest(DIV1_URL)
    files = [f for f in m["files"] if f.get("table") == table and f.get("format") == "parquet"]
    if not files:
        raise LookupError(f"no parquet for table {table!r} in the Division 1 release")
    frames = [pd.read_parquet(fetch_file(DIV1_URL, f["path"], f.get("sha256"), cache)) for f in files]
    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


def load_local_truth(folder: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """The same three objects from a folder on disk (a downloaded release or
    a test fixture)."""
    folder = Path(folder)
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    weekly = pd.read_parquet(folder / "call_truth_weekly.parquet")
    daily_p = folder / "call_truth_daily.parquet"
    daily = pd.read_parquet(daily_p) if daily_p.exists() else pd.DataFrame()
    return m, weekly, daily
