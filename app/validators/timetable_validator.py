"""Final Timetable Validator analyzing full timetables, generating reports and suggestions."""
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import os
import json
from app.core.domain import Schedule
from app.validators.validator import ValidationContext
from app.validators.hard_constraints import (
    check_faculty_clash, check_room_clash, check_lab_clash, check_section_clash,
    check_faculty_availability, check_permanent_classroom, check_permanent_class_teacher,
    check_department_isolation, check_ai_rule_validation
)
from app.validators.soft_constraints import (
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
        
        # Rule Status Dictionary
        rule_statuses = {
            "Faculty Clash": {"status": "PASS", "details": [], "type": "Hard"},
            "Room Clash": {"status": "PASS", "details": [], "type": "Hard"},
            "Lab Clash": {"status": "PASS", "details": [], "type": "Hard"},
            "Section Clash": {"status": "PASS", "details": [], "type": "Hard"},
            "Faculty Workload": {"status": "PASS", "details": [], "type": "Hard"},
            "Consecutive Practicals": {"status": "PASS", "details": [], "type": "Hard"},
            "Department rules": {"status": "PASS", "details": [], "type": "Hard"},
            "AI Rules": {"status": "PASS", "details": [], "type": "Hard"}
        }

        # 1. Faculty Clash Rule Check
        fac_occupations = defaultdict(list)
        for s in schedule:
            fac_occupations[(s.faculty_id, s.day_id, s.period_no)].append(s)
        for key, allocs in fac_occupations.items():
            if len(allocs) > 1:
                rule_statuses["Faculty Clash"]["status"] = "FAIL"
                detail = f"Faculty {key[0]} is double-booked on Day {key[1]} Period {key[2]} across sections: {', '.join(s.section_id for s in allocs)}."
                rule_statuses["Faculty Clash"]["details"].append(detail)
                report.errors.append(f"Faculty Clash: Faculty {key[0]} is scheduled {len(allocs)} times on Day {key[1]} Period {key[2]}.")

        # 2. Room Clash Rule Check
        room_occupations = defaultdict(list)
        for s in schedule:
            if s.room_no:
                room_occupations[(s.room_no, s.day_id, s.period_no)].append(s)
        for key, allocs in room_occupations.items():
            if len(allocs) > 1:
                rule_statuses["Room Clash"]["status"] = "FAIL"
                detail = f"Room {key[0]} is double-booked on Day {key[1]} Period {key[2]} by sections: {', '.join(s.section_id for s in allocs)}."
                rule_statuses["Room Clash"]["details"].append(detail)
                report.errors.append(f"Room Clash: Room {key[0]} is occupied {len(allocs)} times on Day {key[1]} Period {key[2]}.")

        # Check for Room Clash CONFLICT (shared permanent rooms in context)
        if context.room_sections:
            room_to_sections = defaultdict(list)
            for sec, rm in context.room_sections.items():
                if rm:
                    room_to_sections[rm].append(sec)
            for rm, secs in room_to_sections.items():
                if len(secs) > 1:
                    active_secs = {s.section_id for s in schedule if s.section_id in secs}
                    if len(active_secs) > 1:
                        rule_statuses["Room Clash"]["status"] = "CONFLICT"
                        detail = f"Sections ({', '.join(active_secs)}) are assigned the same permanent classroom {rm}."
                        rule_statuses["Room Clash"]["details"].append(detail)
                        report.errors.append(f"Room Conflict: {detail}")

        # 3. Lab Clash Rule Check
        lab_occupations = defaultdict(list)
        for s in schedule:
            if s.lab_room_no:
                lab_occupations[(s.lab_room_no, s.day_id, s.period_no)].append(s)
        for key, allocs in lab_occupations.items():
            if len(allocs) > 1:
                rule_statuses["Lab Clash"]["status"] = "FAIL"
                detail = f"Laboratory {key[0]} is double-booked on Day {key[1]} Period {key[2]} by sections: {', '.join(s.section_id for s in allocs)}."
                rule_statuses["Lab Clash"]["details"].append(detail)
                report.errors.append(f"Lab Clash: Laboratory {key[0]} is occupied {len(allocs)} times on Day {key[1]} Period {key[2]}.")

        # 4. Section Clash Rule Check
        sec_occupations = defaultdict(list)
        for s in schedule:
            sec_occupations[(s.section_id, s.day_id, s.period_no)].append(s)
        for key, allocs in sec_occupations.items():
            if len(allocs) > 1:
                rule_statuses["Section Clash"]["status"] = "FAIL"
                detail = f"Section {key[0]} has {len(allocs)} sessions scheduled simultaneously on Day {key[1]} Period {key[2]}."
                rule_statuses["Section Clash"]["details"].append(detail)
                report.errors.append(f"Section Clash: Section {key[0]} is scheduled {len(allocs)} times on Day {key[1]} Period {key[2]}.")

        # Check for Section Clash UNSATISFIABLE (required hours > available template slots)
        active_periods_count = len(context.template_slots) if context.template_slots else 35
        sec_hours = defaultdict(int)
        for s in schedule:
            sec_hours[s.section_id] += 1
        for sec, hours in sec_hours.items():
            if hours > active_periods_count:
                rule_statuses["Section Clash"]["status"] = "UNSATISFIABLE"
                detail = f"Section {sec} requires {hours} slots in this schedule, which exceeds template slots limit of {active_periods_count}."
                rule_statuses["Section Clash"]["details"].append(detail)
                report.errors.append(f"Section UNSATISFIABLE: {detail}")

        # 5. Faculty Workload Rule Check
        fac_daily_count = defaultdict(int)
        fac_weekly_hours = defaultdict(int)
        for s in schedule:
            fac_daily_count[(s.faculty_id, s.day_id)] += 1
            fac_weekly_hours[s.faculty_id] += 1

        for (fac_id, day), count in fac_daily_count.items():
            max_daily = 5
            if context.faculty_max_daily and fac_id in context.faculty_max_daily:
                max_daily = context.faculty_max_daily[fac_id]
            elif fac_id.startswith("L") or "lab" in fac_id.lower():
                max_daily = 6
            if count > max_daily:
                rule_statuses["Faculty Workload"]["status"] = "FAIL"
                detail = f"Faculty {fac_id} daily workload limit exceeded: {count}/{max_daily} periods scheduled on Day {day}."
                rule_statuses["Faculty Workload"]["details"].append(detail)
                report.errors.append(f"Faculty Daily Limit exceeded: Faculty {fac_id} has {count} classes on Day {day} (limit: 5).")

        for fac_id, hours in fac_weekly_hours.items():
            max_weekly = 30
            if context.faculty_max_hours and fac_id in context.faculty_max_hours:
                max_weekly = context.faculty_max_hours[fac_id]
            if hours > max_weekly:
                rule_statuses["Faculty Workload"]["status"] = "UNSATISFIABLE"
                detail = f"Faculty {fac_id} weekly workload limit exceeded: {hours}/{max_weekly} periods scheduled."
                rule_statuses["Faculty Workload"]["details"].append(detail)
                report.errors.append(f"Faculty Workload UNSATISFIABLE: {detail}")

        # 6. Consecutive Practicals Rule Check
        day_sec_course = defaultdict(list)
        for s in schedule:
            day_sec_course[(s.section_id, s.course_id, s.day_id)].append(s.period_no)

        for (sec_id, course_id, day), periods in day_sec_course.items():
            course = context.course_dict.get(course_id) if context.course_dict else None
            if course and course.p > 0 and len(periods) > 0:
                periods.sort()
                is_consec = len(periods) == course.p and all(periods[i] + 1 == periods[i+1] for i in range(len(periods)-1))
                
                # Also check that it does not cross BREAK (P2/P3) or LUNCH (P4/P5)
                crosses_boundary = False
                day_periods = [p for d, p in context.template_slots if d == day] if context.template_slots else []
                if day_periods and max(day_periods) >= 5:
                    period_set = set(periods)
                    if 2 in period_set and 3 in period_set:
                        crosses_boundary = True
                    if 4 in period_set and 5 in period_set:
                        crosses_boundary = True
                    
                if not is_consec or crosses_boundary:
                    rule_statuses["Consecutive Practicals"]["status"] = "FAIL"
                    if crosses_boundary:
                        detail = f"Course {course_id} on Day {day} for Section {sec_id} crosses a break or lunch boundary (periods: {periods})."
                        err_msg = f"Consecutive Practical Rule Violated: Course {course_id} on Day {day} for Section {sec_id} crosses a break or lunch boundary (got periods {periods})."
                    else:
                        detail = f"Course {course_id} on Day {day} for Section {sec_id} is not scheduled as consecutive block of length {course.p} (periods: {periods})."
                        err_msg = f"Consecutive Practical Rule Violated: Course {course_id} on Day {day} for Section {sec_id} is not scheduled as a consecutive block of length {course.p} (got periods {periods})."
                    rule_statuses["Consecutive Practicals"]["details"].append(detail)
                    report.errors.append(err_msg)

        # 7. Department rules Check (Department Isolation + Permanent Classroom)
        for s in schedule:
            # Permanent classroom
            if context.room_sections and not check_permanent_classroom(s, context.room_sections):
                rule_statuses["Department rules"]["status"] = "FAIL"
                detail = f"Permanent room violated: Section {s.section_id} scheduled in room {s.room_no} instead of permanent room {context.room_sections.get(s.section_id)}."
                rule_statuses["Department rules"]["details"].append(detail)
                report.errors.append(f"Department rules: {detail}")

            # Permanent class teacher
            course = context.course_dict.get(s.course_id) if context.course_dict else None
            if course and context.class_teachers and not check_permanent_class_teacher(s, context.class_teachers, course):
                rule_statuses["Department rules"]["status"] = "FAIL"
                detail = f"Permanent class teacher violated: Mentor course {s.course_id} must be taught by mentor {context.class_teachers.get(s.section_id)}."
                rule_statuses["Department rules"]["details"].append(detail)
                report.errors.append(f"Department rules: {detail}")

            # Department isolation
            if context.section_depts and context.course_depts:
                sec_dept = context.section_depts.get(s.section_id)
                course_depts = context.course_depts.get(s.course_id, [])
                if sec_dept and not check_department_isolation(s, sec_dept, course_depts):
                    rule_statuses["Department rules"]["status"] = "FAIL"
                    detail = f"Department Isolation: Section {s.section_id} ({sec_dept}) cannot schedule course {s.course_id} offered to departments: {course_depts}."
                    rule_statuses["Department rules"]["details"].append(detail)
                    report.errors.append(f"Department rules: {detail}")

            # Mapped lab room check
            if s.lab_room_no and context.course_labs:
                mapped_lab = context.course_labs.get(s.course_id)
                if mapped_lab and s.lab_room_no != mapped_lab:
                    rule_statuses["Department rules"]["status"] = "FAIL"
                    detail = f"Course Lab Mismatch: Course {s.course_id} scheduled in lab {s.lab_room_no} instead of mapped lab {mapped_lab}."
                    rule_statuses["Department rules"]["details"].append(detail)
                    report.errors.append(f"Department rules: {detail}")

        # 8. AI Rules Check — check each active rule individually for descriptive messages
        if context.ai_rules:
            for rule in context.ai_rules:
                try:
                    rule_course = rule.get("course_id")
                    rule_section = rule.get("section_id")
                    rule_faculty = rule.get("faculty_id")
                    prefer_periods = rule.get("preferred_periods") or rule.get("prefer_periods", [])
                    prefer_days = rule.get("preferred_days") or rule.get("prefer_days", [])
                    avoid_periods = rule.get("avoid_periods", [])
                    avoid_days = rule.get("avoid_days", [])

                    # Course-scoped preferred day/period checks (require at least one session in preferred slots)
                    if rule_course and (prefer_days or prefer_periods):
                        sections_to_check = set(s.section_id for s in schedule if s.course_id == rule_course)
                        for sec_id in sections_to_check:
                            if rule_section and rule_section != sec_id:
                                continue
                            
                            course_allocs = [s for s in schedule if s.course_id == rule_course and s.section_id == sec_id]
                            has_preferred = False
                            for s in course_allocs:
                                match_day = not prefer_days or s.day_id in prefer_days
                                match_period = not prefer_periods or s.period_no in prefer_periods
                                if match_day and match_period:
                                    has_preferred = True
                                    break
                            
                            if not has_preferred:
                                rule_statuses["AI Rules"]["status"] = "FAIL"
                                day_names = {1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri"}
                                expected_slots = []
                                if prefer_days and prefer_periods:
                                    expected_slots = [f"{day_names.get(d,d)} P{p}" for d in prefer_days for p in prefer_periods]
                                elif prefer_days:
                                    expected_slots = [f"{day_names.get(d,d)}" for d in prefer_days]
                                elif prefer_periods:
                                    expected_slots = [f"P{p}" for p in prefer_periods]
                                
                                detail = (
                                    f"AI Rule Violated: Course {rule_course} must have at least one session "
                                    f"scheduled during preferred slot(s) {expected_slots} for Section {sec_id}, "
                                    f"but none were found."
                                )
                                rule_statuses["AI Rules"]["details"].append(detail)
                                report.errors.append(f"AI Rules: {detail}")
                    else:
                        # Otherwise, check allocations individually
                        for s in schedule:
                            if rule_faculty and rule_faculty != s.faculty_id:
                                continue
                            if rule_section and rule_section != s.section_id:
                                continue
                            if rule_course and rule_course != s.course_id:
                                continue

                            rule_room = rule.get("room_no")
                            if rule_room:
                                if str(rule_room).upper() in ("ANY", "ROOM", "ROOMS", "ALL", "ALL_ROOMS"):
                                    if not s.room_no:
                                        continue
                                elif rule_room != s.room_no:
                                    continue

                            rule_lab = rule.get("lab_room_no")
                            if rule_lab:
                                if str(rule_lab).upper() in ("ANY", "LAB", "LABS", "ALL", "ALL_LABS"):
                                    if not s.lab_room_no:
                                        continue
                                elif rule_lab != s.lab_room_no:
                                    continue

                            # Faculty or section scoped preferred checks (apply to all allocations matching criteria)
                            if prefer_periods and prefer_days:
                                if s.day_id not in prefer_days or s.period_no not in prefer_periods:
                                    target_str = f"faculty {rule_faculty or s.faculty_id}" if rule_faculty else f"section {rule_section or s.section_id}"
                                    rule_statuses["AI Rules"]["status"] = "FAIL"
                                    day_names = {1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri"}
                                    expected = f"Day {prefer_days} (={[day_names.get(d,d) for d in prefer_days]}) Period {prefer_periods}"
                                    actual = f"Day {s.day_id} ({day_names.get(s.day_id,s.day_id)}) Period {s.period_no}"
                                    detail = (
                                        f"AI Rule Violated: {target_str} must be scheduled on {expected}, "
                                        f"but found on {actual} for Section {s.section_id}."
                                    )
                                    rule_statuses["AI Rules"]["details"].append(detail)
                                    report.errors.append(f"AI Rules: {detail}")
                            elif prefer_periods and s.period_no not in prefer_periods:
                                target_str = f"faculty {rule_faculty or s.faculty_id}" if rule_faculty else f"section {rule_section or s.section_id}"
                                rule_statuses["AI Rules"]["status"] = "FAIL"
                                detail = (
                                    f"AI Rule Violated: {target_str} must be in period(s) {prefer_periods}, "
                                    f"but scheduled in Period {s.period_no} on Day {s.day_id} for Section {s.section_id}."
                                )
                                rule_statuses["AI Rules"]["details"].append(detail)
                                report.errors.append(f"AI Rules: {detail}")
                            elif prefer_days and s.day_id not in prefer_days:
                                target_str = f"faculty {rule_faculty or s.faculty_id}" if rule_faculty else f"section {rule_section or s.section_id}"
                                rule_statuses["AI Rules"]["status"] = "FAIL"
                                day_names = {1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri"}
                                detail = (
                                    f"AI Rule Violated: {target_str} must be on day(s) {[day_names.get(d,d) for d in prefer_days]}, "
                                    f"but scheduled on Day {s.day_id} ({day_names.get(s.day_id,s.day_id)}) Period {s.period_no} for Section {s.section_id}."
                                )
                                rule_statuses["AI Rules"]["details"].append(detail)
                                report.errors.append(f"AI Rules: {detail}")

                            # Negative/Avoid constraints (always apply to all matching allocations)
                            if avoid_periods and s.period_no in avoid_periods:
                                if not avoid_days or s.day_id in avoid_days:
                                    target_str = f"course {rule_course or s.course_id}" if rule_course else (f"faculty {rule_faculty or s.faculty_id}" if rule_faculty else f"section {rule_section or s.section_id}")
                                    rule_statuses["AI Rules"]["status"] = "FAIL"
                                    detail = (
                                        f"AI Rule Violated: {target_str} must avoid Period(s) {avoid_periods}, "
                                        f"but scheduled in Period {s.period_no} on Day {s.day_id} for Section {s.section_id}."
                                    )
                                    rule_statuses["AI Rules"]["details"].append(detail)
                                    report.errors.append(f"AI Rules: {detail}")
                            elif avoid_days and not avoid_periods and s.day_id in avoid_days:
                                target_str = f"course {rule_course or s.course_id}" if rule_course else (f"faculty {rule_faculty or s.faculty_id}" if rule_faculty else f"section {rule_section or s.section_id}")
                                rule_statuses["AI Rules"]["status"] = "FAIL"
                                day_names = {1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri"}
                                detail = (
                                    f"AI Rule Violated: {target_str} must avoid day(s) {[day_names.get(d,d) for d in avoid_days]}, "
                                    f"but scheduled on Day {s.day_id} ({day_names.get(s.day_id,s.day_id)}) Period {s.period_no} for Section {s.section_id}."
                                )
                                rule_statuses["AI Rules"]["details"].append(detail)
                                report.errors.append(f"AI Rules: {detail}")
                except (TypeError, KeyError, AttributeError):
                    continue

        # 9. Expected Weekly Hours / Missing Allocations validation
        # IMPORTANT: only check sections that are actually represented in THIS
        # schedule.  Iterating over all of context.section_depts causes false
        # "Missing Allocations" errors for sections belonging to other
        # departments whose schedule was generated in a separate run.
        course_weekly_count = defaultdict(int)
        for s in schedule:
            course_weekly_count[(s.section_id, s.course_id)] += 1

        # Build a set of section IDs that appear in the current schedule
        scheduled_section_ids = {s.section_id for s in schedule}

        if schedule and context.course_dict:
            for sec_id in scheduled_section_ids:
                dept_id = context.section_depts.get(sec_id)
                if not dept_id:
                    continue

                # Determine which courses this section is expected to have
                assigned_courses = None
                if hasattr(context, "section_courses") and context.section_courses:
                    assigned_courses = context.section_courses.get(sec_id)

                for course_id, course in context.course_dict.items():
                    if assigned_courses is not None:
                        should_check = course_id in assigned_courses
                    else:
                        sec_sem = (
                            context.section_semesters.get(sec_id)
                            if hasattr(context, "section_semesters") and context.section_semesters
                            else None
                        )
                        should_check = (
                            dept_id in context.course_depts.get(course_id, [])
                            and (sec_sem is None or course.semester == sec_sem)
                        )

                    if should_check:
                        # Determine expected total: use LTP sum when non-zero
                        ltp_total = course.l + course.t + course.p
                        expected = ltp_total if ltp_total > 0 else course.weekly_hours
                        actual = course_weekly_count[(sec_id, course_id)]
                        if actual < expected:
                            report.errors.append(
                                f"Missing Allocations: Section {sec_id} has only "
                                f"{actual}/{expected} hours scheduled for Course {course_id}."
                            )
                        elif actual > expected:
                            report.errors.append(
                                f"Duplicate Allocations: Section {sec_id} has extra hours "
                                f"{actual}/{expected} scheduled for Course {course_id}."
                            )

        # 10. Warnings / Gaps (Soft Rules)
        if context.section_depts:
            for sec_id in context.section_depts.keys():
                gap_penalty = score_compact_timetable(sec_id, schedule)
                if gap_penalty > 0:
                    report.warnings.append(f"Section Gap Warning: Section {sec_id} has gap periods in their timetable (compactness penalty: {gap_penalty}).")

        for fac_id in set(s.faculty_id for s in schedule):
            gap_penalty = score_faculty_gap_minimization(fac_id, schedule)
            if gap_penalty > 0:
                report.warnings.append(f"Faculty Gap Warning: Faculty {fac_id} has gap periods in their timetable (gap penalty: {gap_penalty}).")

        # 11. Compute Statistics
        from app.validators.validator import MasterValidator
        total_penalty = MasterValidator.calculate_total_penalty(schedule, context)
        fitness_score = max(0.0, round((1.0 - total_penalty / max(1, len(schedule) * 10)) * 100, 2))
        constraint_satisfaction = max(0.0, round((1.0 - len(report.errors) / max(1, len(schedule))) * 100, 2))
        soft_penalty_percent = MasterValidator.calculate_soft_penalty_percentage(schedule, context)

        report.stats = {
            "total_allocations": len(schedule),
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "room_utilization_rate": round(len(schedule) / (len(rooms + labs) * len(context.template_slots)), 4) if (rooms + labs) and context.template_slots else 0.0,
            "fitness_score": fitness_score,
            "constraint_satisfaction": constraint_satisfaction,
            "soft_penalty_percent": soft_penalty_percent,
            "rule_statuses": rule_statuses
        }

        # 12. Rule Relaxations / Suggested Repairs
        if report.errors:
            occupied_slots = set((s.day_id, s.period_no, s.room_no or s.lab_room_no) for s in schedule)
            empty_slots = []
            if context.working_days and context.template_slots:
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

        # 13. Write root VALIDATION_REPORT.md
        try:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            report_path = os.path.join(root_dir, "VALIDATION_REPORT.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("# Timetable Validation & Constraint Verification Report\n\n")
                f.write(f"**Overall Verification Result**: {'PASS :white_check_mark:' if report.is_valid() else 'FAIL :x:'}\n\n")
                
                f.write("## Overview Metrics\n")
                f.write(f"- **Constraint Satisfaction Rate**: {constraint_satisfaction}%\n")
                f.write(f"- **Timetable Fitness Score**: {fitness_score}%\n")
                f.write(f"- **Total Schedule Allocations**: {len(schedule)}\n")
                f.write(f"- **Total Violations Detected**: {len(report.errors)}\n\n")
                
                f.write("## Rule-by-Rule Analysis\n")
                f.write("| Rule Name | Type | Status | Summary of Findings |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                for rule, meta in rule_statuses.items():
                    status_icon = ":white_check_mark: PASS" if meta["status"] == "PASS" else f":x: {meta['status']}"
                    summary = "Satisfied with zero clashes." if meta["status"] == "PASS" else "; ".join(meta["details"][:2])
                    f.write(f"| {rule} | {meta['type']} | {status_icon} | {summary} |\n")
                f.write("\n")
                
                if not report.is_valid():
                    f.write("## Conflict Explanations & Exploded Diagnostics\n")
                    for rule, meta in rule_statuses.items():
                        if meta["status"] != "PASS":
                            f.write(f"### {rule} - {meta['status']}\n")
                            for detail in meta["details"]:
                                f.write(f"- {detail}\n")
                            f.write("\n")
                            
                    f.write("## Suggested Rule Relaxations\n")
                    for suggestion in report.suggested_repairs:
                        f.write(f"- {suggestion}\n")
                    f.write("\n")
                else:
                    f.write("## Conflict Explanations & Exploded Diagnostics\n")
                    f.write("- All constraints are fully satisfied. No rule conflicts found.\n")
                    
        except Exception as e:
            print(f"Error writing VALIDATION_REPORT.md: {e}")

        # Also write the legacy SCHEDULER_VALIDATION_REPORT.md to avoid breaking other legacy modules
        try:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            legacy_path = os.path.join(root_dir, "SCHEDULER_VALIDATION_REPORT.md")
            with open(legacy_path, "w", encoding="utf-8") as f:
                f.write("# Timetable Scheduler Validation Report\n\n")
                f.write(f"**Verification Status**: {'PASS' if report.is_valid() else 'FAIL'}\n\n")
                f.write("## Overview Metrics\n")
                f.write(f"- Total Allocations: {len(schedule)}\n")
                f.write(f"- Hard Constraint Violations (Errors): {len(report.errors)}\n")
                f.write(f"- Soft Preference Violations (Warnings): {len(report.warnings)}\n\n")
                if report.errors:
                    f.write("## Violations & Conflict Explanations\n")
                    for err in report.errors:
                        f.write(f"- :x: {err}\n")
                else:
                    f.write("## Violations & Conflict Explanations\n")
                    f.write("- :white_check_mark: All constraints validated successfully.\n")
        except Exception:
            pass

        return report

    @staticmethod
    def detect_conflicts(context: ValidationContext) -> List[Dict[str, str]]:
        conflicts = []
        return conflicts
