"""Synthetic ENTSO-E-shaped data generator (vectorised).

Lets the whole pipeline run end-to-end with NO API token, while producing data
that behaves like the real thing: diurnal demand curves, weekend dips, solar
that follows daylight, country-specific fuel mixes (FR nuclear-heavy, PL
coal-heavy, ES solar/wind, DE mixed renewables, NL gas). The output frames have
exactly the same shape as the real extract, so staging/marts/dbt can't tell the
difference.

Implementation notes:
  * Fully vectorised with NumPy — no per-row Python loops. Generating N rows is
    O(N) with a tiny constant; the only Python-level loop is over the ~8 fuels,
    which is inherent to the output shape (hours x fuels).
  * Deterministic across runs: seeds are derived with hashlib (not the salted
    built-in hash()), so re-running produces identical data.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

# Rough peak demand (MW) per bidding zone — sets the scale of each country.
_PEAK_LOAD_MW = {
    "DE_LU": 75_000, "FR": 60_000, "ES": 40_000, "NL": 18_000, "PL": 25_000,
}

# Per-country generation mix as a share of that hour's load. Keys are raw
# ENTSO-E-style production-type labels; shares only need to be characteristic.
_FUEL_MIX = {
    "DE_LU": {"Solar": 0.14, "Wind Onshore": 0.22, "Wind Offshore": 0.06,
              "Nuclear": 0.03, "Fossil Gas": 0.15, "Fossil Hard coal": 0.18,
              "Hydro Water Reservoir": 0.04, "Biomass": 0.08},
    "FR":    {"Solar": 0.06, "Wind Onshore": 0.10, "Wind Offshore": 0.02,
              "Nuclear": 0.65, "Fossil Gas": 0.05, "Fossil Hard coal": 0.01,
              "Hydro Water Reservoir": 0.09, "Biomass": 0.02},
    "ES":    {"Solar": 0.20, "Wind Onshore": 0.23, "Wind Offshore": 0.00,
              "Nuclear": 0.20, "Fossil Gas": 0.20, "Fossil Hard coal": 0.02,
              "Hydro Water Reservoir": 0.10, "Biomass": 0.02},
    "NL":    {"Solar": 0.14, "Wind Onshore": 0.14, "Wind Offshore": 0.10,
              "Nuclear": 0.03, "Fossil Gas": 0.45, "Fossil Hard coal": 0.05,
              "Hydro Water Reservoir": 0.00, "Biomass": 0.07},
    "PL":    {"Solar": 0.07, "Wind Onshore": 0.16, "Wind Offshore": 0.00,
              "Nuclear": 0.00, "Fossil Gas": 0.09, "Fossil Hard coal": 0.60,
              "Hydro Water Reservoir": 0.02, "Biomass": 0.06},
}


def _rng(*parts: object) -> np.random.Generator:
    """Deterministic NumPy Generator seeded from a stable hash of `parts`."""
    digest = hashlib.sha256("-".join(map(str, parts)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def _make_index(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Hourly, timezone-aware index (Europe/Berlin) like the real API returns."""
    start = start.tz_convert("Europe/Berlin") if start.tz else start.tz_localize("Europe/Berlin")
    end = end.tz_convert("Europe/Berlin") if end.tz else end.tz_localize("Europe/Berlin")
    return pd.date_range(start=start, end=end, freq="h", inclusive="left", tz="Europe/Berlin")


def _demand_factor(hours: np.ndarray, weekend: np.ndarray) -> np.ndarray:
    """Vectorised demand shape: morning + evening peaks, overnight trough, weekend dip."""
    base = (0.62
            + 0.30 * np.sin((hours - 7) / 24 * 2 * np.pi)
            + 0.14 * np.sin((hours - 18) / 24 * 4 * np.pi))
    base = np.where(weekend, base * 0.90, base)
    return np.maximum(0.45, base)


def _solar_factor(hours: np.ndarray) -> np.ndarray:
    """Vectorised solar: daylight only (06–20h local), peaking around noon."""
    daylight = (hours >= 6) & (hours <= 20)
    return np.where(daylight, np.maximum(0.0, np.sin((hours - 6) / 14 * np.pi)), 0.0)


def synth_load(country: str, start: pd.Timestamp, end: pd.Timestamp, seed: int = 42) -> pd.DataFrame:
    """One country's actual-load series, shaped like fetch_load output."""
    idx = _make_index(start, end)
    if len(idx) == 0:
        return pd.DataFrame(columns=["country_code", "datetime", "resolution", "load_mw"])
    hours = idx.hour.to_numpy()
    weekend = idx.weekday.to_numpy() >= 5
    peak = _PEAK_LOAD_MW.get(country, 20_000)
    noise = _rng(country, "load", seed).uniform(0.96, 1.04, size=len(idx))
    load = np.round(peak * _demand_factor(hours, weekend) * noise, 1)
    return pd.DataFrame({
        "country_code": country,
        "datetime": idx,
        "resolution": "PT60M",
        "load_mw": load,
    })


def synth_generation(country: str, start: pd.Timestamp, end: pd.Timestamp, seed: int = 42) -> pd.DataFrame:
    """One country's generation-by-fuel series, shaped like fetch_generation output."""
    idx = _make_index(start, end)
    cols = ["country_code", "datetime", "resolution", "production_type",
            "generation_mw", "consumption_mw"]
    if len(idx) == 0:
        return pd.DataFrame(columns=cols)

    hours = idx.hour.to_numpy()
    weekend = idx.weekday.to_numpy() >= 5
    peak = _PEAK_LOAD_MW.get(country, 20_000)
    mix = _FUEL_MIX.get(country, _FUEL_MIX["DE_LU"])
    rng = _rng(country, "gen", seed)
    total = peak * _demand_factor(hours, weekend) * rng.uniform(0.96, 1.04, size=len(idx))
    solar = _solar_factor(hours)
    n = len(idx)

    frames = []
    for fuel, share in mix.items():
        if fuel == "Solar":
            gen = total * share * solar * rng.uniform(0.85, 1.15, n)
        elif "Wind" in fuel:
            gen = total * share * rng.uniform(0.30, 1.60, n)   # wind is volatile
        elif fuel == "Nuclear":
            gen = total * share * rng.uniform(0.97, 1.01, n)   # baseload, very flat
        else:
            gen = total * share * rng.uniform(0.80, 1.10, n)
        frames.append(pd.DataFrame({
            "country_code": country,
            "datetime": idx,
            "resolution": "PT60M",
            "production_type": fuel,
            "generation_mw": np.round(np.maximum(0.0, gen), 1),
            "consumption_mw": np.nan,
        }))
    return pd.concat(frames, ignore_index=True)
