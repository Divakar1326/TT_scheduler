"""Unit tests for the Timetable Repair Engine."""
import unittest
from app.core.domain import Course, Schedule
from app.services.repair_engine import RepairEngine
from app.validators.validator import ValidationContext

class TestRepairEngine(unittest.TestCase):

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
            room_sections={"S1": "R101", "S2": "R102"},
            class_teachers={"S1": "F01", "S2": "F03"},
            working_days={1, 2},
            template_slots={(d, p) for d in (1, 2) for p in (1, 2)},  # 2 periods/day
            section_depts={"S1": "CS", "S2": "CS"},
            course_depts={
                "CS101": ["CS"],
                "CS102": ["CS"]
            },
            ai_rules=[]
        )
        self.rooms = ["R101", "R102"]
        self.labs = ["L201"]

    def test_faculty_conflict_repair_by_moving(self):
        # Initial schedule has a faculty clash: F01 is scheduled in both S1 and S2 at Day 1 Period 1.
        # Section S1 is missing 1 theory class (CS101 has only 1 slot instead of 2).
        # We attempt to resolve by moving the clash to Day 1 Period 2 (which is empty).
        schedule = [
            # Clash slot
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S2", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R102", year=2026, semester=1),
            
            # Rest of the required slots to meet weekly hours limit of 2
            Schedule(run_id=1, section_id="S2", day_id=2, period_no=1, course_id="CS101", faculty_id="F01", room_no="R102", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=2, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        ]
        
        local_context = ValidationContext(
            course_dict={"CS101": self.course_theory},
            faculty_unavailables=set(),
            room_sections={"S1": "R101", "S2": "R102"},
            class_teachers={"S1": "F01", "S2": "F03"},
            working_days={1, 2},
            template_slots={(d, p) for d in (1, 2) for p in (1, 2)},
            section_depts={"S1": "CS", "S2": "CS"},
            course_depts={"CS101": ["CS"]},
            ai_rules=[]
        )
        
        repaired, stats, remaining_errors = RepairEngine.repair_timetable(schedule, local_context, self.rooms, self.labs)
        
        # Verify that all clashes are resolved and no errors remain
        self.assertEqual(len(remaining_errors), 0)
        self.assertGreater(stats["repaired_count"], 0)
        
        # Verify that the two F01 slots for S1/S2 no longer overlap at the same slot
        s1_slots = [(s.day_id, s.period_no) for s in repaired if s.section_id == "S1"]
        s2_slots = [(s.day_id, s.period_no) for s in repaired if s.section_id == "S2"]
        overlap = set(s1_slots).intersection(set(s2_slots))
        self.assertEqual(len(overlap), 0)

    def test_consecutive_lab_repair(self):
        # Lab CS102 (duration 2) has a split: Day 1 Period 1 and Day 2 Period 1.
        # This violates the consecutive practical rule.
        # The repair engine should shift them to consecutive periods on the same day.
        schedule = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=2, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            # Split lab
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS102", faculty_id="F02", lab_room_no="L201", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=2, period_no=1, course_id="CS102", faculty_id="F02", lab_room_no="L201", year=2026, semester=1)
        ]
        
        local_context = ValidationContext(
            course_dict={"CS101": self.course_theory, "CS102": self.course_lab},
            faculty_unavailables=set(),
            room_sections={"S1": "R101"},
            class_teachers={"S1": "F01"},
            working_days={1, 2},
            template_slots={(d, p) for d in (1, 2) for p in (1, 2)},
            section_depts={"S1": "CS"},
            course_depts={"CS101": ["CS"], "CS102": ["CS"]},
            ai_rules=[]
        )
        
        repaired, stats, remaining_errors = RepairEngine.repair_timetable(schedule, local_context, self.rooms, self.labs)
        self.assertEqual(len(remaining_errors), 0)
        
        # Verify that CS102 allocations are now on the same day and consecutive (e.g. Day 2 Period 1 & Period 2)
        lab_allocs = [s for s in repaired if s.course_id == "CS102"]
        self.assertEqual(lab_allocs[0].day_id, lab_allocs[1].day_id)
        self.assertEqual(abs(lab_allocs[0].period_no - lab_allocs[1].period_no), 1)


if __name__ == "__main__":
    unittest.main()
