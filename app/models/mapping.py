"""Mapping utilities between database dictionary records and domain model objects."""
from typing import Any, Dict
from app.models.domain import (
    Department, AcademicYear, Faculty, Room, Lab, Course, Section, Rule,
    Template, FacultyAssignment, FacultyUnavailable, CourseLab, RoomSection,
    ClassTeacher, User, ImportLog, SchedulerRun, ValidationLog, Schedule
)

class ModelMapper:
    """Utility class to convert SQL row dictionaries to domain models and vice versa."""
    
    @staticmethod
    def to_dict(obj: Any) -> Dict[str, Any]:
        """Converts a domain model object to a database-compatible dictionary."""
        # Standard conversion using dataclass fields
        if hasattr(obj, "__dataclass_fields__"):
            raw_dict = {}
            for field_name in obj.__dataclass_fields__:
                val = getattr(obj, field_name)
                # Convert boolean types to SQLite 0/1 integers
                if isinstance(val, bool):
                    val = 1 if val else 0
                raw_dict[field_name] = val
            return raw_dict
        raise TypeError(f"Object of type {type(obj)} is not a dataclass")

    @staticmethod
    def to_department(data: Dict[str, Any]) -> Department:
        return Department(
            department_id=data["department_id"],
            department_name=data["department_name"],
            hod=data.get("hod"),
            email=data.get("email"),
            phone=data.get("phone")
        )

    @staticmethod
    def to_academic_year(data: Dict[str, Any]) -> AcademicYear:
        return AcademicYear(
            year=int(data["year"]),
            semester=int(data["semester"]),
            odd_even=data["odd_even"]
        )

    @staticmethod
    def to_faculty(data: Dict[str, Any]) -> Faculty:
        return Faculty(
            faculty_id=data["faculty_id"],
            faculty_name=data["faculty_name"],
            max_hours_week=int(data["max_hours_week"]),
            email=data.get("email"),
            status=data.get("status", "ACTIVE"),
            phone=data.get("phone"),
            designation=data.get("designation"),
            max_hours_daily=int(data["max_hours_daily"]) if data.get("max_hours_daily") is not None else 8
        )

    @staticmethod
    def to_room(data: Dict[str, Any]) -> Room:
        return Room(
            room_no=data["room_no"],
            department_id=data["department_id"],
            capacity=int(data["capacity"]),
            building=data.get("building"),
            floor=int(data["floor"]) if data.get("floor") is not None else None
        )

    @staticmethod
    def to_lab(data: Dict[str, Any]) -> Lab:
        return Lab(
            lab_room_no=data["lab_room_no"],
            department_id=data["department_id"],
            lab_name=data["lab_name"],
            capacity=int(data["capacity"]),
            supported_courses=data.get("supported_courses")
        )

    @staticmethod
    def to_course(data: Dict[str, Any]) -> Course:
        return Course(
            course_id=data["course_id"],
            course_name=data["course_name"],
            l=int(data["l"]),
            t=int(data["t"]),
            p=int(data["p"]),
            c=int(data["c"]),
            difficulty=int(data.get("difficulty", 1)),
            semester=int(data["semester"]),
            has_lab=bool(data.get("has_lab", 0)),
            weekly_hours=int(data["weekly_hours"])
        )

    @staticmethod
    def to_section(data: Dict[str, Any]) -> Section:
        return Section(
            section_id=data["section_id"],
            section_name=data["section_name"],
            semester=int(data["semester"]),
            department_id=data["department_id"],
            capacity=int(data["capacity"])
        )

    @staticmethod
    def to_rule(data: Dict[str, Any]) -> Rule:
        return Rule(
            rule_id=data["rule_id"],
            rule_name=data["rule_name"],
            description=data.get("description"),
            priority=int(data.get("priority", 1)),
            type=data["type"],
            parameter=data.get("parameter"),
            enabled=bool(data.get("enabled", 1)),
            cost=int(data.get("cost", 0))
        )

    @staticmethod
    def to_template(data: Dict[str, Any]) -> Template:
        return Template(
            day_id=int(data["day_id"]),
            period_no=int(data["period_no"]),
            start_time=data["start_time"],
            end_time=data["end_time"],
            is_break=bool(data.get("is_break", 0)),
            is_lunch=bool(data.get("is_lunch", 0))
        )

    @staticmethod
    def to_faculty_assignment(data: Dict[str, Any]) -> FacultyAssignment:
        return FacultyAssignment(
            faculty_id=data["faculty_id"],
            section_id=data["section_id"],
            course_id=data["course_id"]
        )

    @staticmethod
    def to_faculty_unavailable(data: Dict[str, Any]) -> FacultyUnavailable:
        return FacultyUnavailable(
            faculty_id=data["faculty_id"],
            day_id=int(data["day_id"]),
            period_no=int(data["period_no"]),
            reason=data.get("reason")
        )

    @staticmethod
    def to_course_lab(data: Dict[str, Any]) -> CourseLab:
        return CourseLab(
            course_id=data["course_id"],
            lab_room_no=data["lab_room_no"]
        )

    @staticmethod
    def to_room_section(data: Dict[str, Any]) -> RoomSection:
        return RoomSection(
            room_no=data["room_no"],
            section_id=data["section_id"]
        )

    @staticmethod
    def to_class_teacher(data: Dict[str, Any]) -> ClassTeacher:
        return ClassTeacher(
            section_id=data["section_id"],
            faculty_id=data["faculty_id"]
        )

    @staticmethod
    def to_user(data: Dict[str, Any]) -> User:
        return User(
            user_id=data.get("user_id"),
            username=data["username"],
            password_hash=data["password_hash"],
            role=data["role"],
            department_id=data.get("department_id")
        )

    @staticmethod
    def to_import_log(data: Dict[str, Any]) -> ImportLog:
        return ImportLog(
            import_id=data.get("import_id"),
            file_name=data["file_name"],
            uploaded_by=data.get("uploaded_by"),
            upload_time=data.get("upload_time"),
            status=data.get("status"),
            remarks=data.get("remarks")
        )

    @staticmethod
    def to_scheduler_run(data: Dict[str, Any]) -> SchedulerRun:
        return SchedulerRun(
            run_id=data.get("run_id"),
            year=int(data["year"]),
            semester=int(data["semester"]),
            department_id=data["department_id"],
            version=int(data.get("version", 1)),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_seconds=data.get("duration_seconds"),
            status=data.get("status"),
            total_penalty=int(data.get("total_penalty", 0))
        )

    @staticmethod
    def to_validation_log(data: Dict[str, Any]) -> ValidationLog:
        return ValidationLog(
            validation_id=data.get("validation_id"),
            run_id=int(data["run_id"]),
            rule_id=data["rule_id"],
            status=data["status"],
            penalty=int(data.get("penalty", 0)),
            remarks=data.get("remarks")
        )

    @staticmethod
    def to_schedule(data: Dict[str, Any]) -> Schedule:
        return Schedule(
            schedule_id=data.get("schedule_id"),
            run_id=int(data["run_id"]),
            section_id=data["section_id"],
            day_id=int(data["day_id"]),
            period_no=int(data["period_no"]),
            course_id=data["course_id"],
            faculty_id=data["faculty_id"],
            room_no=data.get("room_no"),
            lab_room_no=data.get("lab_room_no"),
            year=int(data["year"]),
            semester=int(data["semester"])
        )
