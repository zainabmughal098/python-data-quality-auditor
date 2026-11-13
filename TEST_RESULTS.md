# Portfolio release verification

Executed on 2026-11-13 (Asia/Karachi). Python 3.13.15, openpyxl 3.1.5, Windows 10 build 19045. All demo and test data is entirely synthetic. No publishing, GitHub push, or email was performed.

## Inspection and preservation

Inspected README.md, this file, audit.py, both test modules, rule files, and the original/V2 example outputs before edits. Validation is implemented in audit.py; there are no separate validation modules. No reproducible auditor defect was found, and no working application code, dependencies, or existing tests were modified.

SHA-256 hashes for 14 existing files were captured before work and compared afterward: audit.py, requirements.txt, both test modules, the original dataset, the existing six-row V2 dataset/rules, and all seven existing report artifacts. All 14 hashes matched. The local `.venv/` was retained.

## Exact automated checks run

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/run_portfolio_demo.py
```

- Full unittest discovery: **24 tests passed in 4.213 seconds**, exit code 0, no failures/errors/skips. Includes all 3 original tests and 21 existing V2 tests. Run outside the sandbox with access to temporary synthetic fixtures. No tests were added or removed for this release preparation.
- The demo support script executes the existing documented CLI via the same interpreter:

```bash
python audit.py examples/portfolio_10000.csv --config examples/portfolio_rules.json --output portfolio_reports
```

- The first support-script verification attempt failed because the new verifier compared empty JSON strings directly to openpyxl's `None` representation of empty cells. Normalizing empty Excel cells fixed the verifier; audit.py was unchanged. Two subsequent complete demo runs passed all checks. The earlier measured CLI run was 1.288526 seconds and overlapped the test launch; the final separate run below is the release measurement. These are observed runs, not a benchmark distribution.

The existing suite covers missing values, composite duplicates, numeric finiteness, exact dates/leap years, allowed values, invalid rules, score edge cases, BOM/CRLF, extra fields, original CLI flags, errors, report compatibility, input preservation, literal Excel text, XML-control escaping, and oversized cell handling.

## Synthetic dataset and measured run

The generator in `scripts/run_portfolio_demo.py` uses seed **20261113**, synthetic account labels/IDs, generated amounts/dates/statuses, and `example.com` email addresses. Defects are injected at documented deterministic intervals in the script. Its independently accumulated defect counts and affected-record set are checked against the auditor outputs. Existing demo input bytes are checked rather than overwritten.

- CSV: `examples/portfolio_10000.csv`, exactly **10,000 data rows**, six columns, plus one header.
- Rules: `examples/portfolio_rules.json`; all six columns required, customer_id unique, amount numeric, joined_on exact `%Y-%m-%d`, status in active/inactive.
- Input SHA-256: `6a36a7c073ef8d6a1ceaf6a66936d4df0c42105783e1ba6db4cf813d1c2808de`.
- Final CLI exit code: **0**. Captured stdout: `Audited 10000 rows; found 905 issue records. Reports: portfolio_reports`.
- Final CLI elapsed: **1.4596606998238713 seconds** (1.459661 rounded), measured with `time.perf_counter` around the subprocess. Includes interpreter startup, validation, and all four report writes. Excludes generation, report verification, and automated tests. No memory measurement, throughput guarantee, or multi-run statistical benchmark is claimed.

| Issue type | Count |
| --- | ---: |
| missing_required | 389 |
| duplicate_key | 103 |
| invalid_numeric | 112 |
| invalid_date_format | 120 |
| allowed_value_violation | 126 |
| invalid_email_format | 55 |
| **Total issue records** | **905** |

Missing cells: customer_id 19, name 76, email 88, amount 78, joined_on 67, status 61. There are zero exact duplicate rows; duplicate IDs belong to otherwise different records. **897** distinct records have issues; **9,103** pass. Score: `round(100 * 9103 / 10000, 2) = 91.03`. Multiple issues on a record count once in the score.

| Generated report | Bytes in final run |
| --- | ---: |
| portfolio_reports/summary.json | 118,132 |
| portfolio_reports/issues.csv | 34,488 |
| portfolio_reports/report.md | 1,586 |
| portfolio_reports/report.xlsx | 28,668 |

`portfolio_reports/verification.json` records the full precision timing, environment, source/report hashes, issue counts, score inputs, and workbook verification. Regeneration may change XLSX bytes because archive timestamps and workbook metadata can vary.

## Programmatic Excel and consistency verification

Loaded the final workbook with openpyxl using both `data_only=False` and `data_only=True`.

| Worksheet (in order) | Verified dimension |
| --- | --- |
| Summary | A1:B13 |
| Columns | A1:F7 |
| Issues | A1:D906 |
| Rules | A1:B6 |

Verified all summary metrics against JSON; the stored score at Summary!B9 is **91.03** in both load modes. There are **zero executable formula cells**; the documented score formula is literal text. Every issue record agrees between CSV, JSON, and Excel (normalizing Excel's empty cells). Every column metric and every effective rule agrees with JSON/configuration. Markdown rows, issue count, affected rows, score, and formula agree. Headers, freeze panes, and filter ranges were checked. Source CSV and rules bytes remained unchanged during the CLI run.

**Visual Excel rendering has not been verified.** No claim is made about manual layout review in Microsoft Excel or other spreadsheet applications.

## Repository hygiene verification

Expanded `.gitignore` for temporary files/logs, environment secrets, credentials, private-key formats, and local tool/account directories. Existing `.venv/`, `__pycache__/`, and `*.py[cod]` rules remain.

Used Git 2.55.0 `check-ignore --no-index` in an isolated temporary repository under ignored `.tmp/release-ignore-check/`, with a copy of the actual `.gitignore`. Direct path-argument checks confirmed all **23** representative paths were excluded: environment, nested bytecode/cache, temp files/directories, logs, .env variants, keys/certificates, credentials/secrets JSON, .aws, .ssh, and .codex. Four controls remained shareable: `.env.example`, `.env.template`, the demo CSV, and the workbook. An initial PowerShell stdin-pipeline check included carriage returns in paths; direct path arguments were used for the final verified checks.

There is no root `.git/` repository in this workspace. No repository was initialized at the project root, and tracked files/history could not be audited. Ignore checks do not prove absence of all possible secrets or remove already tracked secrets. No secret-file contents were read or exposed. The user's virtual environment was not deleted or recreated.

## Remaining limitations

No test failures or report consistency failures remain in the final executed checks. V2 release verification was performed only on Python 3.13.15/Windows; Python 3.10 compatibility and other platforms were not rerun. Visual Excel rendering, million-row boundaries, large-data memory use, and client workloads were not tested. The 10,000-row timing is a local observation only.

Existing product limits remain: in-memory processing, float-based numeric validation without business ranges, basic email syntax, calendar-date-only formats, Excel size limits, and nontransactional report writes. Optional missing values do not lower the score unless required; header-only input scores 100 with zero observations. **The quality score measures configured rule compliance, not absolute data correctness.** Review report values and absolute source paths before sharing. No broader security audit or staged/history secret scan was performed.

Earlier implementation verification (historical): the pre-V2 baseline had 3 passing tests; the previous V2 full run had 24 passing tests in 5.451 seconds. Prior sandbox-only attempts failed on temporary-directory permissions and were rerun with authorization; those attempts are not counted as passes in this report.
