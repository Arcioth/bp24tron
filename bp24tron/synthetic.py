"""Tiny sweeps that should hit each class. Not a capture."""

from __future__ import annotations


def _row(ts: str, edits: dict[int, float]) -> dict:
    bins = [{"mhz": float(mhz), "db": -70.0} for mhz in range(2400, 2485)]
    for mhz, db in edits.items():
        bins[mhz - 2400]["db"] = db
    return {
        "ts": ts,
        "config": {
            "f_lo": 2400,
            "f_hi": 2484,
            "bin_hz": 1000000,
            "lna_db": 0,
            "vga_db": 0,
        },
        "bins": bins,
        "note": "synthetic",
    }


def sweeps() -> list[dict]:
    return [
        _row("synthetic-quiet", {2450: -66.0}),
        _row("synthetic-ble", {2402: -52.0, 2403: -58.0}),
        _row("synthetic-narrow", {2410: -55.0, 2411: -55.0, 2412: -54.0, 2413: -55.0, 2450: -50.0}),
        _row(
            "synthetic-wifi",
            {mhz: -50.0 for mhz in range(2433, 2442)} | {2437: -40.0, 2470: -48.0},
        ),
    ]
