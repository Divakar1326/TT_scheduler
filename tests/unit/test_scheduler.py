"""Unit tests for the Scheduler and SchedulingState manager."""
import unittest
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.scheduler import Scheduler

class TestScheduler(unittest.TestCase):

    def setUp(self):
        # Setup test sessions
        self.session_theory = Session(
            session_id="CS101_S1_L1", course_id="CS101", section_id="S1",
            faculty_id="F01", type="THEORY", duration=1, has_lab=False
        )
        self.session_tutorial = Session(
            session_id="CS101_S1_T1", course_id="CS101", section_id="S1",
            faculty_id="F01", type="TUTORIAL", duration=1, has_lab=False
        )
        self.session_practical = Session(
            session_id="CS102_S1_P", course_id="CS102", section_id="S1",
            faculty_id="F02", type="PRACTICAL", duration=3, has_lab=True
        )

        self.state = SchedulingState(remaining_sessions=[
            self.session_theory, self.session_tutorial, self.session_practical
        ])

    def test_theory_allocation(self):
        candidates = [(1, 1, "R101")]
        # Allocate theory session
        success = Scheduler.allocate_session(self.session_theory, candidates, self.state)
        self.assertTrue(success)
        
        # Verify state occupancy lists
        self.assertIn(("F01", 1, 1), self.state.faculty_busy)
        self.assertIn(("R101", 1, 1), self.state.room_busy)
        self.assertIn(("S1", 1, 1), self.state.section_busy)
        
        # Verify workload counters
        self.assertEqual(self.state.faculty_daily_count[("F01", 1)], 1)
        self.assertEqual(self.state.course_weekly_count[("S1", "CS101")], 1)
        
        # Verify allocations lists
        self.assertEqual(len(self.state.allocations), 1)
        alloc = self.state.allocations[0]
        self.assertEqual(alloc.course_id, "CS101")
        self.assertEqual(alloc.room_no, "R101")
        self.assertIsNone(alloc.lab_room_no)
        
        # Remaining backlog update check
        self.assertNotIn(self.session_theory, self.state.remaining_sessions)

    def test_practical_allocation_consecutive(self):
        candidates = [(1, 2, "L201")]  # Day 1 starting Period 2, lab L201
        
        success = Scheduler.allocate_session(self.session_practical, candidates, self.state)
        self.assertTrue(success)
        
        # Duration is 3, so periods 2, 3, and 4 should be busy
        for period in (2, 3, 4):
            self.assertIn(("F02", 1, period), self.state.faculty_busy)
            self.assertIn(("L201", 1, period), self.state.lab_busy)
            self.assertIn(("S1", 1, period), self.state.section_busy)
            
        # Faculty daily workload should be 3
        self.assertEqual(self.state.faculty_daily_count[("F02", 1)], 3)
        self.assertEqual(self.state.course_weekly_count[("S1", "CS102")], 3)

        # 3 allocations should exist
        self.assertEqual(len(self.state.allocations), 3)

    def test_deallocation_rollback(self):
        # 1. Allocate theory session
        candidates = [(1, 1, "R101")]
        Scheduler.allocate_session(self.session_theory, candidates, self.state)
        
        # 2. Deallocate
        self.state.deallocate(self.session_theory)
        
        # Occupancies and counters must be completely restored
        self.assertNotIn(("F01", 1, 1), self.state.faculty_busy)
        self.assertNotIn(("R101", 1, 1), self.state.room_busy)
        self.assertNotIn(("S1", 1, 1), self.state.section_busy)
        self.assertEqual(len(self.state.allocations), 0)
        self.assertNotIn(("F01", 1), self.state.faculty_daily_count)
        self.assertNotIn(("S1", "CS101"), self.state.course_weekly_count)
        self.assertIn(self.session_theory, self.state.remaining_sessions)

    def test_deallocate_practical_consecutive_rollback(self):
        candidates = [(1, 2, "L201")]
        Scheduler.allocate_session(self.session_practical, candidates, self.state)
        self.assertEqual(len(self.state.allocations), 3)
        
        # Rollback
        self.state.deallocate(self.session_practical)
        
        # Occupancy must be clean
        for period in (2, 3, 4):
            self.assertNotIn(("F02", 1, period), self.state.faculty_busy)
            self.assertNotIn(("L201", 1, period), self.state.lab_busy)
        self.assertEqual(len(self.state.allocations), 0)

    def test_allocation_failure_on_empty_candidates(self):
        success = Scheduler.allocate_session(self.session_theory, [], self.state)
        self.assertFalse(success)
        self.assertEqual(len(self.state.allocations), 0)


if __name__ == "__main__":
    unittest.main()
