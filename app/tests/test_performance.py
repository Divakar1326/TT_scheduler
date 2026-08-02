"""Performance and stress testing for Timetable generation and validators."""
import time
import unittest
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.backtracking import BacktrackingSolver
from app.constraints.validator import ValidationContext

class TestSchedulerPerformance(unittest.TestCase):

    def test_backtracking_search_performance(self):
        # Build a stress-test scenario with 4 sections, 8 courses, 30 sessions to allocate
        sessions = []
        for sec in ["S1", "S2", "S3", "S4"]:
            for course_idx in range(1, 6):
                # Theory sessions
                sessions.append(
                    Session(
                        session_id=f"C{course_idx}_{sec}_L",
                        course_id=f"CS{course_idx}",
                        section_id=sec,
                        faculty_id=f"F{course_idx}",
                        type="THEORY",
                        duration=1,
                        has_lab=False
                    )
                )
                
        # Setup context
        from app.models.domain import Course
        course_dict = {}
        for idx in range(1, 6):
            course_dict[f"CS{idx}"] = Course(
                course_id=f"CS{idx}",
                course_name=f"Course {idx}",
                l=3, t=0, p=0, c=3, difficulty=1, semester=1, has_lab=False, weekly_hours=3
            )

        context = ValidationContext(
            course_dict=course_dict,
            faculty_unavailables=set(),
            room_sections={},
            class_teachers={},
            working_days={1, 2, 3, 4, 5},
            template_slots={(d, p) for d in range(1, 6) for p in range(1, 8)},
            section_depts={sec: "CS" for sec in ["S1", "S2", "S3", "S4"]},
            course_depts={f"CS{idx}": ["CS"] for idx in range(1, 6)},
            ai_rules=[]
        )
        
        rooms = ["R101", "R102", "R103", "R104"]
        labs = ["LAB101"]
        
        state = SchedulingState(remaining_sessions=sessions)
        solver = BacktrackingSolver()
        
        start_time = time.time()
        success = solver.solve(state, context, rooms, labs)
        elapsed = time.time() - start_time
        
        print(f"\nStress Test solver elapsed: {elapsed:.3f}s, steps: {solver.stats.nodes_explored}")
        
        # Verify that solver finishes efficiently (e.g. under 5 seconds)
        self.assertTrue(success)
        self.assertTrue(elapsed < 5.0)


if __name__ == "__main__":
    unittest.main()
