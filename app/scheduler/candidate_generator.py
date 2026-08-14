"""Candidate generation and ranking engine for scheduling sessions."""
from typing import Any, Dict, List, Tuple
from app.core.domain import Schedule, Course
from app.scheduler.session import Session
from app.validators.validator import MasterValidator, ValidationContext
from app.validators.soft_constraints import score_balanced_faculty_workload


class CandidateGenerator:
    """Generates and ranks valid slot placements (day, period, room) for sessions."""

    @staticmethod
    def generate_sessions(course: Course, section_id: str, faculty_id: str) -> List[Session]:
        """Splits a course into separate Theory, Tutorial, and Practical scheduling sessions."""
        sessions = []

        # 1. Theory sessions (L independent sessions of duration 1)
        for i in range(1, course.l + 1):
            sessions.append(Session(
                session_id=f"{course.course_id}_{section_id}_L{i}",
                course_id=course.course_id,
                section_id=section_id,
                faculty_id=faculty_id,
                type="THEORY",
                duration=1,
                has_lab=False
            ))

        # 2. Tutorial sessions (T independent sessions of duration 1)
        for i in range(1, course.t + 1):
            sessions.append(Session(
                session_id=f"{course.course_id}_{section_id}_T{i}",
                course_id=course.course_id,
                section_id=section_id,
                faculty_id=faculty_id,
                type="TUTORIAL",
                duration=1,
                has_lab=False
            ))

        # 3. Practical sessions (1 consecutive block of duration P)
        if course.p > 0:
            sessions.append(Session(
                session_id=f"{course.course_id}_{section_id}_P",
                course_id=course.course_id,
                section_id=section_id,
                faculty_id=faculty_id,
                type="PRACTICAL",
                duration=course.p,
                has_lab=course.has_lab
            ))

        return sessions

    @staticmethod
    def get_valid_candidates(
        session: Session,
        current_schedule: List[Schedule],
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ) -> List[Tuple[int, int, str]]:
        """
        Finds all valid candidate slots (day, period, room/lab) for a session.
        For practical blocks (duration > 1), finds valid consecutive slots.
        """
        candidates = []

        # Select search space for rooms
        room_choices = labs if session.has_lab else rooms
        if session.has_lab:
            if context.course_labs and session.course_id in context.course_labs:
                mapped_lab = context.course_labs[session.course_id]
                if mapped_lab in labs:
                    room_choices = [mapped_lab]
        else:
            # Permanent classroom constraint
            perm_room = context.room_sections.get(session.section_id)
            if perm_room:
                room_choices = [perm_room]

        # Iterate through working days and periods
        for day in sorted(context.working_days):
            # Sort template slots for this day to iterate sequentially
            day_periods = sorted([p for d, p in context.template_slots if d == day])

            for i in range(len(day_periods) - session.duration + 1):
                # Candidate starting period
                periods = day_periods[i:i + session.duration]

                # Check if periods are mathematically consecutive (e.g. [1, 2] or [2, 3])
                if len(periods) != session.duration or any(
                    periods[idx] + 1 != periods[idx + 1] for idx in range(len(periods) - 1)
                ):
                    continue

                # Ensure practical lab periods do not cross BREAK (between P2 and P3) or LUNCH (between P4 and P5)
                # Only apply this constraint in standard full-day schedules (where max period is at least 5)
                if max(day_periods) >= 5:
                    period_set = set(periods)
                    if 2 in period_set and 3 in period_set:
                        continue
                    if 4 in period_set and 5 in period_set:
                        continue

                for room in room_choices:
                    # Create temporary allocation objects for the block
                    allocations = []
                    for p in periods:
                        alloc = Schedule(
                            run_id=1,
                            section_id=session.section_id,
                            day_id=day,
                            period_no=p,
                            course_id=session.course_id,
                            faculty_id=session.faculty_id,
                            year=2026,
                            semester=1,
                            room_no=None if session.has_lab else room,
                            lab_room_no=room if session.has_lab else None
                        )
                        allocations.append(alloc)

                    # Validate all slots in the block
                    block_valid = True
                    temp_schedule = list(current_schedule)

                    for alloc in allocations:
                        if not MasterValidator.validate_allocation_fast(alloc, temp_schedule, context):
                            block_valid = False
                            break
                        temp_schedule.append(alloc)

                    if block_valid:
                        candidates.append((day, periods[0], room))

        return candidates

    @staticmethod
    def rank_candidates(
        candidates: List[Tuple[int, int, str]],
        session: Session,
        current_schedule: List[Schedule],
        context: ValidationContext
    ) -> List[Tuple[int, int, str]]:
        """
        Ranks candidate slots deterministically.

        Phase Omega.5 fixes vs original:
        - REMOVED: lab_penalty <= 4 that locked ALL labs to morning (periods 1-4).
        - REMOVED: student_gap_penalty = period on new days (caused period-1 clustering
          for ALL session types, not just labs).
        - ADDED: per-section hash rotation for labs so different sections prefer
          different starting periods (distributes labs naturally across the day).
        - Theory/Tutorial: soft preference for period 3 (mid-morning), away from extremes.
        - New days: gap_penalty = 0 (neutral) so sessions spread across the week.
        """
        # Stable per-section offset: different sections prefer labs to start at
        # different periods (period 1 through 4), making the schedule visually varied.
        _sec_id = session.section_id or ""
        section_hash = sum(ord(c) for c in _sec_id) % 4  # 0..3 (stable, not Python hash())

        def ranking_key(c: Tuple[int, int, str]) -> Tuple[int, int, int, int, int, str]:
            day, period, room = c

            # --- Heuristic 1: Period placement preference ---
            if session.type in ("THEORY", "TUTORIAL"):
                # Theory/Tutorial: soft preference for period 3 (middle of morning).
                # Prevents clustering at period 1 while still preferring morning.
                # Distance from period 3: p1=2, p2=1, p3=0, p4=1, p5=2, p6=3
                period_pref = abs(period - 3)
            else:
                # Practical/Lab: preferred start period rotated per section.
                # section_hash=0 -> prefer period 1, =1 -> period 2, etc.
                preferred_start = section_hash + 1  # 1..4
                period_pref = abs(period - preferred_start)

            # --- Heuristic 2: Compact student schedule ---
            sec_slots = [
                s.period_no for s in current_schedule
                if s.section_id == session.section_id and s.day_id == day
            ]
            if sec_slots:
                # Day already has sessions: prefer adjacent slots to minimise gaps
                min_dist = min(abs(period - p) for p in sec_slots)
                student_gap_penalty = min_dist
            else:
                # New day for this section: neutral (gap_penalty = 0).
                # Let period_pref and fac_load drive the choice.
                # Using period here would re-introduce the period-1 clustering bug.
                student_gap_penalty = 0

            # --- Heuristic 3: Balanced faculty workload ---
            fac_load = sum(
                1 for s in current_schedule
                if s.faculty_id == session.faculty_id and s.day_id == day
            )

            # Tie-breaker: day (spread across week), then period, then room
            return (period_pref, student_gap_penalty, fac_load, day, period, room)

        return sorted(candidates, key=ranking_key)
