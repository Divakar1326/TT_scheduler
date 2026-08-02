"""Unit tests for the Backtracking solver and CSP search pruning."""
import unittest
from app.models.domain import Course, Schedule
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.backtracking import BacktrackingSolver
from app.constraints.validator import ValidationContext

class TestBacktracking(unittest.TestCase):

    def setUp(self):
        # Setup course definitions
        self.course_theory = Course(
            course_id="CS101", course_name="Intro to CS",
            l=2, t=0, p=0, c=2, difficulty=2, semester=1,
            has_lab=False, weekly_hours=2
        )
        self.course_lab = Course(
            course_id="CS102", course_name="CS Lab",
            l=0, t=0, p=2, c=1, difficulty=1, semester=1,
            has_lab=True, weekly_hours=2
        )
        self.context = ValidationContext(
            course_dict={
                "CS101": self.course_theory,
                "CS102": self.course_lab
            },
            faculty_unavailables=set(),
            room_sections={"S1": "R101"},
            class_teachers={"S1": "F01"},
            working_days={1, 2},
            template_slots={(d, p) for d in (1, 2) for p in (1, 2)},  # 2 periods/day
            section_depts={"S1": "CS"},
            course_depts={
                "CS101": ["CS"],
                "CS102": ["CS"]
            },
            ai_rules=[]
        )
        self.rooms = ["R101"]
        self.labs = ["L201"]

    def test_state_snapshot_restore(self):
        state = SchedulingState()
        session = Session("CS101_S1_L1", "CS101", "S1", "F01", "THEORY", 1, False)
        
        # Take snapshot of empty state
        snapshot = state.take_snapshot()
        
        # Perform allocation
        state.allocate(session, 1, 1, room_no="R101")
        self.assertEqual(len(state.allocations), 1)
        
        # Restore snapshot
        state.restore_snapshot(snapshot)
        self.assertEqual(len(state.allocations), 0)
        self.assertNotIn(("F01", 1, 1), state.faculty_busy)

    def test_successful_solving(self):
        # S1 has: 2 theory sessions (CS101) + 1 lab block of duration 2 (CS102)
        # S1 permanent room is R101. Lab room is L201.
        # Template slots: Mon Period 1, Mon Period 2, Tue Period 1, Tue Period 2.
        # Total periods needed = 2 theory + 2 lab = 4 periods.
        # Total slots in template = 4. There is exactly one solution.
        session_theory1 = Session("CS101_S1_L1", "CS101", "S1", "F01", "THEORY", 1, False)
        session_theory2 = Session("CS101_S1_L2", "CS101", "S1", "F01", "THEORY", 1, False)
        session_lab = Session("CS102_S1_P", "CS102", "S1", "F02", "PRACTICAL", 2, True)

        state = SchedulingState(remaining_sessions=[session_theory1, session_theory2, session_lab])
        solver = BacktrackingSolver()
        
        success = solver.solve(state, self.context, self.rooms, self.labs)
        
        self.assertTrue(success)
        self.assertEqual(len(state.allocations), 4)
        
        # Verify stats collection
        stats = solver.stats.to_dict()
        self.assertGreater(stats["nodes_explored"], 0)
        self.assertGreaterEqual(stats["execution_time_seconds"], 0.0)

    def test_impossible_timetable(self):
        # Attempt to allocate 5 periods when only 4 slots are active in the template
        session_theory1 = Session("CS101_S1_L1", "CS101", "S1", "F01", "THEORY", 1, False)
        session_theory2 = Session("CS101_S1_L2", "CS101", "S1", "F01", "THEORY", 1, False)
        session_theory3 = Session("CS101_S1_L3", "CS101", "S1", "F01", "THEORY", 1, False)
        session_lab = Session("CS102_S1_P", "CS102", "S1", "F02", "PRACTICAL", 2, True)

        state = SchedulingState(remaining_sessions=[
            session_theory1, session_theory2, session_theory3, session_lab
        ])
        solver = BacktrackingSolver()
        
        success = solver.solve(state, self.context, self.rooms, self.labs)
        
        # Should fail as there are not enough slots
        self.assertFalse(success)

    def test_backtracking_recovery(self):
        # Create a conflict setup where F01 is busy on Day 1 Period 1 in another section
        # forcing solver to backtrack and find alternative positions.
        session_theory1 = Session("CS101_S1_L1", "CS101", "S1", "F01", "THEORY", 1, False)
        state = SchedulingState(remaining_sessions=[session_theory1])
        
        # Pre-occupy Day 1 Period 1 for Faculty F01 by adding a Schedule allocation
        state.allocate(
            Session("CS101_S2_L1", "CS101", "S2", "F01", "THEORY", 1, False),
            1, 1, room_no="R101"
        )
        
        solver = BacktrackingSolver()
        success = solver.solve(state, self.context, self.rooms, self.labs)
        
        self.assertTrue(success)
        # Allocation should be scheduled on Day 2 Period 1 (due to workload balancing: Day 2 has 0 load, Day 1 has 1 load)
        self.assertEqual(state.allocations[1].day_id, 2)
        self.assertEqual(state.allocations[1].period_no, 1)


if __name__ == "__main__":
    unittest.main()
