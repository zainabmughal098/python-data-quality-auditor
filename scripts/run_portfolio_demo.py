"""Reproduce the synthetic release demonstration without changing the auditor.

Run from the repository root: python scripts/run_portfolio_demo.py
Only the CLI subprocess is timed. Existing dataset bytes must match the generator.
The dedicated portfolio_reports directory is refreshed on each run.
"""
import csv
import hashlib
import io
import json
import platform
import random
import subprocess
import sys
import time
from collections import Counter
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[1]
DATA = Path('examples/portfolio_10000.csv')
RULES = Path('examples/portfolio_rules.json')
OUTPUT = Path('portfolio_reports')
SEED = 20261113
FIELDS = ['customer_id', 'name', 'email', 'amount', 'joined_on', 'status']


def check(condition, message):
    if not condition:
        raise ValueError(message)


def generate():
    rng = random.Random(SEED)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(FIELDS)
    expected = Counter()
    affected = set()
    missing = Counter()
    for i in range(1, 10001):
        row = [f'SYN{i:06d}', f'Synthetic Account {i:05d}',
               f'account{i:05d}@example.com', f'{rng.randint(500, 2500000) / 100:.2f}',
               (date(2023, 1, 1) + timedelta(days=rng.randrange(1096))).isoformat(),
               rng.choice(['active', 'active', 'active', 'inactive'])]
        errors = []
        if i % 97 == 0:
            row[0] = 'SYN000001'
            errors.append('duplicate_key')
        if i % 89 == 0:
            row[3] = ['NaN', 'Infinity', 'not-a-number', '1,234.56'][(i // 89) % 4]
            errors.append('invalid_numeric')
        if i % 83 == 0:
            row[4] = ['2023-02-29', '2024-13-01', '31/12/2024', '2024-2-09'][(i // 83) % 4]
            errors.append('invalid_date_format')
        if i % 79 == 0:
            row[5] = ['pending', 'ACTIVE', 'unknown'][(i // 79) % 3]
            errors.append('allowed_value_violation')
        if i % 181 == 0:
            row[2] = 'invalid-email'
            errors.append('invalid_email_format')
        # These divisors do not overlap the corresponding malformed-value
        # divisors within 10,000 records, so no injected defect is overwritten.
        for column, divisor in enumerate([503, 131, 113, 127, 149, 163]):
            if i % divisor == 0:
                row[column] = ' ' if i % 2 else ''
                errors.append('missing_required')
                missing[FIELDS[column]] += 1
        expected.update(errors)
        if errors:
            affected.add(i)
        writer.writerow(row)
    return buffer.getvalue().encode('utf-8'), expected, affected, missing


def verify_reports(expected, affected, missing):
    out = ROOT / OUTPUT
    result = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
    check(result['rows'] == 10000 and result['columns'] == FIELDS, 'Input dimensions differ')
    check(Counter(i['issue'] for i in result['issues']) == expected, 'Injected defects differ from issue counts')
    check({i['csv_line'] - 1 for i in result['issues']} == affected, 'Affected records differ from injection plan')
    check(result['missing_by_column'] == dict(missing), 'Missing-cell metrics differ')
    check(result['duplicate_rows'] == 0, 'Unexpected exact duplicates')
    check(result['duplicate_keys'] == expected['duplicate_key'], 'Duplicate-key metrics differ')
    for key, col, issue in [('invalid_numeric_by_column', 'amount', 'invalid_numeric'),
                            ('invalid_email_by_column', 'email', 'invalid_email_format'),
                            ('invalid_date_by_column', 'joined_on', 'invalid_date_format'),
                            ('allowed_value_violations_by_column', 'status', 'allowed_value_violation')]:
        check(result[key] == {col: expected[issue]}, f'{key} differs')
    score = result['quality_score']
    check(score['total_rows'] == 10000 and score['affected_rows'] == len(affected), 'Score inputs differ')
    check(score['passing_rows'] == 10000 - len(affected), 'Passing rows differ')
    check(score['score'] == round(100 * (10000 - len(affected)) / 10000, 2), 'Score differs')
    check(result['issue_count'] == len(result['issues']) == sum(expected.values()), 'Issue total differs')
    configured = json.loads((ROOT / RULES).read_text(encoding='utf-8'))
    check(result['rules'] == configured, 'Effective rules differ')
    with (out / 'issues.csv').open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        check(reader.fieldnames == ['csv_line', 'column', 'issue', 'value'], 'CSV schema changed')
        records = list(reader)
    check(records == [{k: str(v) for k, v in issue.items()} for issue in result['issues']], 'CSV/JSON issue details differ')
    md = (out / 'report.md').read_text(encoding='utf-8')
    for text in [f"**Rows:** {result['rows']}", f"**Issue records:** {result['issue_count']}",
                 f"**Score:** {score['score']:.2f}/100", f"**Affected rows:** {len(affected)} of 10000", score['formula']]:
        check(text in md, f'Markdown missing {text}')

    wb = openpyxl.load_workbook(out / 'report.xlsx', data_only=False)
    try:
        check(wb.sheetnames == ['Summary', 'Columns', 'Issues', 'Rules'], 'Worksheet names differ')
        dimensions = {ws.title: ws.calculate_dimension() for ws in wb}
        check(dimensions == {'Summary': 'A1:B13', 'Columns': 'A1:F7',
                             'Issues': f"A1:D{result['issue_count'] + 1}", 'Rules': 'A1:B6'}, 'Worksheet dimensions differ')
        summary = dict(wb['Summary'].iter_rows(min_row=2, values_only=True))
        for name, value in {'File': result['file'], 'Version': result['version'], 'Rows': 10000,
                            'Columns': 6, 'Issue records': result['issue_count'], 'Duplicate rows': 0,
                            'Duplicate keys': expected['duplicate_key'], 'Quality score (0-100)': score['score'],
                            'Affected rows': len(affected), 'Passing rows': score['passing_rows'],
                            'Score formula': score['formula']}.items():
            check(summary[name] == value, f'Excel summary differs: {name}')
        keys = ['missing_by_column', 'invalid_numeric_by_column', 'invalid_email_by_column',
                'invalid_date_by_column', 'allowed_value_violations_by_column']
        check(list(wb['Columns'].values)[1:] == [tuple([c] + [result[k].get(c, 0) for k in keys]) for c in FIELDS],
              'Excel column metrics differ')
        # openpyxl reloads deliberately empty text cells as None.
        excel_issues = [tuple('' if v is None else v for v in row) for row in list(wb['Issues'].values)[1:]]
        check(excel_issues == [tuple(i[k] for k in ['csv_line', 'column', 'issue', 'value']) for i in result['issues']],
              'Excel issue details differ')
        check({k: json.loads(v) for k, v in list(wb['Rules'].values)[1:]} == configured, 'Excel rules differ')
        formula_count = sum(cell.data_type == 'f' for ws in wb for row in ws for cell in row)
        check(formula_count == 0, 'Unexpected executable workbook formulas')
        for ws in wb:
            check(ws.freeze_panes == 'A2' and ws.auto_filter.ref == ws.dimensions, 'Worksheet filters/freeze differ')
            check(ws['A1'].font.bold and ws['A1'].fill.fgColor.rgb == '0017365D', 'Heading style differs')
    finally:
        wb.close()
    cached = openpyxl.load_workbook(out / 'report.xlsx', data_only=True)
    try:
        check(cached['Summary']['B9'].value == score['score'], 'Score is not available as a stored value')
    finally:
        cached.close()
    return result, dimensions, formula_count


def main():
    generated, expected, affected, missing = generate()
    dataset = ROOT / DATA
    if dataset.exists():
        check(dataset.read_bytes() == generated, 'Existing demo dataset differs; refusing to overwrite it')
    else:
        dataset.write_bytes(generated)
    source_hash = hashlib.sha256(generated).hexdigest()
    rules_before = (ROOT / RULES).read_bytes()
    command = [sys.executable, 'audit.py', DATA.as_posix(), '--config', RULES.as_posix(), '--output', OUTPUT.as_posix()]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    check(completed.returncode == 0, completed.stderr or completed.stdout)
    check(dataset.read_bytes() == generated and (ROOT / RULES).read_bytes() == rules_before, 'Input changed during audit')
    result, dimensions, formula_count = verify_reports(expected, affected, missing)
    files = {}
    for name in ['summary.json', 'issues.csv', 'report.md', 'report.xlsx']:
        data = (ROOT / OUTPUT / name).read_bytes()
        files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    evidence = {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(), 'openpyxl': openpyxl.__version__, 'platform': platform.platform(),
        'dataset': DATA.as_posix(), 'rows': 10000, 'seed': SEED, 'source_sha256': source_hash,
        'command': ['python'] + command[1:], 'exit_code': completed.returncode,
        'cli_stdout': completed.stdout.strip(), 'elapsed_seconds': elapsed,
        'timing_scope': 'One wall-clock CLI subprocess run including interpreter startup and all four report writes; excludes dataset generation and verification. Not a benchmark distribution.',
        'issue_count': result['issue_count'], 'issues_by_type': dict(sorted(expected.items())),
        'missing_by_column': dict(missing), 'quality_score': result['quality_score'],
        'workbook_dimensions': dimensions, 'executable_formula_cells': formula_count,
        'stored_score_value_verified': True, 'all_issue_records_match_csv_json_xlsx': True,
        'injection_plan_matches_report': True, 'source_and_rules_unchanged': True,
        'visual_excel_rendering_verified': False, 'outputs': files,
    }
    (ROOT / OUTPUT / 'verification.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
