"""Unit tests for the Final Timetable Validator and reporting."""
import unittest
from app.core.domain import Course, Schedule
from app.validators.timetable_validator import TimetableValidator
from app.validators.validator import ValidationContext

class TestTimetableValidator(unittest.TestCase):

    def setUp(self):
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

    def test_valid_timetable_report(self):
        # A valid complete schedule satisfying all 4 required hours (2 CS101, 2 CS102)
        schedule = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=2, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=2, period_no=1, course_id="CS102", faculty_id="F02", lab_room_no="L201", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=2, period_no=2, course_id="CS102", faculty_id="F02", lab_room_no="L201", year=2026, semester=1)
        ]
        
        report = TimetableValidator.validate_timetable(schedule, self.context, self.rooms, self.labs)
        self.assertTrue(report.is_valid())
        self.assertEqual(len(report.errors), 0)
        self.assertEqual(report.stats["total_allocations"], 4)

    def test_validator_detects_clashes(self):
        # 1. Faculty clash on Day 1 Period 1
        schedule_clash = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S2", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R102", year=2026, semester=1)
        ]
        report = TimetableValidator.validate_timetable(schedule_clash, self.context, self.rooms, self.labs)
        self.assertFalse(report.is_valid())
        self.assertTrue(any("Faculty Clash" in err for err in report.errors))

    def test_validator_detects_missing_allocations(self):
        # Section S1 is missing its required lab hours (CS102)
        schedule_missing = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=2, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1)
        ]
        report = TimetableValidator.validate_timetable(schedule_missing, self.context, self.rooms, self.labs)
        self.assertFalse(report.is_valid())
        self.assertTrue(any("Missing Allocations" in err for err in report.errors))

    def test_validator_consecutive_practical_failure(self):
        # CS102 requires a consecutive lab block of length 2. Here we split it across days.
        schedule_split = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=2, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            # CS102 split: Day 1 Period 3 (wait, Day 1 has only 2 slots, let's place on Day 1 Period 2 and Day 2 Period 1)
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS102", faculty_id="F02", lab_room_no="L201", year=2026, semester=1),
            Schedule(run_id=1, section_id="S1", day_id=2, period_no=1, course_id="CS102", faculty_id="F02", lab_room_no="L201", year=2026, semester=1)
        ]
        report = TimetableValidator.validate_timetable(schedule_split, self.context, self.rooms, self.labs)
        self.assertFalse(report.is_valid())
        self.assertTrue(any("Consecutive Practical Rule Violated" in err for err in report.errors))

    def test_suggested_repairs_triggered_on_error(self):
        schedule_clash = [
            Schedule(run_id=1, section_id="S1", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R101", year=2026, semester=1),
            Schedule(run_id=1, section_id="S2", day_id=1, period_no=1, course_id="CS101", faculty_id="F01", room_no="R102", year=2026, semester=1)
        ]
        report = TimetableValidator.validate_timetable(schedule_clash, self.context, self.rooms, self.labs)
        self.assertFalse(report.is_valid())
        # Conflicted schedule has empty slots on Day 2, so validator should suggest a repair placement
        self.assertGreater(len(report.suggested_repairs), 0)
        self.assertTrue(any("Move conflicting session" in rep for rep in report.suggested_repairs))


if __name__ == "__main__":
    unittest.main()
