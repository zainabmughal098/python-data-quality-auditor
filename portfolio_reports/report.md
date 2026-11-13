# CSV Data Quality Audit

**File:** portfolio_10000.csv
**Rows:** 10000
**Columns:** 6
**Issue records:** 905
**Exact duplicate rows:** 0
**Duplicate nonblank keys:** 103

## Missing values by column

- customer_id: 19
- name: 76
- email: 88
- amount: 78
- joined_on: 67
- status: 61

## Data quality score

**Score:** 91.03/100
**Affected rows:** 897 of 10000
Formula: `round(100 * (total_rows - affected_rows) / total_rows, 2); 100 for zero rows`.
Each row counts once regardless of issue count. Optional missing cells do not fail a row.
A header-only file scores 100 by convention; it contains no observations.

## Validation rules

```json
{
  "required": [
    "customer_id",
    "name",
    "email",
    "amount",
    "joined_on",
    "status"
  ],
  "unique": [
    "customer_id"
  ],
  "numeric": [
    "amount"
  ],
  "dates": {
    "joined_on": "%Y-%m-%d"
  },
  "allowed_values": {
    "status": [
      "active",
      "inactive"
    ]
  }
}
```

## Validation failures by column

| Column | Numeric | Email | Date | Allowed values |
| --- | ---: | ---: | ---: | ---: |
| customer_id | 0 | 0 | 0 | 0 |
| name | 0 | 0 | 0 | 0 |
| email | 0 | 55 | 0 | 0 |
| amount | 112 | 0 | 0 | 0 |
| joined_on | 0 | 0 | 120 | 0 |
| status | 0 | 0 | 0 | 126 |

## Notes

This audit does not modify the input file. An issue record is not necessarily a unique affected row.
Email checks are basic syntax checks, not deliverability verification.
For large datasets, this starter implementation loads the CSV into memory.
