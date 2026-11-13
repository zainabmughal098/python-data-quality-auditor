# Data Quality Auditor V2: portfolio demonstration

## Business problem and solution

CSV exports used for customer reporting, billing, and migrations can contain incomplete records, repeated identifiers, invalid amounts, inconsistent dates, and unsupported statuses. These defects can distort reports and increase manual review work.

This read-only Python auditor applies explicit JSON rules and produces a detailed issue CSV, a machine-readable JSON summary, a Markdown report, and a formatted Excel workbook. It identifies records to investigate while preserving the source. The score measures **configured rule compliance, not absolute data correctness**; it is not a claim of financial accuracy or verified customer identity.

## Sample demonstration

`examples/portfolio_10000.csv` contains 10,000 generated account records: synthetic account labels, generated IDs, amounts, signup dates, and statuses. Emails use `example.com` or an invalid placeholder. No real personal or confidential data is used. Seed `20261113` and deterministic defect schedules make the example reproducible.

After installing `requirements.txt` in the project environment:

```bash
python audit.py examples/portfolio_10000.csv --config examples/portfolio_rules.json --output portfolio_reports
```

To regenerate/check the fixture, measure the CLI, and validate all four outputs:

```bash
python scripts/run_portfolio_demo.py
python -m unittest discover -s tests -v
```

Open [the Excel workbook](portfolio_reports/report.xlsx) for stakeholder review; use [the CSV](portfolio_reports/issues.csv) for remediation work and [the JSON](portfolio_reports/summary.json) for automation.

## Observed results

| Measure | Result |
| --- | ---: |
| Data records | 10,000 |
| Missing required cells | 389 |
| Duplicate IDs (later occurrences) | 103 |
| Invalid numeric values | 112 |
| Date-format/calendar errors | 120 |
| Invalid categorical values | 126 |
| Invalid email syntax | 55 |
| Total issue records | 905 |
| Distinct affected records | 897 |
| Passing records | 9,103 |
| Rule compliance score | 91.03/100 |
| Final measured CLI elapsed time | 1.459661 seconds |

Timing covers one Windows/Python 3.13.15 subprocess run, including startup and all report writes; it excludes generation and verification. It is not a multi-run benchmark or a client performance commitment. All **24 existing automated tests passed in 4.213 seconds**. openpyxl verified worksheet names/dimensions, stored score values, all 905 issue records, column metrics, rules, and cross-report consistency. Visual Excel rendering has **not** been verified. Evidence and limits are in [TEST_RESULTS.md](TEST_RESULTS.md) and [verification.json](portfolio_reports/verification.json).

## Potential paid-client deliverables

- An agreed data-quality rule specification and configuration for a client's export schema.
- A read-only baseline audit, Excel review pack, and prioritized remediation recommendations.
- A repeatable validation command and handover documentation for the client's team.
- A follow-up comparison after the client approves and performs corrections.

Scheduling, production deployment, domain-specific checks, large-file streaming, and any data correction would require separate scope and validation. The current tool loads data into memory and does not establish email deliverability, numeric business ranges, or absolute data correctness.
