"""Backtracking Engine executing CSP search for conflict-free timetables."""
import time
from typing import Any, Dict, List, Optional, Tuple
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.scheduler import Scheduler
from app.scheduler.candidate_generator import CandidateGenerator
from app.constraints.validator import ValidationContext

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


class BacktrackingSolver:
    """Solves timetable scheduling using recursive search with forward checking."""

    def __init__(self):
        self.stats = BacktrackStats()

    def _select_next_session(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ) -> Optional[Tuple[Session, List[Tuple[int, int, str]]]]:
        """
        Orders sessions statically and returns Tuple (session, candidates) or None.
        """
        if not state.remaining_sessions:
            return None

        session = state.remaining_sessions[0]
        candidates = CandidateGenerator.get_valid_candidates(
            session, state.allocations, context, rooms, labs
        )
        return session, candidates

    def _forward_checking(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str]
    ) -> bool:
        """
        Looks ahead at all remaining sessions.
        Returns False if any remaining session has 0 valid candidates left.
        """
        for session in state.remaining_sessions:
            candidates = CandidateGenerator.get_valid_candidates(
                session, state.allocations, context, rooms, labs
            )
            if not candidates:
                # Early failure detection - dead end branch
                return False
        return True

    def solve(
        self,
        state: SchedulingState,
        context: ValidationContext,
        rooms: List[str],
        labs: List[str],
        depth: int = 1
    ) -> bool:
        """Recursively solves timetable slot allocations."""
        if depth == 1:
            self.stats.start()
            def get_type_priority(s: Session) -> int:
                if s.type == "PRACTICAL": return 0
                if s.type == "THEORY": return 1
                return 2
            state.remaining_sessions.sort(key=lambda s: (get_type_priority(s), s.session_id))

        self.stats.max_depth = max(self.stats.max_depth, depth)
        self.stats.nodes_explored += 1
        if self.stats.nodes_explored % 100 == 0:
            print(f"Nodes explored: {self.stats.nodes_explored} | Current Depth: {depth} | Remaining: {len(state.remaining_sessions)}", flush=True)
        if self.stats.nodes_explored > 2000:
            self.stats.stop()
            return False

        # 1. Base Case: timetable is complete
        if not state.remaining_sessions:
            self.stats.stop()
            return True

        # 2. Select the next session statically in order
        selection = self._select_next_session(state, context, rooms, labs)
        if not selection:
            self.stats.stop()
            return True

        session, candidates = selection

        # 3. Failure Handling: If no candidates exist, prune/backtrack immediately
        if not candidates:
            self.stats.failed_allocations += 1
            return False

        # Rank the candidates using the heuristics
        ranked_candidates = CandidateGenerator.rank_candidates(
            candidates, session, state.allocations, context
        )

        # 4. Search candidates recursively
        for candidate in ranked_candidates:
            # Save state snapshot
            snapshot = state.take_snapshot()
            
            # Place allocation
            success = Scheduler.allocate_session(session, [candidate], state)
            if not success:
                continue

            self.stats.successful_allocations += 1

            # 5. Forward Checking (Disabled for Python optimization)
            # if self._forward_checking(state, context, rooms, labs):
            if True:
                # Recurse
                if self.solve(state, context, rooms, labs, depth + 1):
                    return True

            # Rollback on path failure
            state.restore_snapshot(snapshot)
            self.stats.backtracks += 1

        return False
