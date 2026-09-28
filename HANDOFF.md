# HANDOFF — bp24tron

Updated: 2026-09-28

## State

Classical 2.4 GHz recognizer for hack24tron sweep JSONL. Standard library only (numpy does not import here). RX only.

Real log: `/home/arcioth/Documents/hack24tron/logs/sweeps.jsonl`. Six sweeps, 2026-09-28, 2400–2484 MHz, 1 MHz bins, LNA 24 / VGA 20, about 91 ms each. Table: `examples/run-20260928.txt`.

Class counts on that log:

- wifi_ofdm = 1. Sweep 6, channel 6, center 2437 MHz, measured run 8 MHz, peak -27.96, margin 32.62 dB. Bandpass excess versus the louder guard is 6.72 dB.
- ble_adv = 0. Bins at 2402, 2426, and 2480 stayed within 6 dB of each sweep median.
- narrow_carrier = 6.
- quiet = 0.
- unresolved runs = 28. Not a class. Sweep 6 still has two loud groups, about 5 MHz wide, around 2406 and 2416 MHz (peaks -34.6 and -37.4).

`python3 -m bp24tron --check` passes. `examples/synthetic.jsonl` has four fake sweeps so each class fires (the Wi-Fi sweep also carries one narrow carrier).

IQ file `/home/arcioth/Documents/hack24tron/captures/iq-20260928T190252Z-2460M.cs8` is 4000000 bytes, 2000000 complex samples. It was streamed in place and not copied. RMS 4.29, peak magnitude 16.55, DC I +2.708, DC Q -3.066. That matches hack24tron's level check (they truncated the peak to 16). No modulation label yet.

## How to run

```bash
cd /home/arcioth/Documents/bp24tron
python3 -m bp24tron /home/arcioth/Documents/hack24tron/logs/sweeps.jsonl
python3 -m bp24tron --check
```

From elsewhere: `python3 /home/arcioth/Documents/bp24tron/analyze.py <jsonl>`.

Optional: `--bandpass CENTER_MHZ BW_MHZ`, or `--iq capture.cs8`. A `.cs8` path on its own prints the level check only.

## Next

IQ dwell classifier on a `.cs8` that stays where it is. Short FFTs, still classical: wide shoulder versus a tone versus noise. Do not copy the capture into this tree.

## Open

- Runs of 3–7 MHz are left unresolved on purpose. The two groups on sweep 6 are louder than several narrow hits. Undecided whether that becomes its own class or stays "confirm on an IQ dwell."
- A narrow hit needs 9 dB over the sweep median and 8 dB over the local median (±10 MHz). 2459 MHz on sweep 6 passed at 9.2 dB over the median. Do not retune that from six sweeps.
- A BLE advertisement is shorter than the time `hackrf_sweep` spends on one bin. ble_adv = 0 does not mean those channels were empty.
- Gates are margins, read at LNA 24 / VGA 20, amp off. There is no dBm calibration. A different gain needs the margins looked at again.
- No 40 MHz 802.11n class. Channel 6 winning does not say the signal was 20 MHz wide.
- The cs8 does not store a sample rate. hack24tron recorded this one at 8 Msps, 2460 MHz. This project does not assume that yet.
