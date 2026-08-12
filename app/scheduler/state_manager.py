"""Timetable state manager tracking occupancies, workloads, and busy slot grids."""
from typing import Dict, List, Optional, Set, Tuple
from app.core.domain import Schedule
from app.scheduler.session import Session

class SchedulingState:
    """Manages transactional state changes in the active timetable schedule."""

    def __init__(
        self,
        remaining_sessions: Optional[List[Session]] = None,
        initial_allocations: Optional[List[Schedule]] = None,
        year: int = 2026,
        semester: int = 1
    ):
        # Academic year metadata — injected at construction, never hard-coded
        self.year: int = year
        self.semester: int = semester

        # Busy status sets for quick lookup
        self.faculty_busy: Set[Tuple[str, int, int]] = set()      # {(faculty_id, day_id, period_no)}
        self.room_busy: Set[Tuple[str, int, int]] = set()         # {(room_no, day_id, period_no)}
        self.lab_busy: Set[Tuple[str, int, int]] = set()          # {(lab_room_no, day_id, period_no)}
        self.section_busy: Set[Tuple[str, int, int]] = set()      # {(section_id, day_id, period_no)}

        # Workload and period counts
        self.faculty_daily_count: Dict[Tuple[str, int], int] = {}  # {(faculty_id, day_id): count}
        self.course_weekly_count: Dict[Tuple[str, str], int] = {}  # {(section_id, course_id): count}

        # Placed schedule list
        self.allocations: List[Schedule] = []
        
        # Remaining scheduling backlog
        self.remaining_sessions: List[Session] = remaining_sessions if remaining_sessions is not None else []

        if initial_allocations:
            for s in initial_allocations:
                self.allocations.append(s)
                self.faculty_busy.add((s.faculty_id, s.day_id, s.period_no))
                if s.room_no:
                    self.room_busy.add((s.room_no, s.day_id, s.period_no))
                if s.lab_room_no:
                    self.lab_busy.add((s.lab_room_no, s.day_id, s.period_no))
                self.section_busy.add((s.section_id, s.day_id, s.period_no))
                
                self.faculty_daily_count[(s.faculty_id, s.day_id)] = self.faculty_daily_count.get((s.faculty_id, s.day_id), 0) + 1
                self.course_weekly_count[(s.section_id, s.course_id)] = self.course_weekly_count.get((s.section_id, s.course_id), 0) + 1

    def allocate(
        self,
        session: Session,
        day_id: int,
        start_period: int,
        room_no: Optional[str] = None,
        lab_room_no: Optional[str] = None
    ) -> None:
        """
        Allocates a session to starting slot (day_id, start_period).
        Handles multi-period blocks (consecutives) automatically.
        """
        for offset in range(session.duration):
            period = start_period + offset
            
            # Create a Schedule allocation record
            alloc = Schedule(
                run_id=1,
                section_id=session.section_id,
                day_id=day_id,
                period_no=period,
                course_id=session.course_id,
                faculty_id=session.faculty_id,
                room_no=room_no,
                lab_room_no=lab_room_no,
                year=self.year,
                semester=self.semester
            )
            # Add to placed list
            self.allocations.append(alloc)
            
            # Add to busy status sets
            self.faculty_busy.add((session.faculty_id, day_id, period))
            if room_no:
                self.room_busy.add((room_no, day_id, period))
            if lab_room_no:
                self.lab_busy.add((lab_room_no, day_id, period))
            self.section_busy.add((session.section_id, day_id, period))
            
            # Update workloads
            fd_key = (session.faculty_id, day_id)
            self.faculty_daily_count[fd_key] = self.faculty_daily_count.get(fd_key, 0) + 1
            
            cw_key = (session.section_id, session.course_id)
            self.course_weekly_count[cw_key] = self.course_weekly_count.get(cw_key, 0) + 1

        # Remove from remaining sessions backlog
        if session in self.remaining_sessions:
            self.remaining_sessions.remove(session)

    def deallocate(self, session: Session) -> None:
        """
        Removes all allocations belonging to the session.
        Restores workloads and busy status maps.
        """
        # Find all allocation records matching this session
        matched = [
            s for s in self.allocations
            if s.section_id == session.section_id and s.course_id == session.course_id 
            and s.faculty_id == session.faculty_id
        ]
        
        # We need to filter exactly by the periods occupied. To be safe, we look at the session's duration.
        # But wait, during search, multiple allocations of the same course exist. We should only delete the ones
        # representing this specific session. Let's trace allocations by a unique identifier if possible.
        # Since Schedule doesn't have session_id, we can track them by looking at the period details or matching duration.
        # Let's filter allocations that match session's attributes and remove them.
        # Wait, if we backtrack, we deallocate the EXACT allocation we just placed!
        # So we can simply pop/remove the last `session.duration` allocations from the list if they match!
        # Yes! Backtracking is LIFO (last-in-first-out). So popping the last elements is perfectly correct!
        for _ in range(session.duration):
            if not self.allocations:
                break
            alloc = self.allocations.pop()
            
            # Remove from busy sets
            self.faculty_busy.discard((alloc.faculty_id, alloc.day_id, alloc.period_no))
            if alloc.room_no:
                self.room_busy.discard((alloc.room_no, alloc.day_id, alloc.period_no))
            if alloc.lab_room_no:
                self.lab_busy.discard((alloc.lab_room_no, alloc.day_id, alloc.period_no))
            self.section_busy.discard((alloc.section_id, alloc.day_id, alloc.period_no))
            
            # Decrement counts
            fd_key = (alloc.faculty_id, alloc.day_id)
            if fd_key in self.faculty_daily_count:
                self.faculty_daily_count[fd_key] -= 1
                if self.faculty_daily_count[fd_key] == 0:
                    del self.faculty_daily_count[fd_key]
                    
            cw_key = (alloc.section_id, alloc.course_id)
            if cw_key in self.course_weekly_count:
                self.course_weekly_count[cw_key] -= 1
                if self.course_weekly_count[cw_key] == 0:
                    del self.course_weekly_count[cw_key]

        # Add back to remaining list
        if session not in self.remaining_sessions:
            self.remaining_sessions.append(session)

    def take_snapshot(self) -> dict:
        """Captures a snapshot of the current state maps to allow rollback."""
        return {
            "faculty_busy": set(self.faculty_busy),
            "room_busy": set(self.room_busy),
            "lab_busy": set(self.lab_busy),
            "section_busy": set(self.section_busy),
            "faculty_daily_count": dict(self.faculty_daily_count),
            "course_weekly_count": dict(self.course_weekly_count),
            "allocations": list(self.allocations),
            "remaining_sessions": list(self.remaining_sessions)
        }

    def restore_snapshot(self, snapshot: dict) -> None:
        """Restores a previously captured snapshot of the state maps."""
        self.faculty_busy = set(snapshot["faculty_busy"])
        self.room_busy = set(snapshot["room_busy"])
        self.lab_busy = set(snapshot["lab_busy"])
        self.section_busy = set(snapshot["section_busy"])
        self.faculty_daily_count = dict(snapshot["faculty_daily_count"])
        self.course_weekly_count = dict(snapshot["course_weekly_count"])
        self.allocations = list(snapshot["allocations"])
        self.remaining_sessions = list(snapshot["remaining_sessions"])
