"""Unit tests for Candidate Generator and Session creation."""
import unittest
from app.models.domain import Course, Schedule
from app.scheduler.session import Session
from app.scheduler.candidate_generator import CandidateGenerator
from app.constraints.validator import ValidationContext

class TestCandidateGenerator(unittest.TestCase):

    def setUp(self):
        self.course_theory_lab = Course(
            course_id="CS101", course_name="Intro to CS",
            l=2, t=1, p=2, c=4, difficulty=2, semester=1,
            has_lab=True, weekly_hours=5
        )
        self.context = ValidationContext(
            course_dict={"CS101": self.course_theory_lab},
            faculty_unavailables=set(),
            room_sections={"S1": "R101"},
            class_teachers={"S1": "F01"},
            working_days={1, 2},  # Only Mon & Tue to limit search space
            template_slots={(d, p) for d in (1, 2) for p in (1, 2, 3)},  # 3 periods per day
            section_depts={"S1": "CS"},
            course_depts={"CS101": ["CS"]},
            ai_rules=[]
        )
        self.rooms = ["R101", "R102"]
        self.labs = ["L201"]

    def test_session_generation(self):
        sessions = CandidateGenerator.generate_sessions(self.course_theory_lab, "S1", "F01")
        # Should generate: 2 Theory sessions, 1 Tutorial session, and 1 Practical session of duration 2
        self.assertEqual(len(sessions), 4)
        
        types = [s.type for s in sessions]
        self.assertEqual(types.count("THEORY"), 2)
        self.assertEqual(types.count("TUTORIAL"), 1)
        self.assertEqual(types.count("PRACTICAL"), 1)

        practical_session = next(s for s in sessions if s.type == "PRACTICAL")
        self.assertEqual(practical_session.duration, 2)
        self.assertTrue(practical_session.has_lab)

    def test_theory_candidates_constrained_to_permanent_classroom(self):
        sessions = CandidateGenerator.generate_sessions(self.course_theory_lab, "S1", "F01")
        theory_session = next(s for s in sessions if s.type == "THEORY")
        
        candidates = CandidateGenerator.get_valid_candidates(
            theory_session, [], self.context, self.rooms, self.labs
        )
        
        # Valid slots should only be in permanent classroom R101 (2 working days * 3 periods = 6 slots)
        self.assertEqual(len(candidates), 6)
        for c in candidates:
            self.assertEqual(c[2], "R101")  # Room must be R101

    def test_practical_lab_candidates_consecutive(self):
        sessions = CandidateGenerator.generate_sessions(self.course_theory_lab, "S1", "F01")
        practical_session = next(s for s in sessions if s.type == "PRACTICAL")
        
        candidates = CandidateGenerator.get_valid_candidates(
            practical_session, [], self.context, self.rooms, self.labs
        )
        
        # 3 periods/day. Consecutive block of duration 2 can start at period 1 (1,2) or period 2 (2,3)
        # 2 working days * 2 start slots = 4 candidate placements.
        # Room must be lab room L201.
        self.assertEqual(len(candidates), 4)
        for c in candidates:
            self.assertEqual(c[2], "L201")
            self.assertIn(c[1], (1, 2))  # Starting periods must be 1 or 2

    def test_candidate_filtering_on_clash(self):
        sessions = CandidateGenerator.generate_sessions(self.course_theory_lab, "S1", "F01")
        theory_session = next(s for s in sessions if s.type == "THEORY")
        
        # Scenario: Faculty F01 is busy on Day 1 Period 1 in another section
        current_schedule = [
            Schedule(
                run_id=1, section_id="S2", day_id=1, period_no=1,
                course_id="CS101", faculty_id="F01", room_no="R102",
                year=2026, semester=1
            )
        ]
        
        candidates = CandidateGenerator.get_valid_candidates(
            theory_session, current_schedule, self.context, self.rooms, self.labs
        )
        
        # Out of the 6 total slots, Day 1 Period 1 should be excluded.
        self.assertEqual(len(candidates), 5)
        self.assertNotIn((1, 1, "R101"), candidates)

    def test_candidate_ranking(self):
        session = Session(
            session_id="CS101_S1_P", course_id="CS101", section_id="S1",
            faculty_id="F01", type="PRACTICAL", duration=2, has_lab=True
        )
        # Candidate slots: Day 1 Period 1, Day 1 Period 5 (afternoon), Day 2 Period 1
        candidates = [
            (1, 5, "L201"),
            (2, 1, "L201"),
            (1, 1, "L201")
        ]
        # Current schedule shows faculty teaches 1 course on Day 2, and 0 courses on Day 1
        current_schedule = [
            Schedule(
                run_id=1, section_id="S2", day_id=2, period_no=3,
                course_id="CS101", faculty_id="F01", room_no="R101",
                year=2026, semester=1
            )
        ]
        
        ranked = CandidateGenerator.rank_candidates(candidates, session, current_schedule, self.context)
        
        # Afternoon lab period (1, 5) should be ranked last due to afternoon lab penalty (lab_penalty = 1).
        # Day 2 has faculty load of 1, Day 1 has faculty load of 0. So Day 1 (1, 1) should be first (fac_load = 0).
        # Expected order: (1, 1, "L201") -> (2, 1, "L201") -> (1, 5, "L201")
        self.assertEqual(ranked[0], (1, 1, "L201"))
        self.assertEqual(ranked[1], (2, 1, "L201"))
        self.assertEqual(ranked[2], (1, 5, "L201"))


if __name__ == "__main__":
    unittest.main()
