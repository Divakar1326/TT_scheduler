"""Entity-specific repositories inheriting from BaseRepository, mapping SQLite rows to domain models."""
from typing import Any, Dict, List, Optional
from app.repository.base_repository import BaseRepository
from app.repository.connection import DatabaseConnectionManager
from app.models.mapping import ModelMapper
from app.models.domain import (
    Department, Faculty, Room, Lab, Course, Section, Rule
)

class DepartmentRepository(BaseRepository):
    def insert_dept(self, dept_id: str, name: str) -> None:
        self.insert("department", {"department_id": dept_id, "department_name": name})

    def find_by_id(self, dept_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("department", {"department_id": dept_id})

    def get_all(self) -> List[Department]:
        return [ModelMapper.to_department(row) for row in self.find_all("department")]

    def get_by_id(self, dept_id: str) -> Optional[Department]:
        row = self.find_by_id(dept_id)
        return ModelMapper.to_department(row) if row else None

    def add_entity(self, entity: Department) -> str:
        self.insert("department", ModelMapper.to_dict(entity))
        return entity.department_id

    def update_entity(self, entity: Department) -> None:
        super().update("department", {"department_id": entity.department_id}, ModelMapper.to_dict(entity))

    def delete_entity(self, dept_id: str) -> None:
        super().delete("department", {"department_id": dept_id})


class FacultyRepository(BaseRepository):
    def insert_faculty(self, faculty_id: str, name: str, max_hours: int, email: str, status: str = "ACTIVE") -> None:
        self.insert("faculty", {
            "faculty_id": faculty_id,
            "faculty_name": name,
            "max_hours_week": max_hours,
            "email": email,
            "status": status
        })

    def find_by_id(self, faculty_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("faculty", {"faculty_id": faculty_id})

    def get_all(self) -> List[Faculty]:
        return [ModelMapper.to_faculty(row) for row in self.find_all("faculty")]

    def get_by_id(self, faculty_id: str) -> Optional[Faculty]:
        row = self.find_by_id(faculty_id)
        return ModelMapper.to_faculty(row) if row else None

    def add_entity(self, entity: Faculty) -> str:
        self.insert("faculty", ModelMapper.to_dict(entity))
        return entity.faculty_id

    def update_entity(self, entity: Faculty) -> None:
        super().update("faculty", {"faculty_id": entity.faculty_id}, ModelMapper.to_dict(entity))

    def delete_entity(self, faculty_id: str) -> None:
        super().delete("faculty", {"faculty_id": faculty_id})


class RoomRepository(BaseRepository):
    def insert_room(self, room_no: str, dept_id: str, capacity: int) -> None:
        self.insert("rooms", {
            "room_no": room_no,
            "department_id": dept_id,
            "capacity": capacity
        })

    def find_by_no(self, room_no: str) -> Optional[Dict[str, Any]]:
        return self.find_one("rooms", {"room_no": room_no})

    def get_all(self) -> List[Room]:
        return [ModelMapper.to_room(row) for row in self.find_all("rooms")]

    def get_by_id(self, room_no: str) -> Optional[Room]:
        row = self.find_by_no(room_no)
        return ModelMapper.to_room(row) if row else None

    def add_entity(self, entity: Room) -> str:
        self.insert("rooms", ModelMapper.to_dict(entity))
        return entity.room_no

    def update_entity(self, entity: Room) -> None:
        super().update("rooms", {"room_no": entity.room_no}, ModelMapper.to_dict(entity))

    def delete_entity(self, room_no: str) -> None:
        super().delete("rooms", {"room_no": room_no})


class LabRepository(BaseRepository):
    def insert_lab(self, lab_room_no: str, dept_id: str, name: str, capacity: int) -> None:
        self.insert("labs", {
            "lab_room_no": lab_room_no,
            "department_id": dept_id,
            "lab_name": name,
            "capacity": capacity
        })

    def find_by_no(self, lab_room_no: str) -> Optional[Dict[str, Any]]:
        return self.find_one("labs", {"lab_room_no": lab_room_no})

    def get_all(self) -> List[Lab]:
        return [ModelMapper.to_lab(row) for row in self.find_all("labs")]

    def get_by_id(self, lab_room_no: str) -> Optional[Lab]:
        row = self.find_by_no(lab_room_no)
        return ModelMapper.to_lab(row) if row else None

    def add_entity(self, entity: Lab) -> str:
        self.insert("labs", ModelMapper.to_dict(entity))
        return entity.lab_room_no

    def update_entity(self, entity: Lab) -> None:
        super().update("labs", {"lab_room_no": entity.lab_room_no}, ModelMapper.to_dict(entity))

    def delete_entity(self, lab_room_no: str) -> None:
        super().delete("labs", {"lab_room_no": lab_room_no})


class CourseRepository(BaseRepository):
    def insert_course(self, course_id: str, name: str, l: int, t: int, p: int, c: int,
                      difficulty: int, semester: int, has_lab: bool, weekly_hours: int) -> None:
        self.insert("courses", {
            "course_id": course_id,
            "course_name": name,
            "l": l,
            "t": t,
            "p": p,
            "c": c,
            "difficulty": difficulty,
            "semester": semester,
            "has_lab": int(has_lab),
            "weekly_hours": weekly_hours
        })

    def find_by_id(self, course_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("courses", {"course_id": course_id})

    def get_all(self) -> List[Course]:
        return [ModelMapper.to_course(row) for row in self.find_all("courses")]

    def get_by_id(self, course_id: str) -> Optional[Course]:
        row = self.find_by_id(course_id)
        return ModelMapper.to_course(row) if row else None

    def add_entity(self, entity: Course) -> str:
        self.insert("courses", ModelMapper.to_dict(entity))
        return entity.course_id

    def update_entity(self, entity: Course) -> None:
        super().update("courses", {"course_id": entity.course_id}, ModelMapper.to_dict(entity))

    def delete_entity(self, course_id: str) -> None:
        super().delete("courses", {"course_id": course_id})


class SectionRepository(BaseRepository):
    def insert_section(self, section_id: str, name: str, semester: int, dept_id: str, capacity: int) -> None:
        self.insert("sections", {
            "section_id": section_id,
            "section_name": name,
            "semester": semester,
            "department_id": dept_id,
            "capacity": capacity
        })

    def find_by_id(self, section_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("sections", {"section_id": section_id})

    def get_all(self) -> List[Section]:
        return [ModelMapper.to_section(row) for row in self.find_all("sections")]

    def get_by_id(self, section_id: str) -> Optional[Section]:
        row = self.find_by_id(section_id)
        return ModelMapper.to_section(row) if row else None

    def add_entity(self, entity: Section) -> str:
        self.insert("sections", ModelMapper.to_dict(entity))
        return entity.section_id

    def update_entity(self, entity: Section) -> None:
        super().update("sections", {"section_id": entity.section_id}, ModelMapper.to_dict(entity))

    def delete_entity(self, section_id: str) -> None:
        super().delete("sections", {"section_id": section_id})


class RulesRepository(BaseRepository):
    def insert_rule(self, rule_id: str, name: str, desc: str, priority: int, rule_type: str,
                    parameter: str, enabled: bool = True, cost: int = 0) -> None:
        self.insert("rules", {
            "rule_id": rule_id,
            "rule_name": name,
            "description": desc,
            "priority": priority,
            "type": rule_type,
            "parameter": parameter,
            "enabled": int(enabled),
            "cost": cost
        })

    def find_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("rules", {"rule_id": rule_id})

    def get_all(self) -> List[Rule]:
        return [ModelMapper.to_rule(row) for row in self.find_all("rules")]

    def get_by_id(self, rule_id: str) -> Optional[Rule]:
        row = self.find_by_id(rule_id)
        return ModelMapper.to_rule(row) if row else None

    def add_entity(self, entity: Rule) -> str:
        self.insert("rules", ModelMapper.to_dict(entity))
        return entity.rule_id

    def update_entity(self, entity: Rule) -> None:
        super().update("rules", {"rule_id": entity.rule_id}, ModelMapper.to_dict(entity))

    def delete_entity(self, rule_id: str) -> None:
        super().delete("rules", {"rule_id": rule_id})


class TemplateRepository(BaseRepository):
    def find_by_slot(self, day_id: int, period_no: int) -> Optional[Dict[str, Any]]:
        return self.find_one("template", {"day_id": day_id, "period_no": period_no})


class FacultyAssignmentRepository(BaseRepository):
    def assign_faculty(self, faculty_id: str, section_id: str, course_id: str) -> None:
        self.insert("faculty_assignment", {
            "faculty_id": faculty_id,
            "section_id": section_id,
            "course_id": course_id
        })


class FacultyUnavailableRepository(BaseRepository):
    def mark_unavailable(self, faculty_id: str, day_id: int, period_no: int, reason: str = "") -> None:
        self.insert("faculty_unavailable", {
            "faculty_id": faculty_id,
            "day_id": day_id,
            "period_no": period_no,
            "reason": reason
        })


class CourseLabRepository(BaseRepository):
    def link_course_lab(self, course_id: str, lab_room_no: str) -> None:
        self.insert("course_lab", {"course_id": course_id, "lab_room_no": lab_room_no})


class RoomSectionRepository(BaseRepository):
    def link_room_section(self, room_no: str, section_id: str) -> None:
        self.insert("room_section", {"room_no": room_no, "section_id": section_id})


class ClassTeacherRepository(BaseRepository):
    def assign_class_teacher(self, section_id: str, faculty_id: str) -> None:
        self.insert("class_teacher", {"section_id": section_id, "faculty_id": faculty_id})


class UserRepository(BaseRepository):
    def create_user(self, username: str, password_hash: str, role: str, dept_id: Optional[str] = None) -> None:
        self.insert("users", {
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "department_id": dept_id
        })

    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return self.find_one("users", {"username": username})


class ImportLogRepository(BaseRepository):
    pass


class SchedulerRunRepository(BaseRepository):
    pass


class ValidationLogRepository(BaseRepository):
    pass


class ScheduleRepository(BaseRepository):
    def find_clashes(self, run_id: int, day_id: int, period_no: int, faculty_id: str, room_no: Optional[str], lab_room_no: Optional[str]) -> List[Dict[str, Any]]:
        """Queries for existing allocations that might conflict."""
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            query = """
                SELECT * FROM schedule 
                WHERE run_id = ? AND day_id = ? AND period_no = ? 
                AND (faculty_id = ? OR room_no = ? OR lab_room_no = ?)
            """
            cursor.execute(query, (run_id, day_id, period_no, faculty_id, room_no, lab_room_no))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if should_close:
                conn.close()
