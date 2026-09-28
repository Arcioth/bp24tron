# CHANGELOG — bp24tron

## 2026-09-28

- Initial tree: channelizer (`bp24tron/bandpass.py`), rule recognizer (`bp24tron/recognize.py`), JSONL CLI (`python3 -m bp24tron`).
- Classes are wifi_ofdm, ble_adv, narrow_carrier, and quiet. Hot energy that matches none of them is printed as unresolved and is not a class.
- `--check` and `examples/synthetic.jsonl` cover all four classes.
- Ran the six-sweep hack24tron log. Counts: wifi_ofdm 1, ble_adv 0, narrow_carrier 6, quiet 0. Table saved to `examples/run-20260928.txt`.
- Optional `.cs8` reader reports RMS, peak magnitude, and DC only. The 2460 MHz capture was measured in place (RMS 4.29) and not copied.
