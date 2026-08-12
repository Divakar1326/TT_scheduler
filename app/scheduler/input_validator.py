"""
Pre-flight Input Validator for the Scheduling Pipeline.

Validates all required entities before the CSP solver is invoked.
Abort scheduling immediately if any check fails -- do NOT proceed
with partial / corrupt input data.
"""
from typing import Dict, List, Set, Tuple
import time
from config.config import logger


class InputValidationError(ValueError):
    """Raised when required scheduling data is missing or inconsistent."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


class PipelineTrace:
    """Lightweight per-stage timing tracer for the scheduling pipeline."""

    def __init__(self, run_start: float):
        self._run_start = run_start
        self._stages: List[Dict] = []
        self._current_stage: str = ""
        self._stage_start: float = run_start

    def begin(self, stage: str) -> None:
        self._current_stage = stage
        self._stage_start = time.time()
        elapsed = round(self._stage_start - self._run_start, 3)
        logger.info(f"[PIPELINE] >> STAGE: {stage!r:<40} | T+{elapsed:.3f}s")

    def end(self, stage: str, detail: str = "") -> float:
        now = time.time()
        duration = round(now - self._stage_start, 3)
        total_elapsed = round(now - self._run_start, 3)
        self._stages.append({
            "stage": stage,
            "duration_ms": round(duration * 1000, 1),
            "elapsed_s": total_elapsed,
            "detail": detail
        })
        log_detail = f" | {detail}" if detail else ""
        logger.info(
            f"[PIPELINE] DONE:   {stage!r:<40} | {duration * 1000:.1f}ms{log_detail}"
        )
        return duration

    def summary(self) -> str:
        lines = ["", "=" * 72, "PIPELINE EXECUTION SUMMARY", "=" * 72]
        total = sum(s["duration_ms"] for s in self._stages)
        for s in self._stages:
            bar = "#" * max(1, int(s["duration_ms"] / max(1, total) * 40))
            lines.append(
                f"  {s['stage']:<38} {s['duration_ms']:>8.1f} ms  {bar}"
            )
        lines.append("-" * 72)
        lines.append(f"  {'TOTAL':<38} {total:>8.1f} ms")
        lines.append("=" * 72)
        return "\n".join(lines)

    def log_summary(self) -> None:
        logger.info(self.summary())


class InputValidator:
    """
    Validates all required scheduling data before the CSP engine runs.

    Call `InputValidator.validate_all(...)` and check the returned errors list.
    If errors is non-empty, abort scheduling and surface them to the caller.
    """

    @staticmethod
    def validate_all(
        department_id: str,
        sections: list,
        courses: list,
        faculty_list: list,
        rooms_list: List[str],
        labs_list: List[str],
        faculty_map: dict,
        fac_course_map: dict,
        section_courses: Dict[str, List[str]],
        working_days: Set[int],
        template_slots: Set[Tuple[int, int]],
        academic_year: Tuple[int, int],
        course_dict: dict
    ) -> List[str]:
        """
        Runs all pre-flight checks. Returns a list of error strings.
        An empty list means all checks passed.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # -- 1. Department ----------------------------------------------------
        if not department_id or not department_id.strip():
            errors.append("ABORT: department_id is empty or null. "
                          "Cannot schedule without a target department.")

        # -- 2. Academic Year -------------------------------------------------
        year, semester = academic_year
        if not year or year <= 0:
            errors.append("ABORT: No active academic year found in the "
                          "'academic_year' table. Add an active year/semester "
                          "record before scheduling.")
        if not semester or semester <= 0:
            errors.append("ABORT: Academic semester is invalid (must be > 0).")

        # -- 3. Sections ------------------------------------------------------
        dept_sections = [s for s in sections
                         if s.department_id and
                         s.department_id.upper() == department_id.upper()]
        if not dept_sections:
            errors.append(
                f"ABORT: No sections found for department '{department_id}'. "
                "Create sections in the Sections module and assign them to "
                "this department before scheduling."
            )

        # -- 4. Courses -------------------------------------------------------
        if not courses:
            errors.append(
                "ABORT: No courses exist in the system. "
                "Import or create courses first."
            )

        # Check which dept sections actually have courses assigned
        sections_with_courses = 0
        for sec in dept_sections:
            assigned = section_courses.get(sec.section_id, [])
            if assigned:
                sections_with_courses += 1
        if dept_sections and sections_with_courses == 0:
            errors.append(
                f"ABORT: Sections in department '{department_id}' have no "
                "courses assigned. Use the HOD Assignment screen to link "
                "courses to sections before scheduling."
            )

        # -- 5. Faculty -------------------------------------------------------
        dept_faculty = [f for f in faculty_list
                        if f.department_id and
                        f.department_id.upper() == department_id.upper()]
        active_faculty = [f for f in dept_faculty if f.status == "ACTIVE"]
        if not dept_faculty:
            warnings.append(
                f"WARNING: No faculty specifically assigned to department "
                f"'{department_id}'. Global faculty pool will be used."
            )
        elif not active_faculty:
            errors.append(
                f"ABORT: All faculty in department '{department_id}' have "
                "inactive status. Activate at least one faculty member."
            )

        # -- 6. Faculty-Course Mappings ---------------------------------------
        if not faculty_map and not fac_course_map:
            errors.append(
                "ABORT: No faculty-course mappings exist. "
                "Use the HOD Assignment screen to assign faculty to courses "
                "before scheduling."
            )

        # Warn about courses with no faculty assigned
        unmapped_courses: List[str] = []
        for sec in dept_sections:
            assigned_course_ids = section_courses.get(sec.section_id, [])
            for cid in assigned_course_ids:
                if (sec.section_id, cid) not in faculty_map:
                    if cid not in fac_course_map:
                        unmapped_courses.append(
                            f"{cid} (section {sec.section_id})"
                        )
        if unmapped_courses:
            warnings.append(
                f"WARNING: {len(unmapped_courses)} course(s) have no faculty "
                f"assigned -- a fallback faculty will be used: "
                f"{', '.join(unmapped_courses[:5])}"
                f"{'...' if len(unmapped_courses) > 5 else ''}"
            )

        # -- 7. Rooms ---------------------------------------------------------
        if not rooms_list:
            errors.append(
                f"ABORT: No classrooms available for department "
                f"'{department_id}'. Add rooms in the Rooms module."
            )

        # -- 8. Labs (only required if any lab course exists) -----------------
        dept_course_ids = set()
        for sec in dept_sections:
            dept_course_ids.update(section_courses.get(sec.section_id, []))
        has_lab_courses = any(
            course_dict.get(cid) and course_dict[cid].has_lab
            for cid in dept_course_ids
        )
        if has_lab_courses and not labs_list:
            errors.append(
                f"ABORT: Department '{department_id}' has lab courses but no "
                "labs are configured. Add labs in the Labs module and link "
                "them to lab courses via course-lab mappings."
            )

        # -- 9. Working Days & Template Slots ---------------------------------
        if not working_days:
            errors.append(
                "ABORT: No working days configured. "
                "The template must define at least 1 working day."
            )
        if not template_slots:
            errors.append(
                "ABORT: No template slots configured. "
                "The timetable template must define active period slots."
            )
        elif len(template_slots) < 5:
            warnings.append(
                f"WARNING: Only {len(template_slots)} template slots are "
                "active -- this is unusually low and may cause partial "
                "scheduling."
            )

        # -- 10. LTP Consistency ----------------------------------------------
        ltp_issues: List[str] = []
        for cid in dept_course_ids:
            course = course_dict.get(cid)
            if not course:
                continue
            ltp_sum = course.l + course.t + course.p
            if ltp_sum > 0 and ltp_sum != course.weekly_hours:
                ltp_issues.append(
                    f"{cid}: L={course.l}+T={course.t}+P={course.p}="
                    f"{ltp_sum} != weekly_hours={course.weekly_hours}"
                )
        if ltp_issues:
            warnings.append(
                f"WARNING: L+T+P != weekly_hours for {len(ltp_issues)} "
                f"course(s). Scheduler will use L+T+P as the actual session "
                f"count: {', '.join(ltp_issues[:3])}"
                f"{'...' if len(ltp_issues) > 3 else ''}"
            )

        # Log all warnings even if we don't abort
        for w in warnings:
            logger.warning(f"[INPUT VALIDATOR] {w}")

        # Log all errors
        for e in errors:
            logger.error(f"[INPUT VALIDATOR] {e}")

        if errors:
            logger.error(
                f"[INPUT VALIDATOR] PRE-FLIGHT FAILED -- "
                f"{len(errors)} error(s), {len(warnings)} warning(s). "
                "Scheduling aborted."
            )
        else:
            logger.info(
                f"[INPUT VALIDATOR] PRE-FLIGHT PASSED -- "
                f"dept={department_id!r}, sections={len(dept_sections)}, "
                f"faculty={len(dept_faculty)}, rooms={len(rooms_list)}, "
                f"labs={len(labs_list)}, warnings={len(warnings)}"
            )

        return errors
