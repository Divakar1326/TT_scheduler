"""Master validator executing all constraints."""
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple
from app.models.domain import Schedule, Course
from app.constraints.hard_constraints import (
    check_faculty_clash, check_room_clash, check_lab_clash, check_section_clash,
    check_faculty_availability, check_weekly_hours, check_max_faculty_periods_per_day,
    check_permanent_classroom, check_permanent_class_teacher, check_ltp_validation,
    check_has_lab_validation, check_department_isolation, check_working_days,
    check_fixed_timetable_template, check_ai_rule_validation
)
from app.constraints.soft_constraints import (
    score_morning_lab_preference, score_balanced_faculty_workload,
    score_compact_timetable, score_minimize_room_changes,
    score_subject_distribution, score_faculty_gap_minimization
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

        # 6. Weekly Hours
        if not check_weekly_hours(allocation, current_schedule, course.weekly_hours):
            violations.append(f"Weekly Hours exceeded: Course {allocation.course_id} already meets all allocated weekly hours ({course.weekly_hours})")

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
        if not check_ai_rule_validation(allocation, context.ai_rules):
            violations.append(f"AI Rule Violation: Proposed slot conflicts with custom AI rules")

        is_valid = len(violations) == 0
        return is_valid, violations

    @staticmethod
    def calculate_total_penalty(
        current_schedule: List[Schedule], 
        context: ValidationContext
    ) -> int:
        """Calculates aggregate soft constraint penalty score for the entire schedule."""
        total_penalty = 0
        
        # Section-specific soft penalties
        sections = set(s.section_id for s in current_schedule)
        for sec in sections:
            total_penalty += score_compact_timetable(sec, current_schedule)
            total_penalty += score_minimize_room_changes(sec, current_schedule, context.room_sections)
            total_penalty += score_subject_distribution(sec, current_schedule)
            
        # Faculty-specific soft penalties
        faculties = set(s.faculty_id for s in current_schedule)
        for fac in faculties:
            total_penalty += score_balanced_faculty_workload(fac, current_schedule)
            total_penalty += score_faculty_gap_minimization(fac, current_schedule)

        # Allocation-specific soft penalties
        for s in current_schedule:
            total_penalty += score_morning_lab_preference(s)
            
        return total_penalty
