"""CLI: python3 -m bp24tron sweeps.jsonl"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .bandpass import channelize, guard_excess
from .iq import format_iq, iq_summary
from .recognize import (
    WIFI_CHANNELS,
    WIFI_MASK_MHZ,
    WIFI_MIN_GUARD_BINS,
    recognize,
)
from .synthetic import sweeps as synthetic_sweeps


def load_jsonl(path: Path) -> tuple[list[dict], int]:
    rows: list[dict] = []
    bad = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                bad += 1
                continue
            if not isinstance(obj, dict) or not isinstance(obj.get("bins"), list):
                bad += 1
                continue
            rows.append(obj)
    return rows, bad


def _channel(center: float) -> str:
    for ch, mhz in WIFI_CHANNELS:
        if abs(mhz - center) < 0.01:
            return f"ch{ch}"
    return "mask"


def format_bandpass(bp: dict, label: str) -> str:
    def side(name: str, db: float | None, n: int) -> str:
        if db is None:
            return f"{name}=n/a"
        return f"{name}={db:.2f} ({n})"

    if bp["inband_db"] is None:
        inner = "in=n/a"
    else:
        inner = (
            f"in={bp['inband_db']:.2f} mean ({bp['inband_bins']} bins, "
            f"sum {bp['inband_sum_db']:.2f})"
        )
    excess = guard_excess(bp, WIFI_MIN_GUARD_BINS)
    excess_s = "n/a" if excess is None else f"{excess:.2f}"
    return (
        f"  bandpass {label} {bp['center_mhz']:.2f}/{bp['bandwidth_mhz']:.2f}  "
        f"{inner}  {side('glo', bp['guard_lo_db'], bp['guard_lo_bins'])}  "
        f"{side('ghi', bp['guard_hi_db'], bp['guard_hi_bins'])}  "
        f"excess {excess_s}"
    )


def format_unresolved(rows: list[dict]) -> str:
    parts = []
    for row in rows:
        n = row["bins"]
        unit = "bin" if n == 1 else "bins"
        parts.append(
            f"{row['lo_mhz']:.0f}-{row['hi_mhz']:.0f} ({n} {unit}, peak {row['peak_db']:.1f})"
        )
    return "  unresolved: " + ", ".join(parts)


def render(rows: list[dict], source: str, bandpass: tuple[float, float] | None) -> str:
    lines = [
        f"bp24tron  source={source}  sweeps={len(rows)}",
        "dB values are uncalibrated HackRF FFT bins, not dBm. RX only.",
        f"  {'class':<16} {'center':>8} {'bw':>6} {'peak_db':>8} {'margin':>7}",
    ]
    counts: Counter[str] = Counter()
    unresolved_runs = 0
    for index, sweep in enumerate(rows, start=1):
        result = recognize(sweep)
        ts = sweep.get("ts", "?")
        cfg = sweep.get("config") or {}
        gain = ""
        if "lna_db" in cfg or "vga_db" in cfg:
            gain = f"  lna={cfg.get('lna_db', '?')} vga={cfg.get('vga_db', '?')}"
        dur = sweep.get("duration_ms")
        dur_s = f"  dur={dur}ms" if isinstance(dur, (int, float)) else ""
        if result.get("error"):
            lines.append(f"sweep {index}/{len(rows)}  ts={ts}  {result['error']}")
            lines.append("")
            continue
        lines.append(
            f"sweep {index}/{len(rows)}  ts={ts}{dur_s}  bins={len(sweep['bins'])}  "
            f"floor={result['floor_db']:.2f}  "
            f"peak={result['peak_db']:.2f} @ {result['peak_mhz']:.1f}{gain}"
        )
        if not result["hits"]:
            lines.append("  (no class hit)")
        for hit in result["hits"]:
            counts[hit["class"]] += 1
            lines.append(
                f"  {hit['class']:<16} {hit['center_mhz']:8.2f} {hit['bandwidth_mhz']:6.2f} "
                f"{hit['peak_db']:8.2f} {hit['margin_db']:7.2f}"
            )
            if hit["class"] == "wifi_ofdm":
                bp = channelize(sweep["bins"], hit["center_mhz"], WIFI_MASK_MHZ)
                lines.append(format_bandpass(bp, _channel(hit["center_mhz"])))
        unresolved_runs += len(result["unresolved"])
        if result["unresolved"]:
            lines.append(format_unresolved(result["unresolved"]))
        if bandpass is not None:
            bp = channelize(sweep["bins"], bandpass[0], bandpass[1])
            lines.append(format_bandpass(bp, "chosen"))
        lines.append("")
    order = ("wifi_ofdm", "ble_adv", "narrow_carrier", "quiet")
    counts_s = " ".join(f"{name}={counts.get(name, 0)}" for name in order)
    lines.append(f"counts {counts_s} unresolved_runs={unresolved_runs}")
    return "\n".join(lines).rstrip() + "\n"


def run_check() -> int:
    flat = [{"mhz": float(i), "db": 0.0} for i in range(0, 101)]
    bp = channelize(flat, 50, 10)
    excess = guard_excess(bp, 1)
    if bp["inband_bins"] != 11 or bp["guard_lo_bins"] != 10 or bp["guard_hi_bins"] != 10:
        print("check failed: flat bin counts", bp["inband_bins"], bp["guard_lo_bins"], bp["guard_hi_bins"], file=sys.stderr)
        return 1
    if excess is None or abs(excess) > 1e-6 or abs(bp["inband_db"] or 0) > 1e-6:
        print("check failed: flat excess", excess, file=sys.stderr)
        return 1
    hot = [{"mhz": float(i), "db": -60.0} for i in range(0, 101)]
    for i in range(45, 56):
        hot[i]["db"] = -40.0
    hot_bp = channelize(hot, 50, 10)
    hot_ex = guard_excess(hot_bp, 3)
    if hot_ex is None or abs(hot_ex - 20.0) > 0.05:
        print("check failed: hot excess", hot_ex, file=sys.stderr)
        return 1

    expect = {
        "synthetic-quiet": [("quiet", 2450.0, 0.0)],
        "synthetic-ble": [("ble_adv", 2402.0, 2.0)],
        "synthetic-narrow": [("narrow_carrier", 2450.0, 1.0)],
        "synthetic-wifi": [("wifi_ofdm", 2437.0, 9.0), ("narrow_carrier", 2470.0, 1.0)],
    }
    rows = synthetic_sweeps()
    print(render(rows, "synthetic", None), end="")
    failed = False
    for row in rows:
        got = recognize(row)
        want = expect[row["ts"]]
        classes = [(h["class"], h["center_mhz"], h["bandwidth_mhz"]) for h in got["hits"]]
        if classes != want:
            print(f"check failed: {row['ts']} got {classes} want {want}", file=sys.stderr)
            failed = True
        if row["ts"] == "synthetic-narrow" and not got["unresolved"]:
            print("check failed: 4 MHz blob was not left unresolved", file=sys.stderr)
            failed = True
        if row["ts"] == "synthetic-quiet" and got["hits"][0]["margin_db"] > 6:
            print("check failed: quiet margin", file=sys.stderr)
            failed = True
    if failed:
        return 1
    print("check ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m bp24tron",
        description="Classify 2.4 GHz HackRF sweep JSONL with fixed DSP rules. RX only.",
    )
    parser.add_argument("path", nargs="?", type=Path, help="sweeps.jsonl, or a .cs8 IQ file")
    parser.add_argument("--iq", type=Path, help="signed-8 IQ .cs8 to measure in place (not copied)")
    parser.add_argument(
        "--bandpass",
        nargs=2,
        type=float,
        metavar=("CENTER_MHZ", "BW_MHZ"),
        help="also print a channelizer row at this center and bandwidth",
    )
    parser.add_argument("--check", action="store_true", help="run built-in synthetic checks")
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    if args.path is None:
        parser.error("path is required unless --check")
    path = args.path
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2
    if path.suffix.lower() == ".cs8":
        if args.bandpass or args.iq:
            parser.error("a .cs8 path is the IQ file; do not combine it with --bandpass or --iq")
        print(format_iq(iq_summary(path)))
        return 0
    try:
        rows, bad = load_jsonl(path)
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 2
    if bad:
        print(f"skipped {bad} lines", file=sys.stderr)
    if not rows:
        print(f"no sweeps in {path}", file=sys.stderr)
        return 1
    bandpass = None if args.bandpass is None else (args.bandpass[0], args.bandpass[1])
    print(render(rows, str(path), bandpass), end="")
    if args.iq is not None:
        if not args.iq.is_file():
            print(f"not a file: {args.iq}", file=sys.stderr)
            return 2
        print(format_iq(iq_summary(args.iq)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
