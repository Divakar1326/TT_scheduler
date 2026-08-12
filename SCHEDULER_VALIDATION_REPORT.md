# Timetable Scheduler Validation Report

**Verification Status**: FAIL

## Overview Metrics
- Total Allocations: 67
- Hard Constraint Violations (Errors): 8
- Soft Preference Violations (Warnings): 2

## Violations & Conflict Explanations
- :x: Consecutive Practical Rule Violated: Course ISC506 on Day 1 for Section IS5A crosses a break or lunch boundary (got periods [2, 3, 7]).
- :x: Consecutive Practical Rule Violated: Course ISC507 on Day 1 for Section IS5A crosses a break or lunch boundary (got periods [4, 5, 6]).
- :x: Consecutive Practical Rule Violated: Course ISC508 on Day 2 for Section IS5A crosses a break or lunch boundary (got periods [1, 2, 3]).
- :x: AI Rules: AI Rule Violated: section IS5A must avoid Period(s) [1], but scheduled in Period 1 on Day 2 for Section IS5A.
- :x: AI Rules: AI Rule Violated: Course ISC510 must have at least one session scheduled during preferred slot(s) ['Fri P7'] for Section IS5A, but none were found.
- :x: Duplicate Allocations: Section IS5A has extra hours 3/2 scheduled for Course ISC508.
- :x: Duplicate Allocations: Section IS5A has extra hours 3/2 scheduled for Course ISC507.
- :x: Duplicate Allocations: Section IS5A has extra hours 3/2 scheduled for Course ISC506.
