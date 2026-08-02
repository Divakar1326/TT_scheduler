"""Validator for dynamic scheduling rules, checking entity existence, duplication, and logical contradictions."""
from typing import Dict, Any, List, Tuple
from app.repository.entity_repositories import (
    FacultyRepository, CourseRepository, SectionRepository, RoomRepository, LabRepository, DepartmentRepository
)

class RuleValidator:
    """Performs validation of generated JSON rules."""

    def __init__(self):
        self.fac_repo = FacultyRepository()
        self.course_repo = CourseRepository()
        self.sec_repo = SectionRepository()
        self.room_repo = RoomRepository()
        self.lab_repo = LabRepository()
        self.dept_repo = DepartmentRepository()

    def validate_entities(self, parameter: Dict[str, Any]) -> List[str]:
        """Validates that all entity references inside the rule parameter exist in the database."""
        errors = []
        
        fac_id = parameter.get("faculty_id")
        if fac_id and not self.fac_repo.find_by_id(fac_id):
            errors.append(f"Faculty {fac_id} does not exist.")
            
        course_id = parameter.get("course_id")
        if course_id and not self.course_repo.find_by_id(course_id):
            errors.append(f"Course {course_id} does not exist.")
            
        sec_id = parameter.get("section_id")
        if sec_id and not self.sec_repo.find_by_id(sec_id):
            errors.append(f"Section {sec_id} does not exist.")
            
        room_no = parameter.get("room_no")
        if room_no and not self.room_repo.find_by_no(room_no):
            errors.append(f"Room {room_no} does not exist.")
            
        lab_room_no = parameter.get("lab_room_no")
        if lab_room_no and not self.lab_repo.find_by_no(lab_room_no):
            errors.append(f"Lab Room {lab_room_no} does not exist.")
            
        dept_id = parameter.get("department_id")
        if dept_id and not self.dept_repo.find_by_id(dept_id):
            errors.append(f"Department {dept_id} does not exist.")

        # Validate avoid_days range (1 to 5)
        avoid_days = parameter.get("avoid_days", [])
        for d in avoid_days:
            if not (1 <= d <= 5):
                errors.append(f"Invalid day: {d} (must be 1-5).")

        # Validate avoid_periods range (1 to 7)
        avoid_periods = parameter.get("avoid_periods", [])
        for p in avoid_periods:
            if not (1 <= p <= 7):
                errors.append(f"Invalid period: {p} (must be 1-7).")

        return errors

    def check_duplication(self, new_parameter: Dict[str, Any], existing_rules: List[Dict[str, Any]]) -> bool:
        """Returns True if a rule with matching parameters already exists."""
        # Simple parameter comparison
        for r in existing_rules:
            if r.get("is_deleted") or not r.get("enabled", 1):
                continue
            import json
            existing_param = r.get("parameter")
            if isinstance(existing_param, str):
                try:
                    existing_param = json.loads(existing_param)
                except Exception:
                    existing_param = {}
            if existing_param == new_parameter:
                return True
        return False

    def check_contradictions(self, new_parameter: Dict[str, Any], existing_rules: List[Dict[str, Any]]) -> List[str]:
        """Detects contradictions between a new rule and existing active rules.
        Example contradiction: Rule 1 avoids day 5 for F01, Rule 2 prefers day 5 for F01,
        or Rule 1 avoids F01 period 1 and Rule 2 requires F01 period 1.
        """
        contradictions = []
        
        new_fac = new_parameter.get("faculty_id")
        new_course = new_parameter.get("course_id")
        new_sec = new_parameter.get("section_id")
        
        new_avoid_days = set(new_parameter.get("avoid_days", []))
        new_pref_days = set(new_parameter.get("preferred_days", []))
        new_avoid_periods = set(new_parameter.get("avoid_periods", []))
        new_pref_periods = set(new_parameter.get("preferred_periods", []))

        # Check self-contradictions (inside the same rule)
        day_overlap = new_avoid_days.intersection(new_pref_days)
        if day_overlap:
            contradictions.append(f"Self contradiction: Days {list(day_overlap)} are listed as both preferred and avoided.")

        period_overlap = new_avoid_periods.intersection(new_pref_periods)
        if period_overlap:
            contradictions.append(f"Self contradiction: Periods {list(period_overlap)} are listed as both preferred and avoided.")

        # Check contradictions with other active rules
        for r in existing_rules:
            if r.get("is_deleted") or not r.get("enabled", 1):
                continue
                
            import json
            existing_param = r.get("parameter")
            if isinstance(existing_param, str):
                try:
                    existing_param = json.loads(existing_param)
                except Exception:
                    continue
                    
            ext_fac = existing_param.get("faculty_id")
            ext_course = existing_param.get("course_id")
            ext_sec = existing_param.get("section_id")
            
            # Compare same targets
            if (new_fac and ext_fac == new_fac) or (new_course and ext_course == new_course) or (new_sec and ext_sec == new_sec):
                ext_avoid_days = set(existing_param.get("avoid_days", []))
                ext_pref_days = set(existing_param.get("preferred_days", []))
                ext_avoid_periods = set(existing_param.get("avoid_periods", []))
                ext_pref_periods = set(existing_param.get("preferred_periods", []))
                
                # Check cross preference/avoidance clash
                clash_days = new_avoid_days.intersection(ext_pref_days) or new_pref_days.intersection(ext_avoid_days)
                if clash_days:
                    contradictions.append(f"Contradicts existing rule '{r['rule_name']}': Day(s) {list(clash_days)} are avoided in one and preferred in another.")
                    
                clash_periods = new_avoid_periods.intersection(ext_pref_periods) or new_pref_periods.intersection(ext_avoid_periods)
                if clash_periods:
                    contradictions.append(f"Contradicts existing rule '{r['rule_name']}': Period(s) {list(clash_periods)} are avoided in one and preferred in another.")

        return contradictions
