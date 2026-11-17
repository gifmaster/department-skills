# Worked example: hr-pay-gap-analysis

## Request

> Test run before we do the full company: anonymised payroll for 19 people at our Odense office, categories are our job families which we treat as equal value. What are the gaps and is anything above 5%?

## Command (run from the skill's automation folder)

```
python3 scripts/paygap.py assets/payroll_template.csv
```

## Output

# Gender pay gap analysis

19 employees in the binary gap figures (11 men, 8 women). Pay normalised to hourly: annual pay / (hours per week x 52). Gap = (men - women) / men. Positive means men are paid more.

## Pay gap metrics

| Metric | Men | Women | Gap |
|---|---|---|---|
| Mean hourly base pay | 283.74 | 251.26 | 11.4% |
| Median hourly base pay | 280.67 | 212.32 | 24.4% |
| Mean hourly total pay | 310.20 | 259.53 | 16.3% |
| Median hourly total pay | 301.46 | 213.92 | 29.0% |
| Share receiving variable pay | 90.9% | 62.5% |  |

## Categories of equal work or work of equal value

| Category | Men / women | Mean base gap | Median base gap | Mean total gap | Median total gap | Flag |
|---|---|---|---|---|---|---|
| Kundeservice | 5 / 5 | 5.1% | 3.6% | 7.5% | 7.7% | mean base pay gap 5.1%; mean total pay gap 7.5% |
| Ledelse | 2 / 1 | suppressed (< 5 of a gender) |  |  |  |  |
| Udvikling | 4 / 2 | suppressed (< 5 of a gender) |  |  |  |  |

## Category gaps at or above 5%

- Kundeservice: mean base pay gap 5.1%; mean total pay gap 7.5%. Needs an objective, gender-neutral justification (for example documented differences in experience, performance or responsibility) or correction.
- 2 categories were suppressed (fewer than 5 women or men) and could not be assessed against the 5% threshold: Ledelse, Udvikling. Review them internally on the full data.

## Pay quartiles (hourly total pay, lowest to highest)

| Quartile | People | Men | Women | Hourly range |
|---|---|---|---|---|
| Q1 | 5 | 1 (20.0%) | 4 (80.0%) | 203.74 - 213.10 |
| Q2 | 5 | 4 (80.0%) | 1 (20.0%) | 214.74 - 244.28 |
| Q3 | 5 | 3 (60.0%) | 2 (40.0%) | 294.47 - 330.04 |
| Q4 | 4 | 3 (75.0%) | 1 (25.0%) | 348.23 - 504.16 |

## Data quality warnings

- S10: variable_pay_annual blank, treated as 0
- Line 21: duplicate employee_ref S03, later row ignored
- At least one pay quartile has fewer than 5 people; quartile shares may identify individuals, do not publish them

## How to read this

- A pay gap is a statistic, not proof of discrimination. Gaps that objective, gender-neutral criteria do not explain must be justified or corrected; under Directive (EU) 2023/970 an unjustified category gap of 5% or more not remedied within six months triggers a joint pay assessment (check the Danish transposition).
- Suppression protects people in small groups in published figures; the full data may still have to be available to workers' representatives and authorities.
- Check that categories really group work of equal value and that all pay components (allowances, overtime, pension, benefits in kind) are included before reporting.

## Interpretation

- Across the 19 people, men's mean hourly base pay is 11.4% higher than women's (16.3% on total pay); the median gaps are larger because the two highest-paid job families are mostly men.
- Kundeservice is the only category large enough to show, and its mean gaps are 5.1% on base and 7.5% on total pay, so it is flagged. Part of the total-pay gap comes from variable pay: 4 of 5 men received some, against 2 of 5 women.
- Udvikling and Ledelse are suppressed because they have fewer than 5 women and fewer than 5 men, so they could not be assessed against the 5% threshold; analyse them internally, do not publish them.
- The 5.1% does not mean discrimination: check whether experience, performance or responsibility documented on objective, gender-neutral criteria explains it, and correct what it does not.
- Fix the duplicate S03 row and confirm S10 had no variable pay before the full run.
