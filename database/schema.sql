PRAGMA foreign_keys = ON;

----------------------------------------------------------
-- DATABASE : TIMETABLE AUTOMATION SYSTEM
-- VERSION 1.0
----------------------------------------------------------

----------------------------------------------------------
-- DEPARTMENT
----------------------------------------------------------

CREATE TABLE department (
    department_id TEXT PRIMARY KEY,
    department_name TEXT NOT NULL UNIQUE,
    hod TEXT, -- Faculty ID

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

----------------------------------------------------------
-- DAYS
----------------------------------------------------------

CREATE TABLE days (
    day_id INTEGER PRIMARY KEY,
    day_name TEXT NOT NULL UNIQUE
);

----------------------------------------------------------
-- ACADEMIC YEAR
-- (preserved unchanged)
----------------------------------------------------------

CREATE TABLE academic_year (
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    odd_even TEXT NOT NULL
        CHECK(odd_even IN ('ODD','EVEN')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    PRIMARY KEY(year,semester)
);

----------------------------------------------------------
-- FACULTY
----------------------------------------------------------

CREATE TABLE faculty (
    faculty_id TEXT PRIMARY KEY,
    faculty_name TEXT NOT NULL,
    max_hours_week INTEGER NOT NULL CHECK(max_hours_week>=0),
    email TEXT UNIQUE,
    status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','ON_LEAVE','TRANSFERRED','RETIRED')),
    
    department_id TEXT REFERENCES department(department_id) ON UPDATE CASCADE,
    designation TEXT,
    professor_type TEXT,
    phone TEXT,
    max_hours_daily INTEGER DEFAULT 8 CHECK(max_hours_daily>=0),
    availability TEXT,
    specialization TEXT,
    preferred_days TEXT,
    preferred_time_slots TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

----------------------------------------------------------
-- LABS
----------------------------------------------------------

CREATE TABLE labs (
    lab_room_no TEXT PRIMARY KEY,
    department_id TEXT NOT NULL,
    lab_name TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity>0),
    
    lab_incharge_id TEXT REFERENCES faculty(faculty_id) ON UPDATE CASCADE,
    equipment TEXT,
    availability TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY(department_id) REFERENCES department(department_id) ON UPDATE CASCADE
);

----------------------------------------------------------
-- ROOMS
----------------------------------------------------------

CREATE TABLE rooms (
    room_no TEXT PRIMARY KEY,
    department_id TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity>0),
    
    room_type TEXT DEFAULT 'SMART' CHECK(room_type IN ('PROJECTOR','SMART','LAB')),
    availability TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY(department_id) REFERENCES department(department_id) ON UPDATE CASCADE
);

----------------------------------------------------------
-- COURSES
----------------------------------------------------------

CREATE TABLE courses (
    course_id TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    l INTEGER NOT NULL DEFAULT 0,
    t INTEGER NOT NULL DEFAULT 0,
    p INTEGER NOT NULL DEFAULT 0,
    c INTEGER NOT NULL DEFAULT 0,
    difficulty INTEGER DEFAULT 1,
    semester INTEGER NOT NULL,
    has_lab INTEGER DEFAULT 0,
    weekly_hours INTEGER NOT NULL,
    
    department_id TEXT REFERENCES department(department_id) ON UPDATE CASCADE,
    credits INTEGER DEFAULT 3,
    theory_hours INTEGER DEFAULT 3,
    lab_hours INTEGER DEFAULT 0,
    course_type TEXT DEFAULT 'CORE' CHECK(course_type IN ('CORE','ELECTIVE')),
    required_laboratory TEXT REFERENCES labs(lab_room_no) ON UPDATE CASCADE,
    course_color TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

----------------------------------------------------------
-- SECTIONS
----------------------------------------------------------

CREATE TABLE sections (
    section_id TEXT PRIMARY KEY,
    section_name TEXT NOT NULL,
    semester INTEGER NOT NULL,
    department_id TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    
    strength INTEGER DEFAULT 60,
    class_teacher_id TEXT REFERENCES faculty(faculty_id) ON UPDATE CASCADE,
    classroom_id TEXT REFERENCES rooms(room_no) ON UPDATE CASCADE,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY(department_id) REFERENCES department(department_id) ON UPDATE CASCADE
);

----------------------------------------------------------
-- RULES
----------------------------------------------------------

CREATE TABLE rules (
    rule_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    rule_name TEXT NOT NULL,
    original_text TEXT,
    generated_json TEXT,
    department_id TEXT,
    priority INTEGER DEFAULT 1,
    type TEXT NOT NULL CHECK(type IN ('HARD','SOFT')),
    parameter TEXT,
    enabled INTEGER DEFAULT 1,
    cost INTEGER DEFAULT 0,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    PRIMARY KEY(rule_id, version),
    FOREIGN KEY(department_id) REFERENCES department(department_id) ON UPDATE CASCADE
);

----------------------------------------------------------
-- TEMPLATE
----------------------------------------------------------

CREATE TABLE template (

    day_id INTEGER NOT NULL,

    period_no INTEGER NOT NULL,

    start_time TEXT NOT NULL,

    end_time TEXT NOT NULL,

    is_break INTEGER DEFAULT 0,

    is_lunch INTEGER DEFAULT 0,

    PRIMARY KEY(day_id,period_no),

    FOREIGN KEY(day_id)
        REFERENCES days(day_id)
);

----------------------------------------------------------
-- DEPARTMENT ↔ FACULTY
----------------------------------------------------------

CREATE TABLE department_faculty (

    department_id TEXT NOT NULL,

    faculty_id TEXT NOT NULL,

    PRIMARY KEY(department_id, faculty_id),

    FOREIGN KEY(department_id)
        REFERENCES department(department_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(faculty_id)
        REFERENCES faculty(faculty_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- DEPARTMENT ↔ COURSE
----------------------------------------------------------

CREATE TABLE department_course (

    department_id TEXT NOT NULL,

    course_id TEXT NOT NULL,

    PRIMARY KEY(department_id, course_id),

    FOREIGN KEY(department_id)
        REFERENCES department(department_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- SECTION ↔ COURSE
----------------------------------------------------------

CREATE TABLE section_course (

    section_id TEXT NOT NULL,

    course_id TEXT NOT NULL,

    PRIMARY KEY(section_id, course_id),

    FOREIGN KEY(section_id)
        REFERENCES sections(section_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- FACULTY ↔ COURSE
----------------------------------------------------------

CREATE TABLE faculty_course (

    faculty_id TEXT NOT NULL,

    course_id TEXT NOT NULL,

    PRIMARY KEY(faculty_id, course_id),

    FOREIGN KEY(faculty_id)
        REFERENCES faculty(faculty_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- FACULTY ASSIGNMENT
-- (Faculty teaches Course for Section)
----------------------------------------------------------

CREATE TABLE faculty_assignment (

    faculty_id TEXT NOT NULL,

    section_id TEXT NOT NULL,

    course_id TEXT NOT NULL,

    PRIMARY KEY(faculty_id, section_id, course_id),
    UNIQUE(section_id, course_id),

    FOREIGN KEY(faculty_id)
        REFERENCES faculty(faculty_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(section_id)
        REFERENCES sections(section_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- FACULTY UNAVAILABLE
----------------------------------------------------------

CREATE TABLE faculty_unavailable (

    faculty_id TEXT NOT NULL,

    day_id INTEGER NOT NULL,

    period_no INTEGER NOT NULL,

    reason TEXT,

    PRIMARY KEY(faculty_id, day_id, period_no),

    FOREIGN KEY(faculty_id)
        REFERENCES faculty(faculty_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(day_id)
        REFERENCES days(day_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- COURSE ↔ LAB
----------------------------------------------------------

CREATE TABLE course_lab (

    course_id TEXT NOT NULL,

    lab_room_no TEXT NOT NULL,

    PRIMARY KEY(course_id, lab_room_no),

    FOREIGN KEY(course_id)
        REFERENCES courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(lab_room_no)
        REFERENCES labs(lab_room_no)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- ROOM ↔ SECTION
----------------------------------------------------------

CREATE TABLE room_section (

    room_no TEXT NOT NULL,

    section_id TEXT NOT NULL,

    PRIMARY KEY(room_no, section_id),

    FOREIGN KEY(room_no)
        REFERENCES rooms(room_no)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(section_id)
        REFERENCES sections(section_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- CLASS TEACHER
----------------------------------------------------------

CREATE TABLE class_teacher (

    section_id TEXT PRIMARY KEY,

    faculty_id TEXT NOT NULL,

    FOREIGN KEY(section_id)
        REFERENCES sections(section_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY(faculty_id)
        REFERENCES faculty(faculty_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- USERS
----------------------------------------------------------

CREATE TABLE users (

    user_id INTEGER PRIMARY KEY AUTOINCREMENT,

    username TEXT NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    role TEXT NOT NULL
        CHECK(role IN ('ADMIN','HOD')),

    department_id TEXT,

    last_login DATETIME,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(department_id)
        REFERENCES department(department_id)
        ON UPDATE CASCADE
);

----------------------------------------------------------
-- IMPORT LOG
----------------------------------------------------------

CREATE TABLE import_log (

    import_id INTEGER PRIMARY KEY AUTOINCREMENT,

    file_name TEXT NOT NULL,

    uploaded_by INTEGER,

    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,

    status TEXT,

    remarks TEXT,

    FOREIGN KEY(uploaded_by)
        REFERENCES users(user_id)
);

----------------------------------------------------------
-- SCHEDULER RUN
----------------------------------------------------------

CREATE TABLE scheduler_run (

    run_id INTEGER PRIMARY KEY AUTOINCREMENT,

    year INTEGER NOT NULL,

    semester INTEGER NOT NULL,

    department_id TEXT NOT NULL,

    version INTEGER DEFAULT 1,

    started_at DATETIME,

    finished_at DATETIME,

    duration_seconds REAL,

    status TEXT
        CHECK(status IN
        ('RUNNING','SUCCESS','FAILED')),

    total_penalty INTEGER DEFAULT 0,

    FOREIGN KEY(department_id)
        REFERENCES department(department_id),

    FOREIGN KEY(year,semester)
        REFERENCES academic_year(year,semester)
);

----------------------------------------------------------
-- VALIDATION LOG
----------------------------------------------------------

CREATE TABLE validation_log (

    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id INTEGER NOT NULL,

    rule_id TEXT NOT NULL,

    status TEXT
        CHECK(status IN ('PASS','FAIL')),

    penalty INTEGER DEFAULT 0,

    remarks TEXT,

    FOREIGN KEY(run_id)
        REFERENCES scheduler_run(run_id)
        ON DELETE CASCADE
);

----------------------------------------------------------
-- GENERATED SCHEDULE
----------------------------------------------------------

CREATE TABLE schedule (

    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id INTEGER NOT NULL,

    section_id TEXT NOT NULL,

    day_id INTEGER NOT NULL,

    period_no INTEGER NOT NULL,

    course_id TEXT NOT NULL,

    faculty_id TEXT NOT NULL,

    room_no TEXT,

    lab_room_no TEXT,

    year INTEGER NOT NULL,

    semester INTEGER NOT NULL,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(run_id)
        REFERENCES scheduler_run(run_id)
        ON DELETE CASCADE,

    FOREIGN KEY(section_id)
        REFERENCES sections(section_id),

    FOREIGN KEY(day_id)
        REFERENCES days(day_id),

    FOREIGN KEY(course_id)
        REFERENCES courses(course_id),

    FOREIGN KEY(faculty_id)
        REFERENCES faculty(faculty_id),

    FOREIGN KEY(room_no)
        REFERENCES rooms(room_no),

    FOREIGN KEY(lab_room_no)
        REFERENCES labs(lab_room_no),

    FOREIGN KEY(year,semester)
        REFERENCES academic_year(year,semester),

    UNIQUE(run_id, section_id, day_id, period_no),

    UNIQUE(run_id, faculty_id, day_id, period_no),

    UNIQUE(run_id, room_no, day_id, period_no),

    UNIQUE(run_id, lab_room_no, day_id, period_no)
);

----------------------------------------------------------
-- INDEXES
----------------------------------------------------------

CREATE INDEX idx_faculty_name
ON faculty(faculty_name);

CREATE INDEX idx_course_name
ON courses(course_name);

CREATE INDEX idx_section_department
ON sections(department_id);

CREATE INDEX idx_schedule_section
ON schedule(section_id);

CREATE INDEX idx_schedule_faculty
ON schedule(faculty_id);

CREATE INDEX idx_schedule_room
ON schedule(room_no);

CREATE INDEX idx_schedule_lab
ON schedule(lab_room_no);

CREATE INDEX idx_schedule_day
ON schedule(day_id);

CREATE INDEX idx_schedule_run
ON schedule(run_id);

CREATE INDEX idx_faculty_assignment_faculty
ON faculty_assignment(faculty_id);

CREATE INDEX idx_faculty_assignment_section
ON faculty_assignment(section_id);

CREATE INDEX idx_faculty_course
ON faculty_course(course_id);

CREATE INDEX idx_section_course
ON section_course(section_id);

CREATE INDEX idx_department_course
ON department_course(department_id);

CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department_id);
CREATE INDEX IF NOT EXISTS idx_courses_department ON courses(department_id);
CREATE INDEX IF NOT EXISTS idx_rules_department ON rules(department_id);
CREATE INDEX IF NOT EXISTS idx_faculty_unavailability_faculty ON faculty_unavailable(faculty_id);
CREATE INDEX IF NOT EXISTS idx_room_section_section ON room_section(section_id);
CREATE INDEX IF NOT EXISTS idx_room_section_room ON room_section(room_no);
CREATE INDEX IF NOT EXISTS idx_class_teacher_section ON class_teacher(section_id);
CREATE INDEX IF NOT EXISTS idx_class_teacher_faculty ON class_teacher(faculty_id);
CREATE INDEX IF NOT EXISTS idx_course_lab_course ON course_lab(course_id);
CREATE INDEX IF NOT EXISTS idx_course_lab_lab ON course_lab(lab_room_no);
CREATE INDEX IF NOT EXISTS idx_scheduler_run_department ON scheduler_run(department_id);
CREATE INDEX IF NOT EXISTS idx_department_course_course ON department_course(course_id);
CREATE INDEX IF NOT EXISTS idx_faculty_course_faculty ON faculty_course(faculty_id);
CREATE INDEX IF NOT EXISTS idx_section_course_course ON section_course(course_id);

----------------------------------------------------------
-- DEFAULT DAYS
----------------------------------------------------------

INSERT INTO days(day_id,day_name) VALUES
(1,'Monday'),
(2,'Tuesday'),
(3,'Wednesday'),
(4,'Thursday'),
(5,'Friday');