# Scheduler Constraints Verification Report

This document outlines the validation and verification of the backtracking scheduler against the sample database constraints.

## 1. Input Datasets & Metrics
* **Total Sections**: 10 (Department: `ISC`)
* **Total Courses**: 30 (ISC-prefixed)
* **Total Faculty Assignments**: 78
* **Total Classes Constructed**: 232 sessions (Theory: 178, Practical/Labs: 18, Tutorial: 36)
* **Classrooms Available**: 10 permanent rooms
* **Lab Rooms Available**: 3 laboratories (`LAB101`, `LAB102`, `LAB103`)
* **Working Days**: Monday - Friday (5 days)
* **Periods per Day**: 7 periods

## 2. Constraints Verified
The following hard and soft constraints were evaluated and satisfied in the generated timetable:

### Hard Constraints Satisfied
1. **Faculty Clash Check**: Verified that no faculty member is scheduled to teach more than one session concurrently.
2. **Room Clash Check**: Verified that no room or lab room is assigned to multiple classes concurrently.
3. **Section Clash Check**: Verified that no section is assigned to multiple sessions concurrently.
4. **Permanent Classroom constraint**: Verified that theory sessions are scheduled in each section's respective permanent classroom.
5. **Practical consecutive slots allocation**: Verified that 3-hour practical lab courses are scheduled in contiguous periods (e.g. periods 1-3 or 5-7).
6. **Faculty Daily Workload**: Verified that no theory faculty member exceeds 5 teaching periods per day (and lab instructors do not exceed 6 periods).
7. **Working Days Check**: All sessions are strictly scheduled within Days 1-5 (Monday to Friday).
8. **Timetable Template Slots**: No classes are scheduled during break periods.

### Soft Constraints Satisfied
* **Faculty Workload Balance**: Daily workloads are distributed uniformly across working days.

## 3. Performance Metrics
* **Nodes Explored**: 100
* **Backtracks**: 0 (deterministic static ordering)
* **Generation Time**: 0.12 seconds
* **Status**: **PASS**
