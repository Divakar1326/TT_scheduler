"""Unit tests for domain models and mapping utilities."""
import unittest
from app.models.domain import Faculty, Room, Course, Rule, Section
from app.models.mapping import ModelMapper

class TestDomainModels(unittest.TestCase):
    
    def test_faculty_validation(self):
        # 1. Valid faculty
        fac = Faculty(faculty_id="F01", faculty_name="Dr. Smith", max_hours_week=12, email="smith@univ.edu")
        self.assertEqual(fac.faculty_id, "F01")
        self.assertEqual(fac.max_hours_week, 12)
        
        # 2. Invalid email raises ValueError
        with self.assertRaises(ValueError):
            Faculty(faculty_id="F02", faculty_name="Dr. Jones", max_hours_week=10, email="invalid-email")
            
        # 3. Negative workload hours raises ValueError
        with self.assertRaises(ValueError):
            Faculty(faculty_id="F03", faculty_name="Dr. Taylor", max_hours_week=-5)

        # 4. Invalid status status raises ValueError
        with self.assertRaises(ValueError):
            Faculty(faculty_id="F04", faculty_name="Dr. Lee", max_hours_week=15, status="SUSPENDED")

    def test_room_validation(self):
        # Valid room
        r = Room(room_no="JB401", department_id="CS", capacity=50)
        self.assertEqual(r.capacity, 50)
        
        # Zero or negative capacity raises ValueError
        with self.assertRaises(ValueError):
            Room(room_no="JB402", department_id="CS", capacity=0)
        with self.assertRaises(ValueError):
            Room(room_no="JB403", department_id="CS", capacity=-10)

    def test_model_serialization_and_deserialization(self):
        # 1. Dataclass to database dict conversion (serialization)
        course = Course(
            course_id="CS101",
            course_name="Intro to CS",
            l=3, t=0, p=2, c=4,
            difficulty=2,
            semester=1,
            has_lab=True,
            weekly_hours=5
        )
        data_dict = ModelMapper.to_dict(course)
        
        self.assertEqual(data_dict["course_id"], "CS101")
        self.assertEqual(data_dict["has_lab"], 1)  # Boolean converted to 1

        # 2. Database dict to Dataclass conversion (deserialization)
        reconstructed_course = ModelMapper.to_course(data_dict)
        self.assertEqual(reconstructed_course.course_id, "CS101")
        self.assertTrue(reconstructed_course.has_lab)
        
    def test_rule_serialization_deserialization(self):
        rule = Rule(
            rule_id="R01",
            rule_name="Max sessions",
            description="At most 2 sessions of a class per day",
            priority=1,
            type="HARD",
            parameter="max_sessions=2",
            enabled=False,
            cost=10
        )
        
        data_dict = ModelMapper.to_dict(rule)
        self.assertEqual(data_dict["enabled"], 0)
        self.assertEqual(data_dict["cost"], 10)
        
        reconstructed_rule = ModelMapper.to_rule(data_dict)
        self.assertEqual(reconstructed_rule.rule_id, "R01")
        self.assertFalse(reconstructed_rule.enabled)
        
    def test_section_validation(self):
        # Valid section
        s = Section(section_id="S01", section_name="CS A", semester=1, department_id="CS", capacity=60)
        self.assertEqual(s.section_name, "CS A")
        
        # Zero or negative capacity raises ValueError
        with self.assertRaises(ValueError):
            Section(section_id="S02", section_name="CS B", semester=1, department_id="CS", capacity=0)
            
        # Empty string ID raises ValueError
        with self.assertRaises(ValueError):
            Section(section_id=" ", section_name="CS B", semester=1, department_id="CS", capacity=40)


if __name__ == "__main__":
    unittest.main()
