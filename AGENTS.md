# bp24tron

2.4 GHz bandpass analyzer for HackRF sweep JSONL. Recognition stays on the PC.

- RX only. No TX, no jammer, no packet injection, no radio retune from this tree.
- Classical rules live in `bp24tron/recognize.py`. This is not a model. imprint24 is the other project.
- Python 3 standard library. Do not add numpy unless `python3 -c "import numpy"` works on this machine.
- Read `.cs8` in place. Do not copy captures into this tree.
- hack24tron owns the radio and the logs. This project only reads them.
- Do not touch other projects, git remotes, `/etc`, or boot.
- Update `HANDOFF.md` and `CHANGELOG.md` when the rules or the saved run change.
