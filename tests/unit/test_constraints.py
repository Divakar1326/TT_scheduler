"""Unit tests for hard constraints, soft constraints, and MasterValidator."""
import unittest
from app.core.domain import Schedule, Course
from app.validators.validator import MasterValidator, ValidationContext
from app.validators.hard_constraints import check_faculty_clash, check_room_clash
from app.validators.soft_constraints import score_morning_lab_preference, score_compact_timetable

class TestConstraintEngine(unittest.TestCase):

    def setUp(self):
        # Sample metadata
        self.course_theory = Course(
            course_id="CS101", course_name="Introduction to CS",
            l=3, t=0, p=0, c=3, difficulty=2, semester=1,
            has_lab=False, weekly_hours=3
        )
        self.course_lab = Course(
            course_id="CS102", course_name="CS Lab",
            l=0, t=0, p=3, c=2, difficulty=1, semester=1,
            has_lab=True, weekly_hours=3
        )
        self.course_mentor = Course(
            course_id="MENTOR1", course_name="Mentor Hour",
            l=1, t=0, p=0, c=1, difficulty=1, semester=1,
            has_lab=False, weekly_hours=1
        )
        
        self.context = ValidationContext(
            course_dict={
                "CS101": self.course_theory,
                "CS102": self.course_lab,
                "MENTOR1": self.course_mentor
            },
            faculty_unavailables={("F01", 1, 5)},  # Faculty F01 unavailable Mon Period 5
            room_sections={"S1": "R101"},         # Section S1 permanent room is R101
            class_teachers={"S1": "F01"},         # Section S1 class teacher is F01
            working_days={1, 2, 3, 4, 5},
            template_slots={(d, p) for d in range(1, 6) for p in range(1, 8) if p != 5}, # Mon-Fri, period 5 lunch
            section_depts={"S1": "CS"},
            course_depts={
                "CS101": ["CS"],
                "CS102": ["CS"],
                "MENTOR1": ["CS"]
            },
            ai_rules=[
                {"faculty_id": "F02", "avoid_periods": [6, 7]}  # F02 should not teach periods 6, 7
            ]
        )

    def test_faculty_clash(self):
        current = [
            Schedule(run_id=1, section_id="S2", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R102", year=2026, semester=1)
        ]
        # Attempt to allocate F01 to S1 at same slot
        alloc = Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        self.assertFalse(check_faculty_clash(alloc, current))
        
        # Allocate at different slot - valid
        alloc_ok = Schedule(run_id=1, section_id="S1", day_id=1, period_no=2, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        self.assertTrue(check_faculty_clash(alloc_ok, current))

    def test_room_clash(self):
        current = [
            Schedule(run_id=1, section_id="S2", day_id=1, period_no=1, course_id="CS101", faculty_id="F02", room_no="R101", year=2026, semester=1)
        ]
        # Attempt to occupy room R101 at same slot
        alloc = Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        self.assertFalse(check_room_clash(alloc, current))

    def test_master_validator_success(self):
        current = []
        alloc = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=1,
            course_id="CS101", faculty_id="F01", room_no="R101",
            year=2026, semester=1
        )
        is_valid, violations = MasterValidator.validate_allocation(alloc, current, self.context)
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)

    def test_master_validator_failures(self):
        # 1. Test classroom rule failure
        alloc_bad_room = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=1,
            course_id="CS101", faculty_id="F01", room_no="R102",  # R102 is not permanent classroom R101
            year=2026, semester=1
        )
        is_valid, violations = MasterValidator.validate_allocation(alloc_bad_room, [], self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Permanent Classroom" in v for v in violations))

        # 2. Test template boundary failure (Lunch period 5)
        alloc_lunch = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=5,
            course_id="CS101", faculty_id="F01", room_no="R101",
            year=2026, semester=1
        )
        is_valid, violations = MasterValidator.validate_allocation(alloc_lunch, [], self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Fixed Template" in v for v in violations))

        # 3. Test has_lab validation failure (theory course allocated to lab, or lab course to classroom)
        alloc_lab_mismatch = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=1,
            course_id="CS102", faculty_id="F01", room_no="R101",  # CS102 is lab but room_no is theory room
            year=2026, semester=1
        )
        is_valid, violations = MasterValidator.validate_allocation(alloc_lab_mismatch, [], self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Lab Allocation Mismatch" in v for v in violations))

        # 4. Test Class Teacher rule (MENTOR1 course must be taught by class teacher F01)
        alloc_mentor_bad_teacher = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=1,
            course_id="MENTOR1", faculty_id="F02", room_no="R101",  # F02 is not class teacher F01
            year=2026, semester=1
        )
        is_valid, violations = MasterValidator.validate_allocation(alloc_mentor_bad_teacher, [], self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Permanent Class Teacher" in v for v in violations))

    def test_soft_constraint_morning_lab(self):
        # Lab scheduled in period 2 (morning) - no penalty
        alloc_morning = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=2,
            course_id="CS102", faculty_id="F01", lab_room_no="L201",
            year=2026, semester=1
        )
        self.assertEqual(score_morning_lab_preference(alloc_morning), 0)

        # Lab scheduled in period 6 (afternoon) - penalty
        alloc_afternoon = Schedule(
            run_id=1, section_id="S1", day_id=1, period_no=6,
            course_id="CS102", faculty_id="F01", lab_room_no="L201",
            year=2026, semester=1
        )
        self.assertEqual(score_morning_lab_preference(alloc_afternoon), 5)

    def test_soft_constraint_compact_timetable(self):
        # Section with classes in Period 1 and Period 3 has a gap in Period 2
        schedule = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=3, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        ]
        self.assertEqual(score_compact_timetable("S1", schedule), 2)  # 1 gap * 2 points = 2

        # No gaps
        schedule_ok = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=2, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        ]
        self.assertEqual(score_compact_timetable("S1", schedule_ok), 0)


if __name__ == "__main__":
    unittest.main()
