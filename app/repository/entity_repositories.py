"""Entity-specific repositories inheriting from BaseRepository, mapping SQLite rows to domain models."""
from typing import Any, Dict, List, Optional
from app.repository.base_repository import BaseRepository
from app.repository.connection import DatabaseConnectionManager
from app.core.mapping import ModelMapper
from app.core.domain import (
    Department, Faculty, Room, Lab, Course, Section, Rule
)

class DepartmentRepository(BaseRepository):
    _cache = None

    def insert_dept(self, dept_id: str, name: str) -> None:
        self.insert("department", {"department_id": dept_id, "department_name": name})
        DepartmentRepository._cache = None

    def find_by_id(self, dept_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("department", {"department_id": dept_id})

    def get_all(self) -> List[Department]:
        if DepartmentRepository._cache is None:
            DepartmentRepository._cache = [ModelMapper.to_department(row) for row in self.find_all("department")]
        return DepartmentRepository._cache

    def get_by_id(self, dept_id: str) -> Optional[Department]:
        row = self.find_by_id(dept_id)
        return ModelMapper.to_department(row) if row else None

    def add_entity(self, entity: Department) -> str:
        self.insert("department", ModelMapper.to_dict(entity))
        DepartmentRepository._cache = None
        return entity.department_id

    def update_entity(self, entity: Department) -> None:
        super().update("department", {"department_id": entity.department_id}, ModelMapper.to_dict(entity))
        DepartmentRepository._cache = None

    def delete_entity(self, dept_id: str) -> None:
        super().delete("department", {"department_id": dept_id})
        DepartmentRepository._cache = None


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
    _cache = None

    def insert_room(self, room_no: str, dept_id: str, capacity: int) -> None:
        self.insert("rooms", {
            "room_no": room_no,
            "department_id": dept_id,
            "capacity": capacity
        })
        RoomRepository._cache = None

    def find_by_no(self, room_no: str) -> Optional[Dict[str, Any]]:
        return self.find_one("rooms", {"room_no": room_no})

    def get_all(self) -> List[Room]:
        if RoomRepository._cache is None:
            RoomRepository._cache = [ModelMapper.to_room(row) for row in self.find_all("rooms")]
        return RoomRepository._cache

    def get_by_id(self, room_no: str) -> Optional[Room]:
        row = self.find_by_no(room_no)
        return ModelMapper.to_room(row) if row else None

    def add_entity(self, entity: Room) -> str:
        self.insert("rooms", ModelMapper.to_dict(entity))
        RoomRepository._cache = None
        return entity.room_no

    def update_entity(self, entity: Room) -> None:
        super().update("rooms", {"room_no": entity.room_no}, ModelMapper.to_dict(entity))
        RoomRepository._cache = None

    def delete_entity(self, room_no: str) -> None:
        super().delete("rooms", {"room_no": room_no})
        RoomRepository._cache = None


class LabRepository(BaseRepository):
    _cache = None

    def insert_lab(self, lab_room_no: str, dept_id: str, name: str, capacity: int) -> None:
        self.insert("labs", {
            "lab_room_no": lab_room_no,
            "department_id": dept_id,
            "lab_name": name,
            "capacity": capacity
        })
        LabRepository._cache = None

    def find_by_no(self, lab_room_no: str) -> Optional[Dict[str, Any]]:
        return self.find_one("labs", {"lab_room_no": lab_room_no})

    def get_all(self) -> List[Lab]:
        if LabRepository._cache is None:
            LabRepository._cache = [ModelMapper.to_lab(row) for row in self.find_all("labs")]
        return LabRepository._cache

    def get_by_id(self, lab_room_no: str) -> Optional[Lab]:
        row = self.find_by_no(lab_room_no)
        return ModelMapper.to_lab(row) if row else None

    def add_entity(self, entity: Lab) -> str:
        self.insert("labs", ModelMapper.to_dict(entity))
        LabRepository._cache = None
        return entity.lab_room_no

    def update_entity(self, entity: Lab) -> None:
        super().update("labs", {"lab_room_no": entity.lab_room_no}, ModelMapper.to_dict(entity))
        LabRepository._cache = None

    def delete_entity(self, lab_room_no: str) -> None:
        super().delete("labs", {"lab_room_no": lab_room_no})
        LabRepository._cache = None


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
        import logging
        logger = logging.getLogger("TT_Scheduler")
        rows = self.find_all("courses")
        courses = []
        for row in rows:
            if (row.get("l") or 0) == 0 and (row.get("t") or 0) == 0 and (row.get("p") or 0) == 0:
                th = row.get("theory_hours") or 0
                lh = row.get("lab_hours") or 0
                if th > 0 or lh > 0:
                    row["l"] = th
                    row["t"] = 0
                    row["p"] = lh
                    logger.info(f"Self-healed database course {row['course_id']}: setting L={th}, T=0, P={lh}")
                    self.update("courses", {"course_id": row["course_id"]}, row)
            courses.append(ModelMapper.to_course(row))
        return courses

    def get_by_id(self, course_id: str) -> Optional[Course]:
        import logging
        logger = logging.getLogger("TT_Scheduler")
        row = self.find_by_id(course_id)
        if row:
            if (row.get("l") or 0) == 0 and (row.get("t") or 0) == 0 and (row.get("p") or 0) == 0:
                th = row.get("theory_hours") or 0
                lh = row.get("lab_hours") or 0
                if th > 0 or lh > 0:
                    row["l"] = th
                    row["t"] = 0
                    row["p"] = lh
                    logger.info(f"Self-healed database course {row['course_id']}: setting L={th}, T=0, P={lh}")
                    self.update("courses", {"course_id": row["course_id"]}, row)
            return ModelMapper.to_course(row)
        return None

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
            "original_text": desc,
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
    """Repository for scheduler_run table with proper SQLite/PostgreSQL compatibility."""

    def create_run(self, year: int, semester: int, department_id: str, version: int = 1) -> int:
        """Creates a new scheduler_run record and returns the generated run_id.

        Uses RETURNING for PostgreSQL and lastrowid for SQLite.
        """
        from config.config import LOCAL_MODE
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            import datetime
            started_at = datetime.datetime.utcnow().isoformat()
            if LOCAL_MODE:
                cursor.execute(
                    """
                    INSERT INTO scheduler_run (year, semester, department_id, version, status, started_at)
                    VALUES (?, ?, ?, ?, 'RUNNING', ?)
                    """,
                    (year, semester, department_id, version, started_at)
                )
                run_id = cursor.lastrowid
                conn.commit()
            else:
                cursor.execute(
                    """
                    INSERT INTO scheduler_run (year, semester, department_id, version, status, started_at)
                    VALUES (%s, %s, %s, %s, 'RUNNING', %s)
                    RETURNING run_id
                    """,
                    (year, semester, department_id, version, started_at)
                )
                row = cursor.fetchone()
                run_id = row[0] if row else None
                conn.commit()
            return run_id
        finally:
            if should_close:
                conn.close()

    def update_run_status(
        self,
        run_id: int,
        status: str,
        total_penalty: int = 0,
        duration_seconds: float = 0.0
    ) -> None:
        """Updates the status, penalty, and finish time of a scheduler run."""
        import datetime
        finished_at = datetime.datetime.utcnow().isoformat()
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            query = self._adjust_query(
                """
                UPDATE scheduler_run
                SET status = ?, total_penalty = ?, finished_at = ?, duration_seconds = ?
                WHERE run_id = ?
                """
            )
            cursor.execute(query, (status, total_penalty, finished_at, duration_seconds, run_id))
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def get_latest_successful_run(self, year: int, semester: int, department_id: str) -> Optional[Dict[str, Any]]:
        """Returns the most recent successful run for the given semester/department."""
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            query = self._adjust_query(
                """
                SELECT * FROM scheduler_run
                WHERE status = 'SUCCESS' AND year = ? AND semester = ?
                AND (department_id IS NULL OR department_id = ?)
                ORDER BY run_id DESC LIMIT 1
                """
            )
            cursor.execute(query, (year, semester, department_id))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if should_close:
                conn.close()

    def get_latest_run_id(self) -> Optional[int]:
        """Returns the run_id of the most recent scheduler_run record."""
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT run_id FROM scheduler_run ORDER BY run_id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            if should_close:
                conn.close()


class ValidationLogRepository(BaseRepository):
    pass



class ScheduleRepository(BaseRepository):
    def find_clashes(self, run_id: int, day_id: int, period_no: int, faculty_id: str, room_no: Optional[str], lab_room_no: Optional[str]) -> List[Dict[str, Any]]:
        """Queries for existing allocations that might conflict."""
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            query = """
                SELECT * FROM schedule 
                WHERE run_id = ? AND day_id = ? AND period_no = ? 
                AND (faculty_id = ? OR room_no = ? OR lab_room_no = ?)
            """
            query = self._adjust_query(query)
            cursor = conn.cursor()
            cursor.execute(query, (run_id, day_id, period_no, faculty_id, room_no, lab_room_no))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if should_close:
                conn.close()
