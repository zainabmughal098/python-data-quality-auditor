# CSV Data Quality Audit

**File:** v2_synthetic.csv
**Rows:** 6
**Columns:** 6
**Issue records:** 13
**Exact duplicate rows:** 1
**Duplicate nonblank keys:** 1

## Missing values by column

- customer_id: 0
- name: 0
- email: 1
- amount: 1
- joined_on: 0
- status: 0

## Data quality score

**Score:** 33.33/100
**Affected rows:** 4 of 6
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
| email | 0 | 2 | 0 | 0 |
| amount | 2 | 0 | 0 | 0 |
| joined_on | 0 | 0 | 3 | 0 |
| status | 0 | 0 | 0 | 2 |

## Notes

This audit does not modify the input file. An issue record is not necessarily a unique affected row.
Email checks are basic syntax checks, not deliverability verification.
For large datasets, this starter implementation loads the CSV into memory.
