# Timetable Validation & Constraint Verification Report

**Overall Verification Result**: FAIL :x:

## Overview Metrics
- **Constraint Satisfaction Rate**: 88.06%
- **Timetable Fitness Score**: 80.6%
- **Total Schedule Allocations**: 67
- **Total Violations Detected**: 8

## Rule-by-Rule Analysis
| Rule Name | Type | Status | Summary of Findings |
| :--- | :--- | :--- | :--- |
| Faculty Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Room Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Lab Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Section Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Faculty Workload | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Consecutive Practicals | Hard | :x: FAIL | Course ISC506 on Day 1 for Section IS5A crosses a break or lunch boundary (periods: [2, 3, 7]).; Course ISC507 on Day 1 for Section IS5A crosses a break or lunch boundary (periods: [4, 5, 6]). |
| Department rules | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| AI Rules | Hard | :x: FAIL | AI Rule Violated: section IS5A must avoid Period(s) [1], but scheduled in Period 1 on Day 2 for Section IS5A.; AI Rule Violated: Course ISC510 must have at least one session scheduled during preferred slot(s) ['Fri P7'] for Section IS5A, but none were found. |

## Conflict Explanations & Exploded Diagnostics
### Consecutive Practicals - FAIL
- Course ISC506 on Day 1 for Section IS5A crosses a break or lunch boundary (periods: [2, 3, 7]).
- Course ISC507 on Day 1 for Section IS5A crosses a break or lunch boundary (periods: [4, 5, 6]).
- Course ISC508 on Day 2 for Section IS5A crosses a break or lunch boundary (periods: [1, 2, 3]).

### AI Rules - FAIL
- AI Rule Violated: section IS5A must avoid Period(s) [1], but scheduled in Period 1 on Day 2 for Section IS5A.
- AI Rule Violated: Course ISC510 must have at least one session scheduled during preferred slot(s) ['Fri P7'] for Section IS5A, but none were found.

## Suggested Rule Relaxations
- Suggested Repair: Move conflicting session from current slot to Day 1 Period 6 Room JB402.
- Suggested Repair: Move conflicting session from current slot to Day 1 Period 6 Room JB403.
- Suggested Repair: Move conflicting session from current slot to Day 1 Period 6 Room JB404.

