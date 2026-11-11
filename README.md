# Static documentation auditor

An offline audit tool that compares documentation assertions with source syntax.
It uses only the standard library and never executes inspected files.

Install and run:

```sh
python3 -m pip install .
plotting-claim-audit --version
plotting-claim-audit audit . --json
python3 -m plotting_claim_audit audit . --verbose
python3 -m unittest discover
```

The optional directory defaults to the current directory. Root README.md and
Markdown files beneath a docs component are inspected. Fenced blocks are skipped;
inline code participates. Source files are parsed with AST. Symlinks and files
beneath fixtures, docs, or examples components are excluded from evidence.
Test files contribute separately. Syntax errors contribute no evidence.

Options include --json for structured output, --verbose for file counts,
repeatable --ignore PREFIX for root-relative path exclusions, and
--fail-on high|medium to set the failure threshold (default high).
Exit status is 0 below threshold, 2 for findings meeting the threshold, and 1
for usage or I/O errors. Findings remain visible below the failure threshold.

Finding identifiers and levels:

```text
documented-plotting-claim-false HIGH
documented-plotting-claim-false MEDIUM (test evidence only)
documented-no-plotting-claim-false HIGH
```

Analysis is static and module-local. It recognizes specified call names and
constructor/operation pairs; it does not prove runtime reachability or correctness.
No dependencies, network access, or telemetry are used.

## How this differs from nearby tools

- `matplotlib`, `seaborn`, `plotly`, `altair`, `bokeh`, and `pygal` are
  libraries that draw figures; this tool only checks whether documentation
  assertions about such calls match the source.
- `format-claim-audit` checks data formats, never charting calls.
- `image-*-claim-audit` tools check image ML operations, never charting calls.
- `bandit` and `ruff` report code issues, never documentation promises.
- `streaming-claim-audit` checks whole-file reads, never charting calls.

## Honest limitations

- Matching is static and syntactic, not semantic: a call name counts as
  evidence even in dead code, and dynamically constructed calls are missed.
- Import counts as context for some routes, so an unrelated call with a
  matching name in a module that imports the matching library may count.
- Aliases are tracked per file only; evidence split across modules never counts.
- A singular chart-type word is matched; its plural form is not.
- A sentence that denies a claim using words outside the denial list is
  not recognised as a denial.
