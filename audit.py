"""Read-only CSV quality audit, version 2. Python 3.10+."""
import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

__version__ = '2.0.0'
SCORE_FORMULA = 'round(100 * (total_rows - affected_rows) / total_rows, 2); 100 for zero rows'
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def validate_rules(rules):
    """Validate the intentionally small JSON schema; reject typos early."""
    if not isinstance(rules, dict):
        raise ValueError('Rules must be a JSON object')
    unknown = set(rules) - {'required', 'unique', 'numeric', 'dates', 'allowed_values'}
    if unknown:
        raise ValueError('Unknown rules: ' + ', '.join(sorted(unknown)))
    result = {}
    for key in ('required', 'unique', 'numeric'):
        values = rules.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f'{key} must be a list of nonblank column names')
        result[key] = list(dict.fromkeys(values))
    for key in ('dates', 'allowed_values'):
        values = rules.get(key, {})
        if not isinstance(values, dict) or any(not isinstance(c, str) or not c.strip() for c in values):
            raise ValueError(f'{key} must map column names to rules')
        result[key] = dict(values)
    for fmt in result['dates'].values():
        # Deliberately restricted to portable, exact calendar-date formats.
        if not isinstance(fmt, str) or any(fmt.count(d) != 1 for d in ('%Y', '%m', '%d')):
            raise ValueError('Date formats must contain %Y, %m, and %d exactly once')
        remainder = re.sub(r'%[Ymd]', '', fmt)
        if '%' in remainder or any(c not in '-/. ' for c in remainder):
            raise ValueError('Date formats support only %Y, %m, %d and separators - / . space')
    for values in result['allowed_values'].values():
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError('allowed_values entries must be lists of strings')
    return result


def load_rules(path):
    return validate_rules(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def audit_csv(path: Path, required=None, unique=None, numeric=None, *, rules=None):
    rules = validate_rules({} if rules is None else rules)
    for key, extra in (('required', required), ('unique', unique), ('numeric', numeric)):
        if extra is not None:
            if not isinstance(extra, list) or any(not isinstance(c, str) or not c.strip() for c in extra):
                raise ValueError(f'{key} must be a list of nonblank column names')
            rules[key] = list(dict.fromkeys(rules[key] + extra))
    required, unique, numeric = (rules[k] for k in ('required', 'unique', 'numeric'))
    path = Path(path)
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError('CSV must have a header row')
        if len(set(headers)) != len(headers):
            raise ValueError('CSV has duplicate column names')
        rows = list(reader)
    missing_columns = sorted(set(required + unique + numeric + list(rules['dates']) + list(rules['allowed_values'])) - set(headers))
    if missing_columns:
        raise ValueError('Columns not found: ' + ', '.join(missing_columns))
    missing = Counter()
    invalid_numeric = Counter()
    invalid_email = Counter()
    invalid_date = Counter()
    invalid_allowed = Counter()
    duplicate_rows = 0
    seen_rows = set()
    seen_keys = set()
    duplicate_keys = 0
    issues = []
    for index, row in enumerate(rows, start=2):
        if None in row:
            issues.append({'csv_line': index, 'column': '*', 'issue': 'extra_fields', 'value': ''})
        signature = tuple((col, row.get(col)) for col in headers)
        if signature in seen_rows:
            duplicate_rows += 1
            issues.append({'csv_line': index, 'column': '*', 'issue': 'duplicate_row', 'value': ''})
        seen_rows.add(signature)
        for col in headers:
            value = row.get(col)
            if value is None or not value.strip():
                missing[col] += 1
                if col in required:
                    issues.append({'csv_line': index, 'column': col, 'issue': 'missing_required', 'value': ''})
                continue
            value = value.strip()
            if col in numeric:
                try:
                    if not math.isfinite(float(value)):
                        raise ValueError('non-finite')
                except ValueError:
                    invalid_numeric[col] += 1
                    issues.append({'csv_line': index, 'column': col, 'issue': 'invalid_numeric', 'value': value})
            if col.lower() == 'email' and not EMAIL.fullmatch(value):
                invalid_email[col] += 1
                issues.append({'csv_line': index, 'column': col, 'issue': 'invalid_email_format', 'value': value})
            if col in rules['dates']:
                fmt = rules['dates'][col]
                try:
                    parsed = datetime.strptime(value, fmt)
                    # strptime accepts unpadded month/day; enforce the configured spelling.
                    expected = fmt.replace('%Y', f'{parsed.year:04d}').replace('%m', f'{parsed.month:02d}').replace('%d', f'{parsed.day:02d}')
                    if value != expected:
                        raise ValueError('Date does not match exact format')
                except ValueError:
                    invalid_date[col] += 1
                    issues.append({'csv_line': index, 'column': col, 'issue': 'invalid_date_format', 'value': value})
            if col in rules['allowed_values'] and value not in rules['allowed_values'][col]:
                invalid_allowed[col] += 1
                issues.append({'csv_line': index, 'column': col, 'issue': 'allowed_value_violation', 'value': value})
        if unique:
            key = tuple((row.get(col) or '').strip() for col in unique)
            if all(key):
                if key in seen_keys:
                    duplicate_keys += 1
                    issues.append({'csv_line': index, 'column': ','.join(unique), 'issue': 'duplicate_key', 'value': '|'.join(key)})
                seen_keys.add(key)
    affected = len({issue['csv_line'] for issue in issues})
    return {'file': path.name, 'source_path': str(path.resolve()), 'rows': len(rows), 'columns': headers,
            'missing_by_column': dict(missing), 'invalid_numeric_by_column': dict(invalid_numeric),
            'invalid_email_by_column': dict(invalid_email), 'duplicate_rows': duplicate_rows,
            'duplicate_keys': duplicate_keys, 'issues': issues,
            'issue_count': len(issues), 'version': __version__, 'rules': rules,
            'invalid_date_by_column': dict(invalid_date),
            'allowed_value_violations_by_column': dict(invalid_allowed),
            'quality_score': {'score': round(100 * (len(rows) - affected) / len(rows), 2) if rows else 100.0,
                              'total_rows': len(rows), 'affected_rows': affected,
                              'passing_rows': len(rows) - affected, 'formula': SCORE_FORMULA}}


def write_excel(result, path):
    """Create a formatted workbook; imported lazily to keep the audit API lightweight."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    score = result.get('quality_score', {})
    sheets = {
        'Summary': [['Metric', 'Value'], ['File', result['file']], ['Version', result.get('version', '1')],
                    ['Rows', result['rows']], ['Columns', len(result['columns'])],
                    ['Issue records', result['issue_count']], ['Duplicate rows', result['duplicate_rows']],
                    ['Duplicate keys', result['duplicate_keys']], ['Quality score (0-100)', score.get('score')],
                    ['Affected rows', score.get('affected_rows')], ['Passing rows', score.get('passing_rows')],
                    ['Score formula', score.get('formula', SCORE_FORMULA)],
                    ['Score scope', 'Only reported issues count. Optional missing cells are counted, but do not fail a row. Zero rows means no observations.']],
        'Columns': [['Column', 'Missing', 'Invalid numeric', 'Invalid email', 'Invalid date', 'Allowed-value violations']] +
                   [[c] + [result.get(k, {}).get(c, 0) for k in ('missing_by_column', 'invalid_numeric_by_column', 'invalid_email_by_column', 'invalid_date_by_column', 'allowed_value_violations_by_column')] for c in result['columns']],
        'Issues': [['CSV record', 'Column', 'Issue', 'Value']] +
                  [[i[k] for k in ('csv_line', 'column', 'issue', 'value')] for i in result['issues']],
        'Rules': [['Rule', 'Configuration']] + [[k, json.dumps(v, ensure_ascii=False)] for k, v in result.get('rules', {}).items()]
    }
    for title, records in sheets.items():
        if len(records) > 1_048_576:
            raise ValueError('Excel row limit exceeded; reduce input size')
        ws = wb.create_sheet(title)
        for record in records:
            cleaned = []
            for value in record:
                if isinstance(value, str):
                    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', lambda m: f'\\x{ord(m[0]):02x}', value)
                    if len(value) > 32767:
                        raise ValueError('Excel cell text limit exceeded')
                cleaned.append(value)
            ws.append(cleaned)
        for row in ws:
            for cell in row:
                if isinstance(cell.value, str):
                    # Force literal text, including strings beginning with '='.
                    cell.data_type = 's'
                cell.alignment = Alignment(vertical='top', wrap_text=True)
            if row[0].row % 2 == 0:
                for cell in row:
                    cell.fill = PatternFill('solid', fgColor='EEF3F8')
        for cell in ws[1]:
            cell.fill = PatternFill('solid', fgColor='17365D')
            cell.font = Font(color='FFFFFF', bold=True)
        ws.row_dimensions[1].height = 28
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = '1:1'
        for column in ws.columns:
            width = min(65, max(18, max(len(str(c.value or '')) for c in column) + 2))
            ws.column_dimensions[get_column_letter(column[0].column)].width = width
    wb['Summary']['B9'].number_format = '0.00" / 100"'
    wb['Summary'].row_dimensions[12].height = 42
    wb['Summary'].row_dimensions[13].height = 60
    wb['Summary'].conditional_formatting.add('B9', ColorScaleRule(start_type='num', start_value=0, start_color='F8696B', end_type='num', end_value=100, end_color='63BE7B'))
    wb.save(path)


def write_reports(result, output: Path):
    output = Path(output)
    if 'source_path' in result:
        source = Path(result['source_path'])
        for name in ('summary.json', 'issues.csv', 'report.md', 'report.xlsx'):
            target = output / name
            if target.resolve() == source.resolve() or (target.exists() and source.exists() and target.samefile(source)):
                raise ValueError('Report output would overwrite an input file')
    output.mkdir(parents=True, exist_ok=True)
    # Render Excel first so a missing dependency cannot silently omit that report.
    write_excel(result, output / 'report.xlsx')
    (output / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with (output / 'issues.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['csv_line', 'column', 'issue', 'value'])
        writer.writeheader()
        writer.writerows(result['issues'])
    lines = ['# CSV Data Quality Audit', '', f"**File:** {result['file']}",
             f"**Rows:** {result['rows']}", f"**Columns:** {len(result['columns'])}",
             f"**Issue records:** {result['issue_count']}",
             f"**Exact duplicate rows:** {result['duplicate_rows']}",
             f"**Duplicate nonblank keys:** {result['duplicate_keys']}", '',
             '## Missing values by column', '']
    lines += [f"- {col}: {result['missing_by_column'].get(col, 0)}" for col in result['columns']]
    if 'quality_score' in result:
        score = result['quality_score']
        lines += ['', '## Data quality score', '', f"**Score:** {score['score']:.2f}/100",
                  f"**Affected rows:** {score['affected_rows']} of {score['total_rows']}",
                  f"Formula: `{score['formula']}`.",
                  'Each row counts once regardless of issue count. Optional missing cells do not fail a row.',
                  'A header-only file scores 100 by convention; it contains no observations.',
                  '', '## Validation rules', '', '```json', json.dumps(result['rules'], indent=2), '```',
                  '', '## Validation failures by column', '',
                  '| Column | Numeric | Email | Date | Allowed values |', '| --- | ---: | ---: | ---: | ---: |']
        for col in result['columns']:
            label = col.replace('|', '\\|').replace('\n', ' ')
            counts = [str(result[k].get(col, 0)) for k in ('invalid_numeric_by_column', 'invalid_email_by_column', 'invalid_date_by_column', 'allowed_value_violations_by_column')]
            lines.append('| ' + ' | '.join([label] + counts) + ' |')
    lines += ['', '## Notes', '', 'This audit does not modify the input file. An issue record is not necessarily a unique affected row.',
              'Email checks are basic syntax checks, not deliverability verification.',
              'For large datasets, this starter implementation loads the CSV into memory.']
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Audit CSV data without modifying source files')
    parser.add_argument('csv_file', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--required', nargs='*', default=[])
    parser.add_argument('--unique', nargs='*', default=[])
    parser.add_argument('--numeric', nargs='*', default=[])
    parser.add_argument('--config', type=Path, help='JSON validation-rule file')
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args()
    try:
        # Refuse output names that would overwrite the source or configuration.
        protected = [args.csv_file] + ([args.config] if args.config else [])
        for name in ('summary.json', 'issues.csv', 'report.md', 'report.xlsx'):
            target = args.output / name
            if any(target.resolve() == p.resolve() or (target.exists() and p.exists() and target.samefile(p)) for p in protected):
                raise ValueError('Report output would overwrite an input file')
        result = audit_csv(args.csv_file, args.required, args.unique, args.numeric,
                           rules=load_rules(args.config) if args.config else None)
        write_reports(result, args.output)
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    print(f"Audited {result['rows']} rows; found {result['issue_count']} issue records. Reports: {args.output}")


if __name__ == '__main__':
    main()
