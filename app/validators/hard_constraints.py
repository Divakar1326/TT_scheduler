"""Hard constraint validation functions for the university timetable."""
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.domain import Schedule, Course

def check_faculty_clash(allocation: Schedule, current_schedule: List[Schedule]) -> bool:
    """True if faculty is free at the proposed slot, False if clashed."""
    for s in current_schedule:
        if (s.day_id == allocation.day_id and 
            s.period_no == allocation.period_no and 
            s.faculty_id == allocation.faculty_id):
            return False
    return True

def check_room_clash(allocation: Schedule, current_schedule: List[Schedule]) -> bool:
    """True if room is free at the proposed slot, False if clashed."""
    if not allocation.room_no:
        return True
    for s in current_schedule:
        if (s.day_id == allocation.day_id and 
            s.period_no == allocation.period_no and 
            s.room_no == allocation.room_no):
            return False
    return True

def check_lab_clash(allocation: Schedule, current_schedule: List[Schedule]) -> bool:
    """True if laboratory is free at the proposed slot, False if clashed."""
    if not allocation.lab_room_no:
        return True
    for s in current_schedule:
        if (s.day_id == allocation.day_id and 
            s.period_no == allocation.period_no and 
            s.lab_room_no == allocation.lab_room_no):
            return False
    return True

def check_section_clash(allocation: Schedule, current_schedule: List[Schedule]) -> bool:
    """True if section is free at the proposed slot, False if clashed."""
    for s in current_schedule:
        if (s.day_id == allocation.day_id and 
            s.period_no == allocation.period_no and 
            s.section_id == allocation.section_id):
            return False
    return True

def check_faculty_availability(allocation: Schedule, unavailable_slots: Set[Tuple[str, int, int]]) -> bool:
    """True if slot is NOT in the faculty unavailable list."""
    return (allocation.faculty_id, allocation.day_id, allocation.period_no) not in unavailable_slots

def check_weekly_hours(
    allocation: Schedule,
    current_schedule: List[Schedule],
    max_hours: int,
    expected_total: Optional[int] = None
) -> bool:
    """
    True if adding this allocation does not exceed the course's total session
    budget.

    Args:
        max_hours:      The raw ``course.weekly_hours`` value (used as fallback).
        expected_total: The LTP-derived total = L + T + P when L+T+P > 0,
                        otherwise falls back to ``max_hours``.
                        Always pass this from MasterValidator so the correct
                        cap is used and the CSP never rejects valid sessions.
    """
    cap = expected_total if expected_total is not None else max_hours
    count = sum(
        1 for s in current_schedule
        if s.section_id == allocation.section_id
        and s.course_id == allocation.course_id
    )
    return (count + 1) <= cap

def check_max_faculty_periods_per_day(allocation: Schedule, current_schedule: List[Schedule], max_daily_periods: int = 5) -> bool:
    """True if faculty daily workload does not exceed the limit (default 5 periods, 6 for lab instructors)."""
    limit = 6 if allocation.faculty_id.startswith("L") else max_daily_periods
    count = sum(1 for s in current_schedule if s.faculty_id == allocation.faculty_id and s.day_id == allocation.day_id)
    return (count + 1) <= limit

def check_permanent_classroom(allocation: Schedule, room_sections: Dict[str, str]) -> bool:
    """True if room matches the section's permanent room (for theory classes)."""
    if allocation.lab_room_no:  # Lab classes don't use permanent classroom
        return True
    perm_room = room_sections.get(allocation.section_id)
    return perm_room is None or allocation.room_no == perm_room

def check_permanent_class_teacher(allocation: Schedule, class_teachers: Dict[str, str], course: Course) -> bool:
    """True if class teacher teaches their class, or not applicable.
    Note: Usually class teacher rule can be configured as soft or hard.
    Here we ensure that if it is class teacher time, it's correct. Or we check that the HOD assignment is maintained.
    Wait! The blueprint and SRS say: 'Permanent class teacher maintained'.
    Wait! In the seed data and DB, class_teacher is a static binding (e.g. section_id -> faculty_id).
    Since HOD defines faculty_assignment (who teaches what course for what section),
    maintaining permanent class teacher means class teacher assignment matches what's in the database.
    So this checks if the class teacher mapping is respected if specified.
    Wait, in the SQL schema: 'class_teacher' maps section_id -> faculty_id.
    And 'faculty_assignment' maps section_id + course_id -> faculty_id.
    Let's ensure that if section class teacher is assigned, we do not conflict.
    Actually, HOD defines faculty assignments. The class teacher is just a role.
    Wait, let's look at MASTER_PROJECT_BLUEPRINT.md:
    'Permanent class teacher maintained'
    This means the class teacher defined in class_teacher table for a section is a valid faculty member in the system,
    and we check if the section's class teacher is maintained for the section.
    Let's define: if the class teacher of a section is F01, then F01 must teach the designated mentor/class teacher hour.
    Let's check if the section's class teacher is matching the class_teacher table.
    """
    perm_teacher = class_teachers.get(allocation.section_id)
    # If the course is a mentoring hour / homeroom session, it MUST be taught by the permanent class teacher.
    if course.course_id.lower().startswith("mentor") or course.course_name.lower().startswith("mentor"):
        return perm_teacher is None or allocation.faculty_id == perm_teacher
    return True

def check_consecutive_practical(allocation: Schedule, current_schedule: List[Schedule]) -> bool:
    """
    During CSP candidate generation (partial schedule), this is called with the
    BLOCK allocations added incrementally.  For a single-period lab allocation
    being *added* to current_schedule, it is always structurally valid to start
    a new block -- the CandidateGenerator already ensures the full consecutive
    block fits in the template before proposing the candidate.

    This function is intentionally lightweight at generation time.  The
    TimetableValidator performs the full consecutive-block audit after the
    complete schedule is assembled.
    """
    # If no lab room is involved, this constraint does not apply.
    if not allocation.lab_room_no:
        return True

    # Find all existing lab periods for this section + course on the same day.
    same_day_lab_periods = sorted(
        s.period_no for s in current_schedule
        if s.section_id == allocation.section_id
        and s.course_id == allocation.course_id
        and s.lab_room_no
        and s.day_id == allocation.day_id
    )

    if not same_day_lab_periods:
        # No existing periods on this day -- valid to start a new block.
        return True

    # The new period must be directly adjacent (before or after) the existing block.
    block_min = min(same_day_lab_periods)
    block_max = max(same_day_lab_periods)
    return (
        allocation.period_no == block_max + 1  # extending rightward
        or allocation.period_no == block_min - 1  # extending leftward
    )

def check_ltp_validation(course: Course) -> bool:
    """True if L + T + P matches the weekly hours."""
    if course.l == 0 and course.t == 0 and course.p == 0:
        return True
    return (course.l + course.t + course.p) == course.weekly_hours

def check_has_lab_validation(course: Course, allocation: Schedule) -> bool:
    """True if room/lab mapping is correct based on course configuration."""
    if (allocation.room_no is not None and allocation.lab_room_no is not None) or (allocation.room_no is None and allocation.lab_room_no is None):
        return False
    if not course.has_lab:
        return allocation.room_no is not None
    if course.l == 0 and course.t == 0:
        return allocation.lab_room_no is not None
    return True

def check_department_isolation(allocation: Schedule, section_dept_id: str, course_dept_ids: List[str]) -> bool:
    """True if course is offered to or belongs to the section's department."""
    if not section_dept_id:
        return True
    return section_dept_id.upper() in [d.upper() for d in course_dept_ids if d]

def check_working_days(allocation: Schedule, working_days: Set[int]) -> bool:
    """True if the day_id is a valid working day."""
    return allocation.day_id in working_days

def check_fixed_timetable_template(allocation: Schedule, template_slots: Set[Tuple[int, int]]) -> bool:
    """True if the proposed slot is a valid active teaching slot (not a break/lunch)."""
    return (allocation.day_id, allocation.period_no) in template_slots

def check_ai_rule_validation(
    allocation: Schedule,
    rule_jsons: List[Dict[str, Any]],
    current_schedule: Optional[List[Schedule]] = None,
    context: Optional[Any] = None
) -> bool:
    """Evaluates dynamic parameters of saved AI rules against a proposed allocation.

    Supported JSON rule schema:
        faculty_id        (str)   — applies rule to a specific faculty
        section_id        (str)   — applies rule to a specific section
        course_id         (str)   — applies rule to a specific course
        avoid_periods     (list)  — list of period_no values to avoid
        avoid_days        (list)  — list of day_id values to avoid (optional filter)
        preferred_periods (list)  — allocation must be in one of these periods (AI schema key)
        preferred_days    (list)  — allocation must be on one of these days (AI schema key)
        prefer_periods    (list)  — legacy alias for preferred_periods
        prefer_days       (list)  — legacy alias for preferred_days

    When BOTH preferred_days and preferred_periods are specified, the constraint
    acts as a hard pin: the allocation must satisfy BOTH simultaneously
    (e.g. "ISC510 must be on Friday P7" → preferred_days=[5], preferred_periods=[7]).
    """
    for rule in rule_jsons:
        try:
            # Determine if this rule is applicable to the proposed allocation.
            # If a rule specifies a target field, the allocation MUST match that field.
            
            rule_faculty = rule.get("faculty_id")
            if rule_faculty and rule_faculty != allocation.faculty_id:
                continue
                
            rule_section = rule.get("section_id")
            if rule_section and rule_section != allocation.section_id:
                continue
                
            rule_course = rule.get("course_id")
            if rule_course and rule_course != allocation.course_id:
                continue
                
            rule_room = rule.get("room_no")
            if rule_room:
                if str(rule_room).upper() in ("ANY", "ROOM", "ROOMS", "ALL", "ALL_ROOMS"):
                    if not allocation.room_no:
                        continue
                elif rule_room != allocation.room_no:
                    continue
                    
            rule_lab = rule.get("lab_room_no")
            if rule_lab:
                if str(rule_lab).upper() in ("ANY", "LAB", "LABS", "ALL", "ALL_LABS"):
                    if not allocation.lab_room_no:
                        continue
                elif rule_lab != allocation.lab_room_no:
                    continue

            # --- Avoid periods check ---
            avoid_periods = rule.get("avoid_periods", [])
            avoid_days = rule.get("avoid_days", [])
            if avoid_periods and allocation.period_no in avoid_periods:
                # Rule blocks this period — check if day filter is also set
                if not avoid_days or allocation.day_id in avoid_days:
                    return False

            # --- Avoid days check ---
            if avoid_days and not avoid_periods:
                # Day-only block (no period restriction)
                if allocation.day_id in avoid_days:
                    return False

            # --- Prefer periods check ---
            # Support both 'preferred_periods' (AI schema) and 'prefer_periods' (legacy)
            prefer_periods = rule.get("preferred_periods") or rule.get("prefer_periods", [])
            prefer_days = rule.get("preferred_days") or rule.get("prefer_days", [])

            if prefer_periods or prefer_days:
                # If course-scoped, we only require at least one session of the course (per section) to be in preferred slots.
                if rule_course:
                    curr_sch = current_schedule if current_schedule is not None else []
                    has_preferred_allocation = False
                    for s in curr_sch:
                        if s.course_id == allocation.course_id and s.section_id == allocation.section_id:
                            match_day = not prefer_days or s.day_id in prefer_days
                            match_period = not prefer_periods or s.period_no in prefer_periods
                            if match_day and match_period:
                                has_preferred_allocation = True
                                break
                    
                    if has_preferred_allocation:
                        # Already satisfied by an existing allocation! Other sessions can go anywhere.
                        continue

                    # If not satisfied yet, check if this is the last session we can schedule
                    if context and context.course_dict:
                        course = context.course_dict.get(allocation.course_id)
                        if course:
                            ltp_total = course.l + course.t + course.p
                            total_expected = ltp_total if ltp_total > 0 else course.weekly_hours
                            already_scheduled = sum(
                                1 for s in curr_sch 
                                if s.course_id == allocation.course_id and s.section_id == allocation.section_id
                            )
                            if already_scheduled < total_expected - 1:
                                # Not the last session yet. Let it pass (it can be scheduled anywhere, 
                                # or one of the subsequent ones will be forced to the preferred slot).
                                continue

                # Otherwise (or if it is the last session), enforce preference as hard pin
                if prefer_periods and prefer_days:
                    if allocation.day_id not in prefer_days or allocation.period_no not in prefer_periods:
                        return False
                else:
                    if prefer_periods and allocation.period_no not in prefer_periods:
                        return False
                    if prefer_days and allocation.day_id not in prefer_days:
                        return False

        except (TypeError, KeyError, AttributeError):
            # Malformed rule — skip rather than crash
            continue

    return True

