"""Backtracking Engine executing CSP search for conflict-free timetables."""
import time
from typing import Any, Dict, List, Optional, Tuple
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.scheduler import Scheduler
from app.scheduler.candidate_generator import CandidateGenerator
from app.validators.validator import ValidationContext, MasterValidator
from app.core.domain import Schedule

# Maximum wall-clock seconds the CSP solver runs before using best partial solution
_SOLVER_TIME_LIMIT_SECONDS = 120


class BacktrackStats:
    """Tracks stats for backtracking execution analysis."""
    def __init__(self):
        self.nodes_explored: int = 0
        self.backtracks: int = 0
        self.successful_allocations: int = 0
        self.failed_allocations: int = 0
        self.max_depth: int = 0
        self.start_time: float = 0.0
        self.execution_time: float = 0.0

    def start(self):
        self.start_time = time.time()

    def stop(self):
        self.execution_time = time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes_explored": self.nodes_explored,
            "backtracks": self.backtracks,
            "successful_allocations": self.successful_allocations,
            "failed_allocations": self.failed_allocations,
            "max_depth": self.max_depth,
            "execution_time_seconds": round(self.execution_time, 4)
        }


def _interleave_sessions_by_section(sessions: List[Session]) -> List[Session]:
    """
    Organise sessions so that theory/tutorial/practical within each section are
    interleaved round-robin across sections -- preventing the global PRACTICAL-first
    ordering that caused entire mornings to fill with back-to-back lab sessions.

    Strategy:
      1. Group sessions by section_id.
      2. Within each group sort: THEORY < TUTORIAL < PRACTICAL.
      3. Interleave groups round-robin so every section gets one slot scheduled
         before any section gets its second slot.
    """
    from collections import defaultdict

    def type_order(s: Session) -> int:
        if s.type == "THEORY": return 0
        if s.type == "TUTORIAL": return 1
        return 2  # PRACTICAL

    groups: Dict[str, List[Session]] = defaultdict(list)
    for s in sessions:
        groups[s.section_id].append(s)

    for sec_id in groups:
        groups[sec_id].sort(key=lambda s: (type_order(s), s.session_id))

    section_order = sorted(groups.keys())
    queues = [groups[k] for k in section_order]

    interleaved: List[Session] = []
    max_len = max((len(q) for q in queues), default=0)
    for i in range(max_len):
        for queue in queues:
            if i < len(queue):
                interleaved.append(queue[i])
    return interleaved


class BacktrackingSolver:
    """Solves timetable scheduling using recursive search with forward checking."""

    def __init__(self):
        self.stats = BacktrackStats()
        self.solutions: List[Tuple[List[Schedule], float]] = []
        self.best_partial_solution: Tuple[List[Schedule], List[Session]] = ([], [])
        self._time_limit: float = _SOLVER_TIME_LIMIT_SECONDS
        self._deadline: float = 0.0

    def _select_next_session(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ) -> Optional[Session]:
        """Select next session using the MRV heuristic -- always applied."""
        if not state.remaining_sessions:
            return None
        best_session = None
        min_count = float("inf")
        for session in state.remaining_sessions:
            cands = CandidateGenerator.get_valid_candidates(
                session, state.allocations, context, rooms, labs
            )
            if len(cands) < min_count:
                min_count = len(cands)
                best_session = session
        return best_session

    def _forward_checking(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ) -> bool:
        """Fail early if ANY remaining session has zero valid candidates."""
        for session in state.remaining_sessions:
            if not CandidateGenerator.get_valid_candidates(
                session, state.allocations, context, rooms, labs
            ):
                return False
        return True

    def solve(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str],
        allow_partial: bool = False
    ) -> bool:
        """Standard solve returning boolean (for compatibility and tests)."""
        for _ in self.solve_generator(state, context, rooms, labs, allow_partial):
            pass
        return len(state.allocations) > 0 or not state.remaining_sessions

    def solve_generator(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str],
        allow_partial: bool = False
    ):
        """Solve timetable scheduling, yielding progress updates during search."""
        self.solutions = []
        self.best_partial_solution = ([], [])
        self.stats = BacktrackStats()
        self.stats.start()
        self.initial_remaining_count = len(state.remaining_sessions)
        self._deadline = time.time() + self._time_limit

        # Section-first interleaved ordering -- fixes lab clustering.
        # Each section gets theory sessions placed before its own practicals,
        # and round-robin interleaving prevents one section monopolising the search.
        state.remaining_sessions = _interleave_sessions_by_section(state.remaining_sessions)

        yield from self._search(state, context, rooms, labs, 1)

        self.stats.stop()

        if self.solutions:
            self.solutions.sort(key=lambda x: x[1], reverse=True)
            best_allocs, best_fit = self.solutions[0]
            state.allocations = best_allocs
            state.remaining_sessions = []
            self._generate_debug_report(state, [], context, rooms, labs)
        elif allow_partial and len(self.best_partial_solution[1]) < self.initial_remaining_count:
            state.allocations = self.best_partial_solution[0]
            state.remaining_sessions = self.best_partial_solution[1]
            self._generate_debug_report(state, state.remaining_sessions, context, rooms, labs)

    def _search(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str],
        depth: int
    ):
        """Recursive solver with MRV, LCV, lab-spread penalty, and wall-clock timeout."""
        if len(self.solutions) >= 10:
            return
        # Wall-clock time limit -- prevents infinite loops on hard instances
        if time.time() > self._deadline:
            return

        self.stats.max_depth = max(self.stats.max_depth, depth)
        self.stats.nodes_explored += 1

        if self.stats.nodes_explored % 5 == 0:
            yield {
                "nodes_explored": self.stats.nodes_explored,
                "scheduled_classes": len(state.allocations),
                "remaining_classes": len(state.remaining_sessions)
            }

        if depth == 1 or len(state.remaining_sessions) < len(self.best_partial_solution[1]):
            self.best_partial_solution = (list(state.allocations), list(state.remaining_sessions))

        # Base Case: timetable is complete
        if not state.remaining_sessions:
            allocs_copy = list(state.allocations)
            total_penalty = MasterValidator.calculate_total_penalty(allocs_copy, context)
            fitness_score = max(0.0, round(
                (1.0 - total_penalty / max(1, len(allocs_copy) * 10)) * 100, 2
            ))
            self.solutions.append((allocs_copy, fitness_score))
            return

        # MRV: pick the session with the fewest remaining valid candidates
        session = self._select_next_session(state, context, rooms, labs)
        if not session:
            return

        candidates = CandidateGenerator.get_valid_candidates(
            session, state.allocations, context, rooms, labs
        )
        if not candidates:
            self.stats.failed_allocations += 1
            return

        # LCV: always compute scores for up to 5 neighbours
        other_sessions = [s for s in state.remaining_sessions if s.session_id != session.session_id]
        # Use year/semester from state (not hard-coded)
        _year = state.year
        _semester = state.semester
        lcv_scores: Dict = {}
        for cand in candidates:
            day, period, room = cand
            temp_alloc = Schedule(
                run_id=1, section_id=session.section_id, day_id=day, period_no=period,
                course_id=session.course_id, faculty_id=session.faculty_id,
                room_no=None if session.has_lab else room,
                lab_room_no=room if session.has_lab else None,
                year=_year, semester=_semester
            )
            temp_schedule = state.allocations + [temp_alloc]
            choices_left = sum(
                len(CandidateGenerator.get_valid_candidates(os, temp_schedule, context, rooms, labs))
                for os in other_sessions[:5]
            )
            lcv_scores[cand] = choices_left

        def lcv_ranking_key(c):
            day, period, room = c
            # Maximise remaining choices (LCV)
            lcv_penalty = -lcv_scores.get(c, 0)
            # Lab spread: strongly penalise a second lab for this section on the same day
            lab_spread_penalty = (
                10 * sum(
                    1 for s in state.allocations
                    if s.section_id == session.section_id and s.day_id == day and s.lab_room_no
                )
                if session.has_lab else 0
            )
            # Lab period-spread: penalise scheduling a lab at a period where another lab
            # for this SAME section already starts (across any day). This prevents all labs
            # from clustering at period 1 while still allowing consecutive blocks.
            # We check only the first period of existing lab blocks (distinct start periods).
            lab_period_spread_penalty = 0
            if session.has_lab:
                existing_lab_starts = set(
                    s.period_no for s in state.allocations
                    if s.section_id == session.section_id and s.lab_room_no
                    # Count only the minimum period of each day's lab block as the "start"
                    # (avoids double-counting consecutive periods within one block)
                )
                # Penalise proportionally to how crowded this start period already is
                lab_period_spread_penalty = 3 * sum(
                    1 for p in existing_lab_starts if p == period
                )
            # Compact student schedule
            sec_slots = [
                s.period_no for s in state.allocations
                if s.section_id == session.section_id and s.day_id == day
            ]
            student_gap_penalty = (
                min(abs(period - p) for p in sec_slots) - 1
                if sec_slots else 0
            )
            # Faculty daily workload balance
            fac_load = sum(
                1 for s in state.allocations
                if s.faculty_id == session.faculty_id and s.day_id == day
            )
            return (lcv_penalty, lab_spread_penalty, lab_period_spread_penalty,
                    student_gap_penalty, fac_load, day, period, room)

        ranked_candidates = sorted(candidates, key=lcv_ranking_key)

        for candidate in ranked_candidates:
            if time.time() > self._deadline:
                return

            snapshot = state.take_snapshot()
            if not Scheduler.allocate_session(session, [candidate], state):
                continue

            if not self._forward_checking(state, context, rooms, labs):
                state.restore_snapshot(snapshot)
                continue

            self.stats.successful_allocations += 1
            yield from self._search(state, context, rooms, labs, depth + 1)

            if len(self.solutions) >= 10:
                return

            state.restore_snapshot(snapshot)
            self.stats.backtracks += 1

    def _generate_debug_report(
        self,
        state: SchedulingState,
        unscheduled_sessions: List[Session],
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ):
        import os
        try:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            report_path = os.path.join(root_dir, "SCHEDULER_DEBUG_REPORT.md")
            status = "SUCCESS" if not unscheduled_sessions else "PARTIAL SUCCESS"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("# Scheduler Execution Diagnostics\n\n")
                f.write(f"**Status**: {status}\n\n")
                f.write("## Metrics\n")
                f.write(f"- Nodes Explored: {self.stats.nodes_explored}\n")
                f.write(f"- Backtracks: {self.stats.backtracks}\n")
                f.write(f"- Successful Allocations: {self.stats.successful_allocations}\n")
                f.write(f"- Failed Allocations: {self.stats.failed_allocations}\n")
                f.write(f"- Max Search Depth: {self.stats.max_depth}\n\n")
                if unscheduled_sessions:
                    f.write("## Unscheduled Sessions\n")
                    for s in unscheduled_sessions:
                        reason = self._diagnose_session(s, state.allocations, context, rooms, labs)
                        f.write(f"- {s.session_id} ({s.course_id}/{s.section_id}/{s.faculty_id}): {reason}\n")
        except Exception as e:
            print(f"Error writing SCHEDULER_DEBUG_REPORT.md: {e}")

    def _diagnose_session(
        self,
        s: Session,
        allocations: List[Schedule],
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ) -> str:
        if not s.faculty_id:
            return "No faculty assigned to course"
        if not (labs if s.has_lab else rooms):
            return "No rooms/labs available in the search space"
        return "Hard constraint clash across all template slots"
