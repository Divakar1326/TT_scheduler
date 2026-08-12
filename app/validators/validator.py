"""Master validator executing all constraints."""
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple
from app.core.domain import Schedule, Course
from app.validators.hard_constraints import (
    check_faculty_clash, check_room_clash, check_lab_clash, check_section_clash,
    check_faculty_availability, check_weekly_hours, check_max_faculty_periods_per_day,
    check_permanent_classroom, check_permanent_class_teacher, check_ltp_validation,
    check_has_lab_validation, check_department_isolation, check_working_days,
    check_fixed_timetable_template, check_ai_rule_validation
)
from app.validators.soft_constraints import (
    score_morning_lab_preference, score_balanced_faculty_workload,
    score_compact_timetable, score_minimize_room_changes,
    score_subject_distribution, score_faculty_gap_minimization,
    score_lab_spread,
    calculate_max_possible_penalty,
    calculate_total_penalty as _sc_calculate_total_penalty,
    calculate_soft_penalty_percentage as _sc_soft_penalty_pct
)

@dataclass
class ValidationContext:
    """Context container holding all lookup data needed for validation."""
    course_dict: Dict[str, Course]
    faculty_unavailables: Set[Tuple[str, int, int]]
    room_sections: Dict[str, str]
    class_teachers: Dict[str, str]
    working_days: Set[int]
    template_slots: Set[Tuple[int, int]]
    section_depts: Dict[str, str]
    course_depts: Dict[str, List[str]]
    ai_rules: List[Dict[str, Any]]
    faculty_max_hours: Dict[str, int] = None
    faculty_max_daily: Dict[str, int] = None
    course_labs: Dict[str, str] = None
    section_semesters: Dict[str, int] = None
    section_courses: Dict[str, List[str]] = None


class MasterValidator:
    """Combines all hard and soft constraint checkers."""

    @staticmethod
    def validate_allocation(
        allocation: Schedule, 
        current_schedule: List[Schedule], 
        context: ValidationContext
    ) -> Tuple[bool, List[str]]:
        """
        Validates all hard constraints for a proposed slot.
        Returns (is_valid, list_of_violations).
        """
        violations = []
        course = context.course_dict.get(allocation.course_id)
        if not course:
            violations.append(f"Course {allocation.course_id} not found in validation context.")
            return False, violations

        # 1. Faculty Clash
        if not check_faculty_clash(allocation, current_schedule):
            violations.append(f"Faculty Clash: Faculty {allocation.faculty_id} already scheduled at Day {allocation.day_id} Period {allocation.period_no}")

        # 2. Room Clash
        if not check_room_clash(allocation, current_schedule):
            violations.append(f"Room Clash: Room {allocation.room_no} already occupied at Day {allocation.day_id} Period {allocation.period_no}")

        # 3. Lab Clash
        if not check_lab_clash(allocation, current_schedule):
            violations.append(f"Lab Clash: Laboratory {allocation.lab_room_no} already occupied at Day {allocation.day_id} Period {allocation.period_no}")

        # 4. Section Clash
        if not check_section_clash(allocation, current_schedule):
            violations.append(f"Section Clash: Section {allocation.section_id} already scheduled at Day {allocation.day_id} Period {allocation.period_no}")

        # 5. Faculty Availability
        if not check_faculty_availability(allocation, context.faculty_unavailables):
            violations.append(f"Faculty Availability: Faculty {allocation.faculty_id} is unavailable at Day {allocation.day_id} Period {allocation.period_no}")

        # 6. Weekly Hours — use LTP-derived expected total if available
        ltp_total = course.l + course.t + course.p
        expected_total = ltp_total if ltp_total > 0 else course.weekly_hours
        if not check_weekly_hours(allocation, current_schedule, course.weekly_hours, expected_total):
            violations.append(f"Weekly Hours exceeded: Course {allocation.course_id} already meets all allocated weekly hours ({expected_total})")

        # 7. Max Daily Limit
        if not check_max_faculty_periods_per_day(allocation, current_schedule):
            violations.append(f"Faculty daily workload limit exceeded for {allocation.faculty_id} on Day {allocation.day_id}")

        # 8. Permanent Classroom
        if not check_permanent_classroom(allocation, context.room_sections):
            violations.append(f"Permanent Classroom violated: Section {allocation.section_id} must be placed in classroom {context.room_sections.get(allocation.section_id)}")

        # 9. Permanent Class Teacher
        if not check_permanent_class_teacher(allocation, context.class_teachers, course):
            violations.append(f"Permanent Class Teacher violated: Mentoring course must be taught by class teacher {context.class_teachers.get(allocation.section_id)}")

        # 10. LTP Validation
        if not check_ltp_validation(course):
            violations.append(f"LTP Mismatch: Course {course.course_id} L+T+P ({course.l}+{course.t}+{course.p}) does not match weekly hours ({course.weekly_hours})")

        # 11. Has Lab Validation
        if not check_has_lab_validation(course, allocation):
            violations.append(f"Lab Allocation Mismatch: Course has_lab={course.has_lab} but allocation room/lab mapping is incorrect")
        if allocation.lab_room_no and context.course_labs:
            mapped_lab = context.course_labs.get(allocation.course_id)
            if mapped_lab and allocation.lab_room_no != mapped_lab:
                violations.append(f"Course Lab Mismatch: Course {allocation.course_id} must be scheduled in lab {mapped_lab}, got {allocation.lab_room_no}")

        # 12. Department Isolation
        section_dept = context.section_depts.get(allocation.section_id)
        course_depts = context.course_depts.get(allocation.course_id, [])
        if not section_dept or not check_department_isolation(allocation, section_dept, course_depts):
            violations.append(f"Department Isolation: Section {allocation.section_id} department {section_dept} is not offered course {allocation.course_id}")

        # 13. Working Days
        if not check_working_days(allocation, context.working_days):
            violations.append(f"Working Days: Day {allocation.day_id} is not an active scheduling day")

        # 14. Fixed Timetable Template
        if not check_fixed_timetable_template(allocation, context.template_slots):
            violations.append(f"Fixed Template: Day {allocation.day_id} Period {allocation.period_no} is a break/lunch or out-of-bounds slot")

        # 15. AI Rules
        if not check_ai_rule_validation(allocation, context.ai_rules, current_schedule, context):
            violations.append(f"AI Rule Violation: Proposed slot conflicts with custom AI rules")

        is_valid = len(violations) == 0
        return is_valid, violations

    @staticmethod
    def calculate_total_penalty(
        current_schedule: List[Schedule],
        context: ValidationContext
    ) -> int:
        """Calculates aggregate soft constraint penalty score for the entire schedule."""
        return _sc_calculate_total_penalty(current_schedule, context.room_sections)

    @staticmethod
    def calculate_soft_penalty_percentage(
        current_schedule: List[Schedule],
        context: ValidationContext
    ) -> float:
        """
        Calculates a meaningful Soft Penalty % using per-category normalization.
        Each category (lab spread, faculty balance, compact schedule, etc.) is
        evaluated independently and averaged, producing a score in [0, 100].
        """
        if not current_schedule:
            return 0.0
        return _sc_soft_penalty_pct(current_schedule, context.room_sections)
