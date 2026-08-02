"""Candidate generation and ranking engine for scheduling sessions."""
from typing import Any, Dict, List, Tuple
from app.models.domain import Schedule, Course
from app.scheduler.session import Session
from app.constraints.validator import MasterValidator, ValidationContext
from app.constraints.soft_constraints import score_balanced_faculty_workload

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
        if not session.has_lab:
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
                if len(periods) != session.duration or any(periods[idx] + 1 != periods[idx + 1] for idx in range(len(periods) - 1)):
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
                        # Validate this slot against current schedule + other slots in this block
                        is_valid, _ = MasterValidator.validate_allocation(alloc, temp_schedule, context)
                        if not is_valid:
                            block_valid = False
                            break
                        # Add to temp schedule so subsequent slots check against this one (e.g. faculty/room clash within block)
                        temp_schedule.append(alloc)
                    
                    if block_valid:
                        # Candidate is identified by day, starting period, and room
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
        Sorting order:
        1. Lab morning slot preference (Morning starts sorted first).
        2. Workload balance (Lower faculty daily workload preferred).
        3. Deterministic tie-breaker (day_id, period_no, room_no).
        """
        def ranking_key(c: Tuple[int, int, str]) -> Tuple[int, int, int, int, str]:
            day, period, room = c
            
            # Heuristic 1: Morning lab preference
            # If session is practical lab class and period starts after Period 4, penalize (1), else (0)
            lab_penalty = 1 if (session.has_lab and period > 4) else 0
            
            # Heuristic 2: Balanced faculty workload
            # Calculate faculty class count on this day
            fac_load = sum(1 for s in current_schedule if s.faculty_id == session.faculty_id and s.day_id == day)
            
            # Tie breakers
            return (lab_penalty, fac_load, day, period, room)

        return sorted(candidates, key=ranking_key)
