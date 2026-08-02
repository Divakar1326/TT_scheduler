"""Final Timetable Validator analyzing full timetables, generating reports and suggestions."""
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
from app.models.domain import Schedule
from app.constraints.validator import ValidationContext
from app.constraints.hard_constraints import (
    check_faculty_clash, check_room_clash, check_lab_clash, check_section_clash,
    check_faculty_availability, check_permanent_classroom, check_permanent_class_teacher,
    check_has_lab_validation, check_department_isolation, check_fixed_timetable_template,
    check_ai_rule_validation
)
from app.constraints.soft_constraints import (
    score_compact_timetable, score_faculty_gap_minimization
)

class ValidationReport:
    """Encapsulates validation output containing errors, warnings, stats and suggestions."""
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict[str, Any] = {}
        self.suggested_repairs: List[str] = []

    def is_valid(self) -> bool:
        """True if there are zero hard constraint errors."""
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid(),
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
            "suggested_repairs": self.suggested_repairs
        }


class TimetableValidator:
    """Validates completed schedules, generating detailed reports and swap suggestions."""

    @staticmethod
    def validate_timetable(schedule: List[Schedule], context: ValidationContext, rooms: List[str], labs: List[str]) -> ValidationReport:
        report = ValidationReport()
        
        # Indexed lookups for clash validation
        fac_occupations = defaultdict(list)
        room_occupations = defaultdict(list)
        lab_occupations = defaultdict(list)
        sec_occupations = defaultdict(list)
        
        # Load count trackers
        fac_daily_count = defaultdict(int)
        sec_daily_count = defaultdict(int)
        course_weekly_count = defaultdict(int)
        
        # 1. Basic duplicate and clash detection
        for s in schedule:
            slot_key = (s.day_id, s.period_no)
            fac_occupations[(s.faculty_id, *slot_key)].append(s)
            if s.room_no:
                room_occupations[(s.room_no, *slot_key)].append(s)
            if s.lab_room_no:
                lab_occupations[(s.lab_room_no, *slot_key)].append(s)
            sec_occupations[(s.section_id, *slot_key)].append(s)
            
            # Load updates
            fac_daily_count[(s.faculty_id, s.day_id)] += 1
            sec_daily_count[(s.section_id, s.day_id)] += 1
            course_weekly_count[(s.section_id, s.course_id)] += 1

        # Register clash errors
        for key, allocs in fac_occupations.items():
            if len(allocs) > 1:
                report.errors.append(f"Faculty Clash: Faculty {key[0]} is scheduled {len(allocs)} times on Day {key[1]} Period {key[2]}.")
        for key, allocs in room_occupations.items():
            if len(allocs) > 1:
                report.errors.append(f"Room Clash: Room {key[0]} is occupied {len(allocs)} times on Day {key[1]} Period {key[2]}.")
        for key, allocs in lab_occupations.items():
            if len(allocs) > 1:
                report.errors.append(f"Lab Clash: Laboratory {key[0]} is occupied {len(allocs)} times on Day {key[1]} Period {key[2]}.")
        for key, allocs in sec_occupations.items():
            if len(allocs) > 1:
                report.errors.append(f"Section Clash: Section {key[0]} is scheduled {len(allocs)} times on Day {key[1]} Period {key[2]}.")

        # 2. Hard constraints checks on each individual allocation
        for s in schedule:
            course = context.course_dict.get(s.course_id)
            if not course:
                report.errors.append(f"Missing Course definition: Course {s.course_id} not found.")
                continue

            # Faculty availability
            if not check_faculty_availability(s, context.faculty_unavailables):
                report.errors.append(f"Faculty Unavailable: Faculty {s.faculty_id} is unavailable at Day {s.day_id} Period {s.period_no}.")
                
            # Permanent classroom
            if not check_permanent_classroom(s, context.room_sections):
                report.errors.append(f"Permanent Room Violated: Section {s.section_id} scheduled in room {s.room_no} instead of permanent room {context.room_sections.get(s.section_id)}.")

            # Permanent class teacher
            if not check_permanent_class_teacher(s, context.class_teachers, course):
                report.errors.append(f"Permanent Class Teacher Violated: Course {s.course_id} on Day {s.day_id} Period {s.period_no} must be taught by class teacher {context.class_teachers.get(s.section_id)}.")

            # Has lab validation
            if not check_has_lab_validation(course, s):
                report.errors.append(f"Lab Allocation Mismatch: Course {s.course_id} has_lab={course.has_lab} but scheduled in incorrect room type.")

            # Department isolation
            sec_dept = context.section_depts.get(s.section_id)
            course_depts = context.course_depts.get(s.course_id, [])
            if not sec_dept or not check_department_isolation(s, sec_dept, course_depts):
                report.errors.append(f"Department Isolation Violation: Section {s.section_id} ({sec_dept}) cannot schedule course {s.course_id} offered to {course_depts}.")

            # Fixed Template
            if not check_fixed_timetable_template(s, context.template_slots):
                report.errors.append(f"Fixed Template Violated: Allocation at Day {s.day_id} Period {s.period_no} falls in break/lunch slot.")

            # AI Rules
            if not check_ai_rule_validation(s, context.ai_rules):
                report.errors.append(f"AI Rule Violation: Allocation for {s.faculty_id} / {s.course_id} on Day {s.day_id} Period {s.period_no} violates custom AI rule.")

        # 3. Workload and limit validations
        for (fac_id, day), count in fac_daily_count.items():
            if count > 5:
                report.errors.append(f"Faculty Daily Limit exceeded: Faculty {fac_id} has {count} classes on Day {day} (limit: 5).")

        max_day_periods = len(set(p for d, p in context.template_slots))
        for (sec_id, day), count in sec_daily_count.items():
            if count > max_day_periods:
                report.errors.append(f"Section Daily Limit exceeded: Section {sec_id} has {count} classes on Day {day} (limit: {max_day_periods}).")

        # 4. Weekly Hours / Missing Allocations checks
        # Verify that total allocated hours match expected weekly hours for all courses assigned to section
        # We look up what courses should be taught in section_depts/course_depts matching.
        # But wait! If some course is completely missing, the weekly count is 0.
        # Let's check all courses defined in course_dict. If the course department matches the section department,
        # we check if it is fully scheduled.
        for sec_id, dept_id in context.section_depts.items():
            for course_id, course in context.course_dict.items():
                if dept_id in context.course_depts.get(course_id, []):
                    expected = course.weekly_hours
                    actual = course_weekly_count[(sec_id, course_id)]
                    if actual < expected:
                        report.errors.append(f"Missing Allocations: Section {sec_id} has only {actual}/{expected} hours scheduled for Course {course_id}.")
                    elif actual > expected:
                        report.errors.append(f"Duplicate Allocations: Section {sec_id} has extra hours {actual}/{expected} scheduled for Course {course_id}.")

        # 5. Consecutive practical checks
        # For each section and course, group by day and check if consecutive blocks are satisfied
        day_sec_course = defaultdict(list)
        for s in schedule:
            day_sec_course[(s.section_id, s.course_id, s.day_id)].append(s.period_no)

        for (sec_id, course_id, day), periods in day_sec_course.items():
            course = context.course_dict.get(course_id)
            if course and course.p > 0 and len(periods) > 0:
                periods.sort()
                # Check if periods are consecutive
                is_consec = len(periods) == course.p and all(periods[i] + 1 == periods[i+1] for i in range(len(periods)-1))
                if not is_consec:
                    report.errors.append(f"Consecutive Practical Rule Violated: Course {course_id} on Day {day} for Section {sec_id} is not scheduled as a consecutive block of length {course.p} (got periods {periods}).")

        # 6. Warnings (Soft Gaps)
        for sec_id in context.section_depts.keys():
            gap_penalty = score_compact_timetable(sec_id, schedule)
            if gap_penalty > 0:
                report.warnings.append(f"Section Gap Warning: Section {sec_id} has gap periods in their timetable (compactness penalty: {gap_penalty}).")

        for fac_id in set(s.faculty_id for s in schedule):
            gap_penalty = score_faculty_gap_minimization(fac_id, schedule)
            if gap_penalty > 0:
                report.warnings.append(f"Faculty Gap Warning: Faculty {fac_id} has gap periods in their timetable (gap penalty: {gap_penalty}).")

        # 7. Statistics
        report.stats = {
            "total_allocations": len(schedule),
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "room_utilization_rate": round(len(schedule) / (len(rooms + labs) * len(context.template_slots)), 4) if (rooms + labs) else 0.0
        }

        # 8. Suggested Repairs
        # If there's an error, suggest moving one conflicted slot to an empty slot that does not cause conflicts
        if report.errors:
            # Let's find a few empty slots in the grid
            occupied_slots = set((s.day_id, s.period_no, s.room_no or s.lab_room_no) for s in schedule)
            empty_slots = []
            for day in context.working_days:
                for t_day, period in context.template_slots:
                    if t_day == day:
                        for room in rooms + labs:
                            if (day, period, room) not in occupied_slots:
                                empty_slots.append((day, period, room))
                                if len(empty_slots) >= 3:
                                    break
                        if len(empty_slots) >= 3:
                            break
            
            for err in report.errors[:3]:
                if empty_slots:
                    target = empty_slots.pop(0)
                    report.suggested_repairs.append(f"Suggested Repair: Move conflicting session from current slot to Day {target[0]} Period {target[1]} Room {target[2]}.")

        return report
