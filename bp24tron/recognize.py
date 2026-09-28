"""Rule recognizer for one 2.4 GHz sweep. Not a trained model.

Floor is the median bin dB. A bin is hot when it is more than 6 dB above that
floor. Classes:

- quiet: no hot bin. One hit at the loudest bin, bandwidth 0.
- wifi_ofdm: a Wi-Fi channel 2412+(ch-1)*5 MHz (ch 1-13) whose 20 MHz mask
  holds a contiguous hot run at least 8 MHz wide, the run's power centroid is
  within 8 MHz of that center, the sweep covers at least 10 bins of the mask,
  and mean in-band power beats the louder adjacent guard (at least 3 bins) by
  3 dB. The 8 MHz run, not a full 20 MHz fill, is the hit: a ~90 ms HackRF
  sweep at 1 MHz rarely lights every OFDM bin. Reported center is the nominal
  channel. Reported bandwidth is the measured run width. Overlapping channels
  (centers less than 20 MHz apart) keep the one whose centroid is closer.
- ble_adv: one or two hot bins, bandwidth at most 2 MHz, loudest bin within
  1 MHz of 2402, 2426, or 2480, at least 8 dB above the local median
  (±10 MHz, excluding the run). Not emitted when that nearest Wi-Fi mask
  already holds an 8 MHz hot run.
- narrow_carrier: one or two hot bins, bandwidth at most 2 MHz, at least 9 dB
  above the sweep median and 8 dB above the local median, and the loudest bin
  is more than 1 MHz off every BLE advertising center.

margin_db is always peak_db minus the sweep median. The local median is only
a gate. Energy that is hot but matches none of the classes is left unresolved.
"""

from __future__ import annotations

import statistics

from .bandpass import channelize, coerce_bins, guard_excess

ACTIVITY_DB = 6.0
WIFI_MASK_MHZ = 20.0
WIFI_MIN_RUN_MHZ = 8.0
WIFI_CENTROID_MHZ = 8.0
WIFI_MIN_EXCESS_DB = 3.0
WIFI_MIN_MASK_BINS = 10
WIFI_MIN_GUARD_BINS = 3
WIFI_NMS_MHZ = 20.0
BLE_OFFSET_MHZ = 1.0
BLE_MIN_LOCAL_DB = 8.0
NARROW_MAX_BINS = 2
NARROW_MAX_MHZ = 2.0
NARROW_MIN_MARGIN_DB = 9.0
NARROW_MIN_LOCAL_DB = 8.0
LOCAL_HALF_MHZ = 10.0
LOCAL_MIN_BINS = 5

WIFI_CHANNELS = tuple((ch, 2412.0 + (ch - 1) * 5.0) for ch in range(1, 14))
BLE_CHANNELS = ((37, 2402.0), (38, 2426.0), (39, 2480.0))


def _bin_width_mhz(bins: list[dict], config: dict | None) -> float:
    hz = None if not config else config.get("bin_hz")
    if isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz > 0:
        return float(hz) / 1e6
    if len(bins) >= 2:
        diffs = [bins[i + 1]["mhz"] - bins[i]["mhz"] for i in range(len(bins) - 1)]
        diffs = [d for d in diffs if d > 0]
        if diffs:
            return float(statistics.median(diffs))
    return 1.0


def _runs(hot: list[dict], width: float) -> list[list[dict]]:
    runs: list[list[dict]] = []
    cur: list[dict] = []
    for b in hot:
        if cur and b["mhz"] - cur[-1]["mhz"] > width * 1.5:
            runs.append(cur)
            cur = [b]
        else:
            cur.append(b)
    if cur:
        runs.append(cur)
    return runs


def _longest(runs: list[list[dict]]) -> list[dict] | None:
    best = None
    best_key = None
    for run in runs:
        key = (run[-1]["mhz"] - run[0]["mhz"], max(b["db"] for b in run))
        if best_key is None or key > best_key:
            best = run
            best_key = key
    return best


def _bandwidth(run: list[dict], width: float) -> float:
    return (run[-1]["mhz"] - run[0]["mhz"]) + width


def _centroid(run: list[dict]) -> float:
    weights = [10 ** (b["db"] / 10.0) for b in run]
    total = sum(weights)
    return sum(b["mhz"] * w for b, w in zip(run, weights)) / total


def _local_median(bins: list[dict], run: list[dict]) -> float | None:
    lo = run[0]["mhz"] - LOCAL_HALF_MHZ
    hi = run[-1]["mhz"] + LOCAL_HALF_MHZ
    skip = {b["mhz"] for b in run}
    neigh = [b["db"] for b in bins if lo <= b["mhz"] <= hi and b["mhz"] not in skip]
    if len(neigh) < LOCAL_MIN_BINS:
        return None
    return float(statistics.median(neigh))


def _hit(cls: str, center: float, bandwidth: float, peak_db: float, margin: float) -> dict:
    return {
        "class": cls,
        "center_mhz": round(center, 2),
        "bandwidth_mhz": round(bandwidth, 2),
        "peak_db": round(peak_db, 2),
        "margin_db": round(margin, 2),
    }


def _mask_has_wide_run(bins: list[dict], center: float, floor: float, width: float) -> bool:
    mask = [b for b in bins if abs(b["mhz"] - center) <= WIFI_MASK_MHZ / 2.0]
    hot = [b for b in mask if b["db"] > floor + ACTIVITY_DB]
    run = _longest(_runs(hot, width))
    return run is not None and _bandwidth(run, width) + 1e-9 >= WIFI_MIN_RUN_MHZ


def recognize(sweep: dict) -> dict:
    """Classify one sweep object. Uses bins and optional config.bin_hz only."""
    raw = sweep.get("bins") if isinstance(sweep, dict) else None
    bins = coerce_bins(raw or [])
    width = _bin_width_mhz(bins, sweep.get("config") if isinstance(sweep, dict) else None)
    if not bins:
        return {
            "floor_db": None,
            "peak_mhz": None,
            "peak_db": None,
            "bin_width_mhz": width,
            "hits": [],
            "unresolved": [],
            "error": "no bins",
        }
    floor = float(statistics.median([b["db"] for b in bins]))
    peak = max(bins, key=lambda b: b["db"])
    hot = [b for b in bins if b["db"] > floor + ACTIVITY_DB]
    base = {
        "floor_db": floor,
        "peak_mhz": peak["mhz"],
        "peak_db": peak["db"],
        "bin_width_mhz": width,
    }
    if not hot:
        return {
            **base,
            "hits": [
                _hit(
                    "quiet",
                    peak["mhz"],
                    0.0,
                    peak["db"],
                    peak["db"] - floor,
                )
            ],
            "unresolved": [],
        }

    candidates = []
    for ch, center in WIFI_CHANNELS:
        bp = channelize(bins, center, WIFI_MASK_MHZ)
        if bp["inband_bins"] < WIFI_MIN_MASK_BINS:
            continue
        mask_hot = [b for b in bins if abs(b["mhz"] - center) <= WIFI_MASK_MHZ / 2.0 and b["db"] > floor + ACTIVITY_DB]
        run = _longest(_runs(mask_hot, width))
        if run is None:
            continue
        bw = _bandwidth(run, width)
        if bw + 1e-9 < WIFI_MIN_RUN_MHZ:
            continue
        centroid = _centroid(run)
        if abs(centroid - center) > WIFI_CENTROID_MHZ:
            continue
        excess = guard_excess(bp, WIFI_MIN_GUARD_BINS)
        if excess is None or excess < WIFI_MIN_EXCESS_DB:
            continue
        pk = max(run, key=lambda b: b["db"])
        candidates.append(
            {
                "ch": ch,
                "center": center,
                "run": run,
                "bandwidth": bw,
                "centroid": centroid,
                "inband_db": bp["inband_db"],
                "excess": excess,
                "peak": pk,
            }
        )
    candidates.sort(key=lambda c: (abs(c["centroid"] - c["center"]), -c["inband_db"]))
    kept = []
    for cand in candidates:
        if any(abs(cand["center"] - prev["center"]) < WIFI_NMS_MHZ for prev in kept):
            continue
        kept.append(cand)
    claimed = {b["mhz"] for cand in kept for b in cand["run"]}
    hits = [
        _hit(
            "wifi_ofdm",
            cand["center"],
            cand["bandwidth"],
            cand["peak"]["db"],
            cand["peak"]["db"] - floor,
        )
        for cand in kept
    ]

    unresolved = []
    for run in _runs([b for b in hot if b["mhz"] not in claimed], width):
        bw = _bandwidth(run, width)
        pk = max(run, key=lambda b: b["db"])
        margin = pk["db"] - floor
        local = _local_median(bins, run)
        local_margin = margin if local is None else pk["db"] - local
        narrow_shape = len(run) <= NARROW_MAX_BINS and bw <= NARROW_MAX_MHZ + 1e-9
        ble = None
        if narrow_shape:
            ble = min(BLE_CHANNELS, key=lambda item: abs(item[1] - pk["mhz"]))
            if abs(ble[1] - pk["mhz"]) > BLE_OFFSET_MHZ:
                ble = None
        wide_mask = False
        if ble is not None:
            nearest = min(WIFI_CHANNELS, key=lambda item: abs(item[1] - ble[1]))
            wide_mask = _mask_has_wide_run(bins, nearest[1], floor, width)
        if narrow_shape and ble is not None and local_margin >= BLE_MIN_LOCAL_DB and not wide_mask:
            hits.append(_hit("ble_adv", ble[1], bw, pk["db"], margin))
        elif narrow_shape and ble is None and margin >= NARROW_MIN_MARGIN_DB and local_margin >= NARROW_MIN_LOCAL_DB:
            hits.append(_hit("narrow_carrier", _centroid(run), bw, pk["db"], margin))
        else:
            unresolved.append(
                {
                    "lo_mhz": run[0]["mhz"],
                    "hi_mhz": run[-1]["mhz"],
                    "bins": len(run),
                    "peak_mhz": pk["mhz"],
                    "peak_db": round(pk["db"], 2),
                    "margin_db": round(margin, 2),
                }
            )
    hits.sort(key=lambda h: (h["center_mhz"], h["class"]))
    return {**base, "hits": hits, "unresolved": unresolved}
