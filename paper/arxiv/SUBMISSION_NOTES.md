# arXiv submission package

Upload `arxiv-submission.tar.gz` (or this directory, zipped) at
https://arxiv.org/submit

## Contents

| File | Purpose |
|---|---|
| `main.tex` | full source |
| `main.bbl` | pre-compiled bibliography — **arXiv does not run BibTeX**, so this must ship |
| `figures/*.png` | the 11 figures actually referenced by `main.tex` |

Verified to compile standalone with two `pdflatex` passes and no BibTeX run:
12 pages, no undefined citations or references.

`IEEEtran.cls` is not included — arXiv provides it. If the build fails on a
missing class, add it and resubmit.

## Form fields

- **Title:** Compared to What? A Human-Anchored Security Benchmark for
  LLM-Generated Infrastructure-as-Code
- **Author:** Animesh Shaw
- **Primary category:** `cs.CR` (Cryptography and Security)
- **Cross-list:** `cs.SE` (Software Engineering)
- **Comments field suggestion:** `12 pages, 11 figures, 9 tables. Code:
  https://github.com/AnimeshShaw/GenIaC-SecBench Data:
  https://huggingface.co/datasets/AnimeshShaw/GenIaC-SecBench`

## Licence

Pick at submission time. arXiv's default (perpetual non-exclusive) is the safe
choice if you may later submit to a venue with its own copyright terms. CC-BY-4.0
maximizes reuse and matches the dataset licence, but check your target venue
first — some publishers object to a pre-existing CC-BY preprint.

## Endorsement

A first submission to `cs.CR` may require endorsement. arXiv will say so during
submission; it is a per-category, one-time step.

## Before you click submit

- [ ] Confirm the author email renders as `animesh15b@iimk.edu.in`
- [ ] Confirm the three named reviewers in the Acknowledgements are happy with
      email + LinkedIn appearing in a permanently public preprint
- [ ] Confirm the GitHub repository is public, or remove the URL from the paper
      until it is — a dead link in a preprint is hard to correct
