# Timetable Validation & Constraint Verification Report

**Overall Verification Result**: FAIL :x:

## Overview Metrics
- **Constraint Satisfaction Rate**: 50.0%
- **Timetable Fitness Score**: 85.0%
- **Total Schedule Allocations**: 2
- **Total Violations Detected**: 1

## Rule-by-Rule Analysis
| Rule Name | Type | Status | Summary of Findings |
| :--- | :--- | :--- | :--- |
| Faculty Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Room Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Lab Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Section Clash | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Faculty Workload | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Consecutive Practicals | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| Department rules | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |
| AI Rules | Hard | :white_check_mark: PASS | Satisfied with zero clashes. |

## Conflict Explanations & Exploded Diagnostics
## Suggested Rule Relaxations
- Suggested Repair: Move conflicting session from current slot to Day 1 Period 1 Room L201.

