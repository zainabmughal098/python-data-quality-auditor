"""V2 regression and integration tests. Every fixture is synthetic."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from audit import audit_csv, load_rules, validate_rules, write_reports


ROOT = Path(__file__).resolve().parents[1]


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'synthetic.csv'

    def data(self, text, **kwargs):
        self.path.write_text(text, encoding='utf-8')
        before = self.path.read_bytes()
        result = audit_csv(self.path, **kwargs)
        self.assertEqual(self.path.read_bytes(), before)
        return result

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'audit.py'), *map(str, args)],
                              capture_output=True, text=True, cwd=self.root)

    def test_missing_whitespace_short_rows_and_optional(self):
        r = self.data('id,name,optional\n1, ,\n2\n', required=['name'])
        self.assertEqual(r['missing_by_column'], {'name': 2, 'optional': 2})
        self.assertEqual(r['issue_count'], 2)
        self.assertEqual(r['quality_score']['score'], 0)
        r = self.data('id,name\n1, \n')
        self.assertEqual(r['quality_score']['score'], 100)

    def test_composite_duplicates_blank_keys_and_exact_rows(self):
        r = self.data('a,b\nx,y\nx,z\n x , y \n,z\n,z\n', unique=['a', 'b'])
        self.assertEqual(r['duplicate_keys'], 1)
        self.assertEqual(r['duplicate_rows'], 1)

    def test_numeric_edge_cases(self):
        values = ['0', '-1.5', '1e3', ' +2 ', 'NaN', 'inf', '-Infinity', '1e999', 'bad', '1,000', '']
        self.path.write_text('', encoding='utf-8')
        with self.path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'n'])
            writer.writerows(enumerate(values))
        r = audit_csv(self.path, numeric=['n'])
        self.assertEqual(r['invalid_numeric_by_column'], {'n': 6})
        self.assertEqual(r['missing_by_column'], {'n': 1})

    def test_dates_exact_format_leap_year_and_missing(self):
        r = self.data('id,date\n1,2024-02-29\n2,2023-02-29\n3,2024-2-09\n4,2024-13-01\n5,29/02/2024\n6,\n7, 0001-01-01 \n',
                      rules={'dates': {'date': '%Y-%m-%d'}})
        self.assertEqual(r['invalid_date_by_column'], {'date': 4})
        self.assertEqual(r['missing_by_column'], {'date': 1})
        r = self.data('date\n31/12/2024\n12/31/2024\n', rules={'dates': {'date': '%d/%m/%Y'}})
        self.assertEqual(r['invalid_date_by_column'], {'date': 1})

    def test_allowed_values_exact_case_trim_unicode_and_empty(self):
        r = self.data('id,status\n1, ready \n2,Ready\n3,été\n4,\n',
                      rules={'allowed_values': {'status': ['ready', 'été']}})
        self.assertEqual(r['allowed_value_violations_by_column'], {'status': 1})
        r = self.data('s\nx\n', rules={'allowed_values': {'s': []}})
        self.assertEqual(r['issue_count'], 1)

    def test_score_multiple_issues_count_row_once(self):
        r = self.data('id,email,n\n1,bad,NaN\n2,a@example.com,1\n3,b@example.com,2\n', numeric=['n'])
        self.assertEqual(r['issue_count'], 2)
        self.assertEqual(r['quality_score']['score'], 66.67)
        self.assertEqual(r['quality_score']['affected_rows'], 1)
        self.assertEqual(r['quality_score']['passing_rows'], 2)

    def test_header_only_score_and_workbook(self):
        r = self.data('id,date\n', rules={'dates': {'date': '%Y-%m-%d'}})
        self.assertEqual(r['quality_score']['score'], 100)
        self.assertEqual(r['quality_score']['total_rows'], 0)
        write_reports(r, self.root / 'reports')
        wb = load_workbook(self.root / 'reports/report.xlsx')
        self.addCleanup(wb.close)
        self.assertEqual(wb['Issues'].max_row, 1)

    def test_extra_fields_and_multiline_record_numbers(self):
        r = self.data('id,name\n1,"two\nlines"\n2,x,extra\n')
        self.assertEqual(r['issues'][0]['issue'], 'extra_fields')
        self.assertEqual(r['issues'][0]['csv_line'], 3)

    def test_reject_empty_and_duplicate_headers(self):
        for text in ('', 'a,a\n1,2\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.data(text)

    def test_bom_and_crlf(self):
        r = self.data('\ufeffid,date\r\n1,2024-01-01\r\n', rules={'dates': {'date': '%Y-%m-%d'}})
        self.assertEqual(r['columns'], ['id', 'date'])
        self.assertEqual(r['issue_count'], 0)

    def test_unknown_columns_all_rule_types(self):
        for rules in ({'required': ['x']}, {'unique': ['x']}, {'numeric': ['x']},
                      {'dates': {'x': '%Y-%m-%d'}}, {'allowed_values': {'x': []}}):
            with self.subTest(rules=rules), self.assertRaisesRegex(ValueError, 'Columns not found'):
                self.data('id\n1\n', rules=rules)

    def test_invalid_configuration(self):
        cases = [[], None, {'typo': []}, {'required': 'id'}, {'numeric': [1]},
                 {'unique': ['']}, {'dates': []}, {'dates': {'d': '%Q'}},
                 {'dates': {'d': '%Y-%m'}}, {'dates': {'d': '%Y-%m-%d %H'}},
                 {'dates': {'d': 1}}, {'allowed_values': {'s': 'ok'}},
                 {'allowed_values': {'s': [1]}}, {'allowed_values': {'': []}}]
        for rules in cases:
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                validate_rules(rules)

    def test_load_config_and_cli_rules_merge(self):
        config = self.root / 'rules.json'
        config.write_text(json.dumps({'required': ['id'], 'numeric': ['n'],
                                      'dates': {'d': '%Y-%m-%d'}, 'allowed_values': {'s': ['ok']}}))
        self.assertEqual(load_rules(config)['required'], ['id'])
        self.data('id,n,d,s\n1,x,no,bad\n')
        before = self.path.read_bytes(), config.read_bytes()
        completed = self.cli(self.path, '--config', config, '--required', 's', '--output', self.root / 'out')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        r = json.loads((self.root / 'out/summary.json').read_text())
        self.assertEqual(r['rules']['required'], ['id', 's'])
        self.assertEqual(r['issue_count'], 3)
        self.assertEqual(before, (self.path.read_bytes(), config.read_bytes()))

    def test_legacy_cli_and_version(self):
        self.data('id,email,n\n1,bad,x\n')
        p = self.cli(self.path, '--required', 'id', '--unique', 'id', '--numeric', 'n', '--output', self.root / 'out')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('found 2 issue records', p.stdout)
        self.assertEqual(self.cli('--version').stdout.strip(), '2.0.0')

    def test_cli_bad_json_unknown_rules_and_missing_file(self):
        self.data('id\n1\n')
        config = self.root / 'bad.json'
        for text in ('{', '{"typo": []}', '{"dates": {"absent": "%Y-%m-%d"}}'):
            config.write_text(text)
            p = self.cli(self.path, '--config', config)
            self.assertEqual(p.returncode, 2)
            self.assertIn('Error:', p.stderr)
            self.assertNotIn('Traceback', p.stderr)
        self.assertEqual(self.cli(self.root / 'absent.csv').returncode, 2)

    def test_cli_refuses_source_and_config_collision(self):
        self.path = self.root / 'issues.csv'
        self.data('id\n1\n')
        before = self.path.read_bytes()
        p = self.cli(self.path, '--output', self.root)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(self.path.read_bytes(), before)
        config = self.root / 'summary.json'
        config.write_text('{}')
        p = self.cli(self.path, '--config', config, '--output', self.root)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(config.read_text(), '{}')

    def test_all_reports_content_formatting_and_literal_excel_values(self):
        r = self.data('id,n,s\n1,no,=1+1\n2,3,ok\n', numeric=['n'], rules={'allowed_values': {'s': ['ok']}})
        out = self.root / 'reports'
        write_reports(r, out)
        self.assertEqual(json.loads((out / 'summary.json').read_text()), r)
        with (out / 'issues.csv').open(newline='', encoding='utf-8') as f:
            issues = list(csv.DictReader(f))
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[1]['value'], '=1+1')
        md = (out / 'report.md').read_text(encoding='utf-8')
        self.assertIn('50.00/100', md)
        self.assertIn(r['quality_score']['formula'], md)
        wb = load_workbook(out / 'report.xlsx', data_only=False)
        self.addCleanup(wb.close)
        self.assertEqual(wb.sheetnames, ['Summary', 'Columns', 'Issues', 'Rules'])
        self.assertEqual(wb['Summary']['B9'].value, 50)
        self.assertEqual(wb['Columns']['C2'].value, 0)
        self.assertEqual(wb['Issues']['D3'].value, '=1+1')
        self.assertEqual(wb['Issues']['D3'].data_type, 's')
        for ws in wb:
            self.assertEqual(ws.freeze_panes, 'A2')
            self.assertTrue(ws.auto_filter.ref)
            self.assertTrue(ws['A1'].font.bold)
            self.assertEqual(ws['A1'].fill.fgColor.rgb, '0017365D')

    def test_excel_control_characters_and_cell_limit(self):
        r = self.data('s\nbad\x01value\n', rules={'allowed_values': {'s': []}})
        out = self.root / 'reports'
        write_reports(r, out)
        wb = load_workbook(out / 'report.xlsx')
        self.addCleanup(wb.close)
        self.assertEqual(wb['Issues']['D2'].value, r'bad\x01value')
        self.assertEqual(json.loads((out / 'summary.json').read_text())['issues'][0]['value'], 'bad\x01value')
        r = self.data('s\n' + 'x' * 32768 + '\n', rules={'allowed_values': {'s': []}})
        with self.assertRaisesRegex(ValueError, 'cell text limit'):
            write_reports(r, self.root / 'oversized')
        self.assertFalse((self.root / 'oversized/summary.json').exists())

    def test_report_api_refuses_source_collision(self):
        self.path = self.root / 'issues.csv'
        r = self.data('id\n1\n')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'overwrite an input'):
            write_reports(r, self.root)
        self.assertEqual(self.path.read_bytes(), before)

    def test_effective_rules_do_not_mutate_configuration(self):
        rules = {'required': ['id'], 'numeric': ['n']}
        r = self.data('id,n\n1,2\n', required=['id', 'n'], rules=rules)
        self.assertEqual(rules, {'required': ['id'], 'numeric': ['n']})
        self.assertEqual(r['rules']['required'], ['id', 'n'])
        self.assertEqual(r['quality_score']['score'], 100)

    def test_reporting_legacy_result_still_works(self):
        r = self.data('id\n1\n')
        legacy_fields = ['file', 'rows', 'columns', 'missing_by_column', 'invalid_numeric_by_column',
                         'invalid_email_by_column', 'duplicate_rows', 'duplicate_keys', 'issues', 'issue_count']
        write_reports({k: r[k] for k in legacy_fields}, self.root / 'legacy')
        self.assertTrue((self.root / 'legacy/report.xlsx').exists())
        self.assertIn('# CSV Data Quality Audit', (self.root / 'legacy/report.md').read_text())


if __name__ == '__main__':
    unittest.main()
