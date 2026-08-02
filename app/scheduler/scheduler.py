"""Core Scheduler (Allocation Engine) placing candidates into the schedule state."""
from typing import List, Tuple
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState

class Scheduler:
    """Manages simple session placement on a SchedulingState using pre-calculated candidate lists."""

    @staticmethod
    def allocate_session(
        session: Session,
        candidates: List[Tuple[int, int, str]],
        state: SchedulingState
    ) -> bool:
        """
        Selects the best candidate (first in the list) and allocates it in the state.
        Returns True if successful, False if no candidate options are available.
        """
        if not candidates:
            return False

        # Choose the best ranked candidate (index 0)
        best_candidate = candidates[0]
        day, start_period, room = best_candidate

        # Allocate based on session properties
        if session.has_lab:
            state.allocate(session, day, start_period, lab_room_no=room)
        else:
            state.allocate(session, day, start_period, room_no=room)

        return True
