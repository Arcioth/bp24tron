"""Passband integrator for HackRF sweep bins.

Bins are uncalibrated FFT powers in dB, one power per frequency label.
Integration is linear power, not an average of the dB numbers.
"""

from __future__ import annotations

import math


def coerce_bins(bins: list[dict]) -> list[dict]:
    """Sort bins by MHz. Duplicate frequencies are averaged in linear power."""
    grouped: dict[float, list[float]] = {}
    for item in bins:
        if not isinstance(item, dict):
            continue
        try:
            mhz = float(item["mhz"])
            db = float(item["db"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(mhz) or not math.isfinite(db):
            continue
        grouped.setdefault(round(mhz, 4), []).append(db)
    out = []
    for mhz in sorted(grouped):
        acc = sum(10 ** (db / 10.0) for db in grouped[mhz])
        out.append({"mhz": mhz, "db": 10.0 * math.log10(acc / len(grouped[mhz]))})
    return out


def _power_db(bins: list[dict], mean: bool) -> float | None:
    if not bins:
        return None
    acc = sum(10 ** (b["db"] / 10.0) for b in bins)
    if mean:
        acc /= len(bins)
    if acc <= 0:
        return None
    return 10.0 * math.log10(acc)


def channelize(bins: list[dict], center_mhz: float, bandwidth_mhz: float) -> dict:
    """Integrate bins in a passband and in the two adjacent guard bands.

    A bin at frequency f is inside the passband when abs(f - center) <= bandwidth/2
    (both edges stay in the passband). Each guard has the same width and sits
    against one edge. Mean power per bin is the level used to compare regions,
    so a shorter guard is not quieter just because it has fewer bins. Summed
    power is reported alongside it.

    excess_db is in-band mean power minus the louder non-empty guard. Callers
    that need to ignore a stub guard should use guard_excess().
    """
    center = float(center_mhz)
    bandwidth = float(bandwidth_mhz)
    if not math.isfinite(center) or not math.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError("bandwidth_mhz must be a positive finite number")
    rows = coerce_bins(bins)
    half = bandwidth / 2.0
    inner: list[dict] = []
    guard_lo: list[dict] = []
    guard_hi: list[dict] = []
    for b in rows:
        delta = b["mhz"] - center
        if abs(delta) <= half:
            inner.append(b)
        elif -3.0 * half <= delta < -half:
            guard_lo.append(b)
        elif half < delta <= 3.0 * half:
            guard_hi.append(b)
    peak = max(inner, key=lambda b: b["db"]) if inner else None
    report = {
        "center_mhz": center,
        "bandwidth_mhz": bandwidth,
        "inband_bins": len(inner),
        "guard_lo_bins": len(guard_lo),
        "guard_hi_bins": len(guard_hi),
        "inband_db": _power_db(inner, mean=True),
        "guard_lo_db": _power_db(guard_lo, mean=True),
        "guard_hi_db": _power_db(guard_hi, mean=True),
        "inband_sum_db": _power_db(inner, mean=False),
        "guard_lo_sum_db": _power_db(guard_lo, mean=False),
        "guard_hi_sum_db": _power_db(guard_hi, mean=False),
        "peak_mhz": None if peak is None else peak["mhz"],
        "peak_db": None if peak is None else peak["db"],
    }
    report["excess_db"] = guard_excess(report, min_bins=1)
    return report


def guard_excess(report: dict, min_bins: int = 1) -> float | None:
    """In-band mean dB minus the louder guard that has at least min_bins."""
    levels = []
    if report["guard_lo_db"] is not None and report["guard_lo_bins"] >= min_bins:
        levels.append(report["guard_lo_db"])
    if report["guard_hi_db"] is not None and report["guard_hi_bins"] >= min_bins:
        levels.append(report["guard_hi_db"])
    if not levels or report["inband_db"] is None:
        return None
    return report["inband_db"] - max(levels)
