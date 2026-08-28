# Contributing to GenIaC-SecBench

This is primarily a research artifact accompanying a published paper, but
issues and pull requests are welcome for:

- Bug reports in the pipeline scripts (`src/geniac_secbench/`)
- Reproducibility problems (see REPRODUCIBILITY.md first -- if a documented
  step doesn't work, that's a bug worth reporting with your OS/Python
  version and the exact command that failed)
- Extending the benchmark to new models, scanners, or IaC formats
- Documentation fixes

## Development setup

```bash
git clone https://github.com/AnimeshShaw/GenIaC-SecBench.git
cd GenIaC-SecBench
pip install -e .
pip install -r requirements.txt
python scripts/setup_checkov_env.py   # isolated venv for Checkov -- see the
                                       # script's docstring for why this is
                                       # separate from the main environment
```

## Repository layout

See the "Repository Architecture" section of README.md for the full
directory map. In short: `src/geniac_secbench/phaseN_*/` holds one directory
per pipeline phase, `scripts/` holds standalone utilities, `data/` holds
inputs/outputs (mostly gitignored -- the dataset lives on Hugging Face),
and `docs/` holds methodology and findings write-ups.

## Before submitting a PR

- Run `python -m geniac_secbench.config` to confirm the path resolver still
  finds the repo root from your working directory (this broke silently once
  before during a directory reorganization -- see
  docs/THREATS_TO_VALIDITY.md -- and is the easiest thing to regress).
- If you change a phase script's I/O paths, update them via `PATHS` in
  `src/geniac_secbench/config.py` rather than hardcoding a new relative
  path. That's the whole point of the resolver.
- If you add a new summary CSV or JSON output, add an entry to
  `docs/appendix/data_dictionary.md`.

## Code style

Plain, readable Python -- this codebase intentionally avoids heavy
abstraction so a third party can read a phase script top to bottom and
understand exactly what it does to the data. Match the existing style in
whichever file you're editing rather than introducing a new pattern.

## Reporting security issues in the pipeline itself

This is a research benchmark, not a production system, so there's no formal
security-disclosure process. If you find something that would affect the
validity of published results (not just a code bug), please open an issue
tagged `research-integrity` rather than a normal bug report -- it'll get
looked at first.
