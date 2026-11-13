# CSV Data Quality Audit

**File:** customers.csv
**Rows:** 7
**Columns:** 4
**Issue records:** 6
**Exact duplicate rows:** 1
**Duplicate nonblank keys:** 1

## Missing values by column

- customer_id: 0
- name: 0
- email: 1
- amount: 1

## Notes

This audit does not modify the input file. An issue record is not necessarily a unique affected row.
Email checks are basic syntax checks, not deliverability verification.
For large datasets, this starter implementation loads the CSV into memory.
