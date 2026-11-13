import tempfile
import unittest
from pathlib import Path
from audit import audit_csv, write_reports

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'test.csv'
        self.path.write_text('id,email,amount\n1,a@example.com,3\n1,bad,NaN\n1,bad,NaN\n2,,x\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_quality_issues(self):
        r = audit_csv(self.path, required=['id', 'email'], unique=['id'], numeric=['amount'])
        self.assertEqual(r['rows'], 4)
        self.assertEqual(r['duplicate_rows'], 1)
        self.assertEqual(r['duplicate_keys'], 2)
        self.assertEqual(r['invalid_numeric_by_column']['amount'], 3)
        self.assertEqual(r['missing_by_column']['email'], 1)
        self.assertEqual(r['invalid_email_by_column']['email'], 2)

    def test_reports_and_unchanged_input(self):
        before = self.path.read_bytes()
        write_reports(audit_csv(self.path, numeric=['amount']), Path(self.tmp.name) / 'output')
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue((Path(self.tmp.name) / 'output' / 'issues.csv').exists())

    def test_unknown_column(self):
        with self.assertRaisesRegex(ValueError, 'Columns not found'):
            audit_csv(self.path, numeric=['not_a_column'])

if __name__ == '__main__':
    unittest.main()
