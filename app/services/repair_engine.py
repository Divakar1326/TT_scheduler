"""Repair Engine resolving conflicts in generated timetables using local search."""
from typing import Any, Dict, List, Tuple, Optional
from app.core.domain import Schedule
from app.validators.validator import ValidationContext, MasterValidator
from app.validators.timetable_validator import TimetableValidator
import random

class RepairStats:
    """Tracks repair metrics."""
    def __init__(self):
        self.repaired_count: int = 0
        self.failed_count: int = 0
        self.initial_penalty: int = 0
        self.final_penalty: int = 0
        self.iterations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repaired_count": self.repaired_count,
            "failed_count": self.failed_count,
            "initial_penalty": self.initial_penalty,
            "final_penalty": self.final_penalty,
            "iterations": self.iterations
        }


class RepairEngine:
    """Executes iterative move and swap repairs to resolve scheduling conflicts."""

    @staticmethod
    def repair_timetable(
        schedule: List[Schedule],
        context: ValidationContext,
        rooms: List[str],
        labs: List[str],
        max_iterations: int = 50
    ) -> Tuple[List[Schedule], Dict[str, Any], List[str]]:
        """
        Attempts to resolve conflicts in the schedule iteratively.
        Returns Tuple (repaired_schedule, stats_dict, remaining_errors).
        """
        stats = RepairStats()
        repaired_schedule = [
            Schedule(
                run_id=s.run_id, section_id=s.section_id, day_id=s.day_id, period_no=s.period_no,
                course_id=s.course_id, faculty_id=s.faculty_id, room_no=s.room_no, lab_room_no=s.lab_room_no,
                year=s.year, semester=s.semester, schedule_id=s.schedule_id
            )
            for s in schedule
        ]

        # Calculate initial soft penalty
        initial_report = TimetableValidator.validate_timetable(repaired_schedule, context, rooms, labs)
        stats.initial_penalty = initial_report.stats.get("warning_count", 0) # Use warning count as simple proxy
        
        if initial_report.is_valid():
            stats.final_penalty = stats.initial_penalty
            return repaired_schedule, stats.to_dict(), []

        for iteration in range(1, max_iterations + 1):
            stats.iterations = iteration
            report = TimetableValidator.validate_timetable(repaired_schedule, context, rooms, labs)
            
            if report.is_valid():
                break

            # Process the first error
            error_msg = report.errors[0]
            
            # Find a conflicted allocation to shift
            conflicted_alloc: Optional[Schedule] = None
            for s in repaired_schedule:
                day_str = f"Day {s.day_id}"
                period_str = f"Period {s.period_no}"
                if (s.faculty_id in error_msg or s.section_id in error_msg or s.course_id in error_msg or (s.room_no and s.room_no in error_msg) or (s.lab_room_no and s.lab_room_no in error_msg)):
                    if day_str in error_msg and period_str in error_msg:
                        conflicted_alloc = s
                        break
            if not conflicted_alloc:
                for s in repaired_schedule:
                    if (s.faculty_id in error_msg or s.section_id in error_msg or s.course_id in error_msg or (s.room_no and s.room_no in error_msg) or (s.lab_room_no and s.lab_room_no in error_msg)):
                        conflicted_alloc = s
                        break
            
            if not conflicted_alloc:
                conflicted_alloc = repaired_schedule[0]

            course = context.course_dict.get(conflicted_alloc.course_id)
            if not course:
                continue

            # Identify if it is part of a consecutive block (P > 1)
            is_practical = course.p > 1
            block_allocs = []
            if is_practical:
                # Find all allocations of this course in the section (all days) to allow regrouping
                block_allocs = [
                    s for s in repaired_schedule 
                    if s.section_id == conflicted_alloc.section_id and s.course_id == conflicted_alloc.course_id
                ]
            else:
                block_allocs = [conflicted_alloc]

            # Collect currently occupied slot coordinates
            occupied_slots = set((s.day_id, s.period_no, s.room_no or s.lab_room_no) for s in repaired_schedule)

            # --- Try Move Heuristic ---
            moved_successfully = False
            for day in context.working_days:
                day_periods = sorted(list(set(p for d, p in context.template_slots if d == day)))
                
                # Check consecutive slots for the block length
                for i in range(len(day_periods) - len(block_allocs) + 1):
                    target_periods = day_periods[i:i + len(block_allocs)]
                    
                    for room in (labs if course.has_lab else rooms):
                        # Verify target slots are empty
                        if any((day, p, room) in occupied_slots for p in target_periods):
                            continue
                        
                        # Temporarily apply move
                        original_slots = [(s.day_id, s.period_no, s.room_no, s.lab_room_no) for s in block_allocs]
                        for idx, s in enumerate(block_allocs):
                            s.day_id = day
                            s.period_no = target_periods[idx]
                            if course.has_lab:
                                s.lab_room_no = room
                                s.room_no = None
                            else:
                                s.room_no = room
                                s.lab_room_no = None
                        
                        # Validate new state
                        temp_report = TimetableValidator.validate_timetable(repaired_schedule, context, rooms, labs)
                        # We accept the move if it decreases total errors
                        if len(temp_report.errors) < len(report.errors):
                            moved_successfully = True
                            stats.repaired_count += 1
                            break
                        else:
                            # Revert
                            for idx, s in enumerate(block_allocs):
                                s.day_id = original_slots[idx][0]
                                s.period_no = original_slots[idx][1]
                                s.room_no = original_slots[idx][2]
                                s.lab_room_no = original_slots[idx][3]
                    
                    if moved_successfully:
                        break
                if moved_successfully:
                    break

            if moved_successfully:
                continue

            # --- Try Swap Heuristic ---
            swapped_successfully = False
            for target_alloc in repaired_schedule:
                if target_alloc in block_allocs:
                    continue
                target_course = context.course_dict.get(target_alloc.course_id)
                if not target_course:
                    continue

                # Try swapping EACH member of block_allocs with target_alloc
                for conflicted_member in block_allocs:
                    s_day, s_period = conflicted_member.day_id, conflicted_member.period_no
                    
                    conflicted_member.day_id, conflicted_member.period_no = target_alloc.day_id, target_alloc.period_no
                    target_alloc.day_id, target_alloc.period_no = s_day, s_period
                    
                    # Validate swap
                    temp_report = TimetableValidator.validate_timetable(repaired_schedule, context, rooms, labs)
                    if len(temp_report.errors) < len(report.errors):
                        swapped_successfully = True
                        stats.repaired_count += 1
                        break
                    else:
                        # Revert swap
                        t_day, t_period = target_alloc.day_id, target_alloc.period_no
                        target_alloc.day_id, target_alloc.period_no = conflicted_member.day_id, conflicted_member.period_no
                        conflicted_member.day_id, conflicted_member.period_no = t_day, t_period
                
                if swapped_successfully:
                    break

            if not swapped_successfully and not moved_successfully:
                # If this iteration could not resolve the error, we increment failed count and break or continue
                stats.failed_count += 1
                break

        # Calculate final stats
        final_report = TimetableValidator.validate_timetable(repaired_schedule, context, rooms, labs)
        stats.final_penalty = final_report.stats.get("warning_count", 0)

        return repaired_schedule, stats.to_dict(), final_report.errors

    @staticmethod
    def optimize_timetable(
        schedule: List[Schedule],
        context: ValidationContext,
        rooms: List[str],
        labs: List[str],
        max_iterations: int = 150
    ) -> List[Schedule]:
        """
        Applies local search (hill climbing) swaps to reduce soft penalties while
        preserving hard constraint correctness.  Attempts to minimize gaps, balance
        workloads, avoid room changes, and distribute theory sessions across days.
        """
        optimized = [
            Schedule(
                run_id=s.run_id, section_id=s.section_id, day_id=s.day_id,
                period_no=s.period_no, course_id=s.course_id, faculty_id=s.faculty_id,
                room_no=s.room_no, lab_room_no=s.lab_room_no,
                year=s.year, semester=s.semester, schedule_id=s.schedule_id
            )
            for s in schedule
        ]

        current_penalty = MasterValidator.calculate_total_penalty(optimized, context)

        for iteration in range(max_iterations):
            improved = False

            # ── Move pass: shift a single theory session to a globally free slot ──
            for s in optimized:
                if s.lab_room_no:
                    # Never move lab sessions — they must stay consecutive
                    continue

                original_day = s.day_id
                original_period = s.period_no
                original_room = s.room_no

                # Build globally occupied (day, period) set, excluding this session
                global_occupied = set(
                    (x.day_id, x.period_no) for x in optimized if x is not s
                )

                # Candidate template slots that are globally free
                candidate_free = [
                    (t_day, t_period)
                    for (t_day, t_period) in context.template_slots
                    if (t_day, t_period) not in global_occupied
                ]
                if not candidate_free:
                    continue

                # Sample up to 10 free slots to keep runtime bounded
                sampled = random.sample(candidate_free, min(len(candidate_free), 10))

                # Room preference order: permanent room → original room → all rooms
                room_choices: List[str] = []
                perm_room = context.room_sections.get(s.section_id)
                if perm_room:
                    room_choices.append(perm_room)
                if original_room and original_room not in room_choices:
                    room_choices.append(original_room)
                for r in rooms:
                    if r not in room_choices:
                        room_choices.append(r)

                for f_day, f_period in sampled:
                    for room in room_choices:
                        if not room:
                            continue

                        s.day_id, s.period_no, s.room_no = f_day, f_period, room

                        other = [x for x in optimized if x is not s]
                        is_valid, _ = MasterValidator.validate_allocation(s, other, context)
                        if is_valid:
                            new_penalty = MasterValidator.calculate_total_penalty(optimized, context)
                            if new_penalty < current_penalty:
                                current_penalty = new_penalty
                                improved = True
                                break

                        # Revert this attempt
                        s.day_id, s.period_no, s.room_no = original_day, original_period, original_room

                    if improved:
                        break
                if improved:
                    break

            # ── Swap pass: exchange (day, period) between two theory sessions ──
            if not improved:
                for idx1 in range(len(optimized)):
                    s1 = optimized[idx1]
                    if s1.lab_room_no:
                        continue

                    for idx2 in range(idx1 + 1, len(optimized)):
                        s2 = optimized[idx2]
                        if s2.lab_room_no:
                            continue

                        # Swap
                        s1.day_id, s1.period_no, s2.day_id, s2.period_no = (
                            s2.day_id, s2.period_no, s1.day_id, s1.period_no
                        )

                        other_allocs = [
                            x for i, x in enumerate(optimized)
                            if i != idx1 and i != idx2
                        ]
                        v1, _ = MasterValidator.validate_allocation(s1, other_allocs + [s2], context)
                        v2, _ = MasterValidator.validate_allocation(s2, other_allocs + [s1], context)

                        if v1 and v2:
                            new_penalty = MasterValidator.calculate_total_penalty(optimized, context)
                            if new_penalty < current_penalty:
                                current_penalty = new_penalty
                                improved = True
                                break

                        # Revert swap
                        s1.day_id, s1.period_no, s2.day_id, s2.period_no = (
                            s2.day_id, s2.period_no, s1.day_id, s1.period_no
                        )
                    if improved:
                        break

            # Terminate if no improvement was found this iteration
            if not improved:
                break

        return optimized

