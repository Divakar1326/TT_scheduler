"""Domain models for University Timetable Management System."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

@dataclass
class Department:
    department_id: str
    department_name: str
    hod: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    def __post_init__(self):
        if not self.department_id or not self.department_id.strip():
            raise ValueError("department_id cannot be empty")
        if not self.department_name or not self.department_name.strip():
            raise ValueError("department_name cannot be empty")


@dataclass
class AcademicYear:
    year: int
    semester: int
    odd_even: str  # 'ODD' or 'EVEN'

    def __post_init__(self):
        if self.year <= 0:
            raise ValueError("year must be positive")
        if self.semester <= 0:
            raise ValueError("semester must be positive")
        if self.odd_even not in ("ODD", "EVEN"):
            raise ValueError("odd_even must be 'ODD' or 'EVEN'")


@dataclass
class Faculty:
    faculty_id: str
    faculty_name: str
    max_hours_week: int
    email: Optional[str] = None
    status: str = "ACTIVE"  # 'ACTIVE', 'ON_LEAVE', 'TRANSFERRED', 'RETIRED'
    phone: Optional[str] = None
    designation: Optional[str] = None
    max_hours_daily: int = 8

    def __post_init__(self):
        if not self.faculty_id or not self.faculty_id.strip():
            raise ValueError("faculty_id cannot be empty")
        if not self.faculty_name or not self.faculty_name.strip():
            raise ValueError("faculty_name cannot be empty")
        if self.max_hours_week < 0:
            raise ValueError("max_hours_week cannot be negative")
        if self.status not in ("ACTIVE", "ON_LEAVE", "TRANSFERRED", "RETIRED"):
            raise ValueError("Invalid faculty status")
        if self.email and not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            raise ValueError("Invalid email format")


@dataclass
class Room:
    room_no: str
    department_id: str
    capacity: int
    building: Optional[str] = None
    floor: Optional[int] = None

    def __post_init__(self):
        if not self.room_no or not self.room_no.strip():
            raise ValueError("room_no cannot be empty")
        if not self.department_id or not self.department_id.strip():
            raise ValueError("department_id cannot be empty")
        if self.capacity <= 0:
            raise ValueError("capacity must be greater than zero")


@dataclass
class Lab:
    lab_room_no: str
    department_id: str
    lab_name: str
    capacity: int
    supported_courses: Optional[str] = None

    def __post_init__(self):
        if not self.lab_room_no or not self.lab_room_no.strip():
            raise ValueError("lab_room_no cannot be empty")
        if not self.department_id or not self.department_id.strip():
            raise ValueError("department_id cannot be empty")
        if not self.lab_name or not self.lab_name.strip():
            raise ValueError("lab_name cannot be empty")
        if self.capacity <= 0:
            raise ValueError("capacity must be greater than zero")


@dataclass
class Course:
    course_id: str
    course_name: str
    l: int
    t: int
    p: int
    c: int
    difficulty: int
    semester: int
    has_lab: bool
    weekly_hours: int

    def __post_init__(self):
        if not self.course_id or not self.course_id.strip():
            raise ValueError("course_id cannot be empty")
        if not self.course_name or not self.course_name.strip():
            raise ValueError("course_name cannot be empty")
        if self.l < 0 or self.t < 0 or self.p < 0 or self.c < 0:
            raise ValueError("Course credits and load values cannot be negative")
        if self.weekly_hours <= 0:
            raise ValueError("weekly_hours must be greater than zero")
        if self.semester <= 0:
            raise ValueError("semester must be positive")


@dataclass
class Section:
    section_id: str
    section_name: str
    semester: int
    department_id: str
    capacity: int

    def __post_init__(self):
        if not self.section_id or not self.section_id.strip():
            raise ValueError("section_id cannot be empty")
        if not self.section_name or not self.section_name.strip():
            raise ValueError("section_name cannot be empty")
        if self.semester <= 0:
            raise ValueError("semester must be positive")
        if not self.department_id or not self.department_id.strip():
            raise ValueError("department_id cannot be empty")
        if self.capacity <= 0:
            raise ValueError("capacity must be greater than zero")


@dataclass
class Rule:
    rule_id: str
    rule_name: str
    description: Optional[str]
    priority: int
    type: str  # 'HARD' or 'SOFT'
    parameter: Optional[str]
    enabled: bool = True
    cost: int = 0

    def __post_init__(self):
        if not self.rule_id or not self.rule_id.strip():
            raise ValueError("rule_id cannot be empty")
        if not self.rule_name or not self.rule_name.strip():
            raise ValueError("rule_name cannot be empty")
        if self.type not in ("HARD", "SOFT"):
            raise ValueError("Rule type must be 'HARD' or 'SOFT'")
        if self.cost < 0:
            raise ValueError("Cost cannot be negative")


@dataclass
class Template:
    day_id: int
    period_no: int
    start_time: str
    end_time: str
    is_break: bool = False
    is_lunch: bool = False

    def __post_init__(self):
        if self.day_id <= 0:
            raise ValueError("day_id must be positive")
        if self.period_no <= 0:
            raise ValueError("period_no must be positive")
        if not self.start_time or not self.end_time:
            raise ValueError("start_time and end_time cannot be empty")


@dataclass
class FacultyAssignment:
    faculty_id: str
    section_id: str
    course_id: str


@dataclass
class FacultyUnavailable:
    faculty_id: str
    day_id: int
    period_no: int
    reason: Optional[str] = None


@dataclass
class CourseLab:
    course_id: str
    lab_room_no: str


@dataclass
class RoomSection:
    room_no: str
    section_id: str


@dataclass
class ClassTeacher:
    section_id: str
    faculty_id: str


@dataclass
class User:
    username: str
    password_hash: str
    role: str  # 'ADMIN', 'HOD'
    user_id: Optional[int] = None
    department_id: Optional[str] = None

    def __post_init__(self):
        if not self.username or not self.username.strip():
            raise ValueError("username cannot be empty")
        if not self.password_hash or not self.password_hash.strip():
            raise ValueError("password_hash cannot be empty")
        if self.role not in ("ADMIN", "HOD"):
            raise ValueError("User role must be 'ADMIN' or 'HOD'")


@dataclass
class ImportLog:
    file_name: str
    import_id: Optional[int] = None
    uploaded_by: Optional[int] = None
    upload_time: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


@dataclass
class SchedulerRun:
    year: int
    semester: int
    department_id: str
    run_id: Optional[int] = None
    version: int = 1
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: Optional[str] = None  # 'RUNNING', 'SUCCESS', 'FAILED'
    total_penalty: int = 0

    def __post_init__(self):
        if self.status and self.status not in ("RUNNING", "SUCCESS", "FAILED"):
            raise ValueError("Invalid scheduler run status")


@dataclass
class ValidationLog:
    run_id: int
    rule_id: str
    status: str  # 'PASS', 'FAIL'
    validation_id: Optional[int] = None
    penalty: int = 0
    remarks: Optional[str] = None

    def __post_init__(self):
        if self.status not in ("PASS", "FAIL"):
            raise ValueError("Validation status must be 'PASS' or 'FAIL'")


@dataclass
class Schedule:
    run_id: int
    section_id: str
    day_id: int
    period_no: int
    course_id: str
    faculty_id: str
    year: int
    semester: int
    schedule_id: Optional[int] = None
    room_no: Optional[str] = None
    lab_room_no: Optional[str] = None
