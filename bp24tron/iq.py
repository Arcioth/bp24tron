"""Streaming stats for signed 8-bit interleaved IQ (.cs8).

The file is read in place and not copied. This is a level check only:
RMS, peak magnitude, and DC. It does not classify the waveform.
"""

from __future__ import annotations

import re
from pathlib import Path


def iq_summary(path: Path, chunk_bytes: int = 1 << 20) -> dict:
    path = Path(path)
    size = path.stat().st_size
    samples = 0
    power = 0
    peak = 0
    dc_i = 0
    dc_q = 0
    pending = b""
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_bytes)
            if not block:
                break
            buf = pending + block
            usable = len(buf) - (len(buf) % 2)
            pending = buf[usable:]
            for i in range(0, usable, 2):
                ii = buf[i]
                qq = buf[i + 1]
                if ii > 127:
                    ii -= 256
                if qq > 127:
                    qq -= 256
                p = ii * ii + qq * qq
                power += p
                dc_i += ii
                dc_q += qq
                if p > peak:
                    peak = p
            samples += usable // 2
    match = re.search(r"(\d+(?:\.\d+)?)M", path.name)
    rms = (power / samples) ** 0.5 if samples else None
    return {
        "file": str(path),
        "name": path.name,
        "bytes": size,
        "samples": samples,
        "trailing_bytes": len(pending),
        "rms": None if rms is None else round(rms, 2),
        "peak_mag": None if samples == 0 else round(peak**0.5, 2),
        "dc_i": None if samples == 0 else round(dc_i / samples, 3),
        "dc_q": None if samples == 0 else round(dc_q / samples, 3),
        "center_mhz": None if match is None else float(match.group(1)),
    }


def format_iq(summary: dict) -> str:
    center = summary["center_mhz"]
    center_s = "n/a" if center is None else f"{center:.0f} (from filename)"
    return (
        f"iq {summary['name']}  bytes={summary['bytes']}  samples={summary['samples']}  "
        f"rms={summary['rms']}  peak_mag={summary['peak_mag']}  "
        f"dc_i={summary['dc_i']}  dc_q={summary['dc_q']}  center_mhz={center_s}\n"
        "iq note: level check only, not a dwell classifier"
    )
