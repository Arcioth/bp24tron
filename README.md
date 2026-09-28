# bp24tron

2.4 GHz bandpass analyzer. The heavy step runs on the PC, on a HackRF sweep log. Nothing here runs on the PortaPack. The classes are fixed rules, not a trained model. A neural net would be a different project (imprint24).

## Run

```bash
cd /home/arcioth/Documents/bp24tron
python3 -m bp24tron /home/arcioth/Documents/hack24tron/logs/sweeps.jsonl
python3 -m bp24tron examples/synthetic.jsonl
python3 -m bp24tron --check
python3 -m bp24tron sweeps.jsonl --bandpass 2437 20
python3 -m bp24tron sweeps.jsonl --iq /path/to/capture.cs8
```

From another directory:

```bash
python3 /home/arcioth/Documents/bp24tron/analyze.py /path/to/sweeps.jsonl
```

Python 3 standard library only. Each JSONL line needs `bins: [{"mhz", "db"}, ...]`. Optional: `ts`, `duration_ms`, `config.bin_hz`, `config.lna_db`, `config.vga_db`. Precomputed `wifi` and `ble` arrays on a hack24tron line are ignored.

`examples/run-20260928.txt` is the 2026-09-28 log. `examples/synthetic.jsonl` is four fake sweeps used by `--check`.

## Rules

The floor is the median bin, in dB. A bin is hot when it is more than 6 dB above that floor.

A hit is `class`, `center_mhz`, `bandwidth_mhz`, `peak_db`, `margin_db`. `margin_db` is the peak minus the sweep median. The local median is only a gate.

- **quiet** — no hot bin. One hit at the loudest bin, bandwidth 0.
- **wifi_ofdm** — Wi-Fi center `2412 + (ch-1)*5` MHz for channels 1–13. Inside the 20 MHz mask (center ± 10 MHz) the longest contiguous hot run must be at least 8 MHz wide, and that run's power centroid must lie within 8 MHz of the center. Mean power in the mask must beat the louder adjacent guard by at least 3 dB. A guard with fewer than 3 bins is not used. The sweep must actually cover at least 10 bins of the mask. The reported center is the nominal channel. The reported bandwidth is the measured run, not a forced 20. Passing channels whose centers are less than 20 MHz apart keep the one closer to its centroid.
- **ble_adv** — one or two hot bins, width at most 2 MHz, loudest bin within 1 MHz of 2402, 2426, or 2480, and at least 8 dB above the local median (±10 MHz, run excluded). Not emitted when the nearest Wi-Fi mask already contains an 8 MHz hot run.
- **narrow_carrier** — one or two hot bins, width at most 2 MHz, at least 9 dB above the sweep median and 8 dB above the local median, and the loudest bin is more than 1 MHz off those three BLE centers.

Hot energy that matches none of these is printed as `unresolved`. That is not a class.

The Wi-Fi mask that is integrated is 20 MHz. The 8 MHz run is the detector because a ~90 ms, 1 MHz sweep does not light every bin of an OFDM channel. Both passband edges are included, so a 20 MHz mask on a 1 MHz grid is 21 bins. Region levels are mean linear power per bin (a short guard is not penalized). Summed power is printed next to the mean.

## IQ

A `.cs8` argument, or `--iq`, streams interleaved signed 8-bit I/Q and prints RMS, peak magnitude, and DC. The file is not copied. This is a level check, not a modulation classifier.

## What this does not do

- No transmit, no jammer, no retune.
- No Wi-Fi or BLE packet decode.
- No neural net.
- The dB values are uncalibrated HackRF FFT powers, not dBm. Compare them only at the same LNA and VGA.
- No 40 MHz 802.11n class.
- A handful of sweeps is not an occupancy study.
