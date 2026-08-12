"""Seeding script to populate Supabase PostgreSQL or SQLite database with a realistic university dataset."""
import sys
from config.config import DATABASE_PATH, DATABASE_URL, logger
from app.repository.connection import DatabaseConnectionManager, TransactionContext

DEPTS = [
    ("ISC", "Intelligent Systems and Cybersecurity"),
    ("CSE", "Computer Science and Engineering"),
    ("ECE", "Electronics and Communication Engineering")
]

TEACHERS = [
    # ISC Teachers
    ("F01", "Dr. Rekha", "ISC"), ("F02", "Dr. Daisy", "ISC"), ("F03", "Dr. Priyadarshini", "ISC"),
    ("F04", "Mr. Vishnu Sekar", "ISC"), ("F05", "Mr. Karthikeyan", "ISC"), ("F06", "Mr. Saravanan", "ISC"),
    ("F07", "Mrs. Subashini", "ISC"), ("F08", "Dr. Ramesh", "ISC"), ("F09", "Mr. Manoj", "ISC"),
    ("F10", "Mrs. Deepa", "ISC"),
    # CSE Teachers
    ("F11", "Dr. Prakash", "CSE"), ("F12", "Mr. Arun", "CSE"), ("F13", "Mrs. Kavitha", "CSE"),
    ("F14", "Mr. Suresh", "CSE"), ("F15", "Dr. Meena", "CSE"), ("F16", "Dr. Anand", "CSE"),
    ("F17", "Mrs. Geetha", "CSE"), ("F18", "Mr. Balaji", "CSE"),
    # ECE Teachers
    ("F19", "Dr. Sridhar", "ECE"), ("F20", "Dr. Lakshmi", "ECE"), ("F21", "Mr. Venkatesh", "ECE"),
    ("F22", "Mrs. Radhika", "ECE"), ("F23", "Mr. Parthiban", "ECE"), ("F24", "Dr. Uma", "ECE"),
    ("F25", "Mrs. Chitra", "ECE")
]

LAB_STAFF = [
    ("L01", "Mr. Lab AI", "ISC"), ("L02", "Mr. Lab ML", "ISC"), ("L03", "Mr. Lab Cyber", "ISC"),
    ("L04", "Mr. Lab CSE", "CSE"), ("L05", "Mr. Lab ECE", "ECE")
]

# (course_id, name, L, T, P, credits, difficulty, semester, has_lab, weekly_hours, dept_id)
COURSES = [
    # ISC Semester 7 (35 hours)
    ("ISC701", "Machine Learning", 3, 1, 0, 4, 4, 7, 0, 4, "ISC"),
    ("ISC702", "Deep Learning", 3, 1, 0, 4, 5, 7, 0, 4, "ISC"),
    ("ISC703", "Computer Vision", 3, 1, 0, 4, 4, 7, 0, 4, "ISC"),
    ("ISC704", "Business Intelligence", 3, 1, 0, 4, 3, 7, 0, 4, "ISC"),
    ("ISC705", "Cloud Computing", 3, 1, 0, 4, 3, 7, 0, 4, "ISC"),
    ("ISC706", "ML Lab", 0, 0, 3, 2, 3, 7, 1, 3, "ISC"),
    ("ISC707", "DL Lab", 0, 0, 3, 2, 3, 7, 1, 3, "ISC"),
    ("ISC708", "CV Lab", 0, 0, 3, 2, 3, 7, 1, 3, "ISC"),
    ("ISC709", "Project Seminar", 2, 1, 0, 3, 2, 7, 0, 3, "ISC"),
    ("ISC710", "Placement Foundations", 2, 1, 0, 3, 2, 7, 0, 3, "ISC"),

    # ISC Semester 5 (35 hours)
    ("ISC501", "Operating Systems", 3, 1, 0, 4, 4, 5, 0, 4, "ISC"),
    ("ISC502", "Computer Networks", 3, 1, 0, 4, 4, 5, 0, 4, "ISC"),
    ("ISC503", "Data Mining", 3, 1, 0, 4, 4, 5, 0, 4, "ISC"),
    ("ISC504", "Compiler Design", 3, 1, 0, 4, 5, 5, 0, 4, "ISC"),
    ("ISC505", "Software Engineering", 3, 1, 0, 4, 3, 5, 0, 4, "ISC"),
    ("ISC506", "OS Lab", 0, 0, 3, 2, 3, 5, 1, 3, "ISC"),
    ("ISC507", "Networks Lab", 0, 0, 3, 2, 3, 5, 1, 3, "ISC"),
    ("ISC508", "Data Mining Lab", 0, 0, 3, 2, 3, 5, 1, 3, "ISC"),
    ("ISC509", "Professional Ethics", 2, 1, 0, 3, 2, 5, 0, 3, "ISC"),
    ("ISC510", "Aptitude Training", 2, 1, 0, 3, 2, 5, 0, 3, "ISC"),

    # CSE Semester 7 (35 hours)
    ("CSE701", "Cryptography & Security", 3, 1, 0, 4, 4, 7, 0, 4, "CSE"),
    ("CSE702", "Mobile Computing", 3, 1, 0, 4, 4, 7, 0, 4, "CSE"),
    ("CSE703", "Artificial Intelligence", 3, 1, 0, 4, 4, 7, 0, 4, "CSE"),
    ("CSE704", "Big Data Analytics", 3, 1, 0, 4, 4, 7, 0, 4, "CSE"),
    ("CSE705", "Internet of Things", 3, 1, 0, 4, 4, 7, 0, 4, "CSE"),
    ("CSE706", "Security Lab", 0, 0, 3, 2, 3, 7, 1, 3, "CSE"),
    ("CSE707", "AI Lab", 0, 0, 3, 2, 3, 7, 1, 3, "CSE"),
    ("CSE708", "IoT Lab", 0, 0, 3, 2, 3, 7, 1, 3, "CSE"),
    ("CSE709", "Technical Seminar", 2, 1, 0, 3, 2, 7, 0, 3, "CSE"),
    ("CSE710", "Career Guidance", 2, 1, 0, 3, 2, 7, 0, 3, "CSE"),

    # CSE Semester 5 (35 hours)
    ("CSE501", "Theory of Computation", 3, 1, 0, 4, 4, 5, 0, 4, "CSE"),
    ("CSE502", "Database Systems", 3, 1, 0, 4, 4, 5, 0, 4, "CSE"),
    ("CSE503", "Computer Graphics", 3, 1, 0, 4, 4, 5, 0, 4, "CSE"),
    ("CSE504", "Object Oriented Analysis", 3, 1, 0, 4, 4, 5, 0, 4, "CSE"),
    ("CSE505", "Web Technology", 3, 1, 0, 4, 4, 5, 0, 4, "CSE"),
    ("CSE506", "DBMS Lab", 0, 0, 3, 2, 3, 5, 1, 3, "CSE"),
    ("CSE507", "Graphics Lab", 0, 0, 3, 2, 3, 5, 1, 3, "CSE"),
    ("CSE508", "Web Lab", 0, 0, 3, 2, 3, 5, 1, 3, "CSE"),
    ("CSE509", "Environmental Science", 2, 1, 0, 3, 2, 5, 0, 3, "CSE"),
    ("CSE510", "Quantitative Methods", 2, 1, 0, 3, 2, 5, 0, 3, "CSE"),

    # ECE Semester 7 (35 hours)
    ("ECE701", "VLSI Design", 3, 1, 0, 4, 4, 7, 0, 4, "ECE"),
    ("ECE702", "Optical Communication", 3, 1, 0, 4, 4, 7, 0, 4, "ECE"),
    ("ECE703", "Embedded Systems", 3, 1, 0, 4, 4, 7, 0, 4, "ECE"),
    ("ECE704", "Microwave Engineering", 3, 1, 0, 4, 4, 7, 0, 4, "ECE"),
    ("ECE705", "Wireless Networks", 3, 1, 0, 4, 4, 7, 0, 4, "ECE"),
    ("ECE706", "VLSI Lab", 0, 0, 3, 2, 3, 7, 1, 3, "ECE"),
    ("ECE707", "Embedded Lab", 0, 0, 3, 2, 3, 7, 1, 3, "ECE"),
    ("ECE708", "Microwave Lab", 0, 0, 3, 2, 3, 7, 1, 3, "ECE"),
    ("ECE709", "ECE Seminar", 2, 1, 0, 3, 2, 7, 0, 3, "ECE"),
    ("ECE710", "Interview Skills", 2, 1, 0, 3, 2, 7, 0, 3, "ECE"),

    # ECE Semester 5 (35 hours)
    ("ECE501", "Microcontrollers", 3, 1, 0, 4, 4, 5, 0, 4, "ECE"),
    ("ECE502", "Signal Processing", 3, 1, 0, 4, 4, 5, 0, 4, "ECE"),
    ("ECE503", "Transmission Lines", 3, 1, 0, 4, 4, 5, 0, 4, "ECE"),
    ("ECE504", "Analog Communication", 3, 1, 0, 4, 4, 5, 0, 4, "ECE"),
    ("ECE505", "Control Systems", 3, 1, 0, 4, 4, 5, 0, 4, "ECE"),
    ("ECE506", "Microcontroller Lab", 0, 0, 3, 2, 3, 5, 1, 3, "ECE"),
    ("ECE507", "DSP Lab", 0, 0, 3, 2, 3, 5, 1, 3, "ECE"),
    ("ECE508", "Communication Lab", 0, 0, 3, 2, 3, 5, 1, 3, "ECE"),
    ("ECE509", "Industrial Orientation", 2, 1, 0, 3, 2, 5, 0, 3, "ECE"),
    ("ECE510", "Group Discussion", 2, 1, 0, 3, 2, 5, 0, 3, "ECE")
]

SECTIONS = [
    # (section_id, section_name, semester, department_id, capacity)
    ("IS7A", "ISC 7A", 7, "ISC", 60),
    ("IS5A", "ISC 5A", 5, "ISC", 60),
    ("CS7A", "CSE 7A", 7, "CSE", 60),
    ("CS5A", "CSE 5A", 5, "CSE", 60),
    ("EC7A", "ECE 7A", 7, "ECE", 60),
    ("EC5A", "ECE 5A", 5, "ECE", 60)
]

ROOMS = [
    ("JB401", "ISC", 60),
    ("JB402", "ISC", 60),
    ("JB403", "CSE", 60),
    ("JB404", "CSE", 60),
    ("JB405", "ECE", 60),
    ("JB406", "ECE", 60)
]

LABS = [
    ("LAB101", "ISC", "AI Laboratory", 35),
    ("LAB102", "ISC", "ML Laboratory", 35),
    ("LAB103", "ISC", "Cyber Security Laboratory", 35),
    ("LAB104", "CSE", "Network/Systems Laboratory", 35),
    ("LAB105", "ECE", "Electronics/IoT Laboratory", 35)
]

CLASS_TEACHERS = {
    "IS7A": "F01",
    "IS5A": "F02",
    "CS7A": "F11",
    "CS5A": "F12",
    "EC7A": "F19",
    "EC5A": "F20"
}

def seed_data():
    if DATABASE_URL:
        logger.info("Seeding realistic university dataset to Supabase PostgreSQL.")
    else:
        logger.info("Seeding realistic university dataset to SQLite.")

    with TransactionContext() as ctx:
        conn = ctx.conn
        cursor = conn.cursor()

        # 1. Clean existing records in dependency order
        logger.info("Truncating old database records...")
        
        # Clear schedule
        cursor.execute("DELETE FROM schedule")
        cursor.execute("DELETE FROM validation_log")
        cursor.execute("DELETE FROM scheduler_run")
        cursor.execute("DELETE FROM class_teacher")
        cursor.execute("DELETE FROM room_section")
        cursor.execute("DELETE FROM course_lab")
        cursor.execute("DELETE FROM section_course")
        cursor.execute("DELETE FROM department_course")
        cursor.execute("DELETE FROM department_faculty")
        cursor.execute("DELETE FROM faculty_assignment")
        cursor.execute("DELETE FROM faculty_unavailable")
        cursor.execute("DELETE FROM rules")
        cursor.execute("DELETE FROM template")
        cursor.execute("DELETE FROM days")
        cursor.execute("DELETE FROM sections")
        cursor.execute("DELETE FROM courses")
        cursor.execute("DELETE FROM labs")
        cursor.execute("DELETE FROM rooms")
        cursor.execute("DELETE FROM faculty")
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM department")
        cursor.execute("DELETE FROM academic_year")

        # 2. Insert Departments
        depts_with_hod = [
            ("ISC", "Intelligent Systems and Cybersecurity", "F01"),
            ("CSE", "Computer Science and Engineering", "F11"),
            ("ECE", "Electronics and Communication Engineering", "F19")
        ]
        for dept_id, name, hod in depts_with_hod:
            cursor.execute("INSERT INTO department(department_id, department_name, hod) VALUES (?, ?, ?)", (dept_id, name, hod))

        # 3. Insert Academic Year
        cursor.execute("INSERT INTO academic_year(year, semester, odd_even) VALUES (2026, 1, 'ODD')")

        # 4. Insert Days
        for i, name in enumerate(["Monday","Tuesday","Wednesday","Thursday","Friday"], 1):
            cursor.execute("INSERT INTO days(day_id, day_name) VALUES (?, ?)", (i, name))

        # 5. Insert Template (7 periods per day)
        template = [(d,p,s,e,b,l) for d in range(1,6) for p,s,e,b,l in [
            (1,"08:30","09:25",0,0), (2,"09:25","10:20",0,0), (3,"10:40","11:35",0,0),
            (4,"11:35","12:30",0,0), (5,"13:20","14:15",0,0), (6,"14:15","15:10",0,0),
            (7,"15:10","16:05",0,0)
        ]]
        for row in template:
            cursor.execute("INSERT INTO template(day_id, period_no, start_time, end_time, is_break, is_lunch) VALUES (?, ?, ?, ?, ?, ?)", row)

        # 6. Insert Faculty & Department bindings
        for fid, name, dept_id in TEACHERS:
            desig = 'Professor' if 'Dr.' in name else 'Assistant Professor'
            cursor.execute("""
                INSERT INTO faculty(faculty_id, faculty_name, max_hours_week, email, status, department_id, designation, professor_type, max_hours_daily) 
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, 'Regular', 8)
            """, (fid, name, 30, f"{fid.lower()}@university.edu.in", dept_id, desig))
            cursor.execute("INSERT INTO department_faculty(department_id, faculty_id) VALUES (?, ?)", (dept_id, fid))

        for fid, name, dept_id in LAB_STAFF:
            cursor.execute("""
                INSERT INTO faculty(faculty_id, faculty_name, max_hours_week, email, status, department_id, designation, professor_type, max_hours_daily) 
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, 'Lab Instructor', 'Regular', 8)
            """, (fid, name, 30, f"{fid.lower()}@university.edu.in", dept_id))
            cursor.execute("INSERT INTO department_faculty(department_id, faculty_id) VALUES (?, ?)", (dept_id, fid))

        # 7. Insert Classrooms (Rooms)
        for r_no, dept_id, cap in ROOMS:
            cursor.execute("INSERT INTO rooms(room_no, department_id, capacity, room_type) VALUES (?, ?, ?, 'SMART')", (r_no, dept_id, cap))

        # 8. Insert Laboratories (Labs)
        for l_no, dept_id, name, cap in LABS:
            incharge_id = "F04" if dept_id == "ISC" else ("F12" if dept_id == "CSE" else "F21")
            cursor.execute("""
                INSERT INTO labs(lab_room_no, department_id, lab_name, capacity, lab_incharge_id, equipment) 
                VALUES (?, ?, ?, ?, ?, 'Computers, Projector')
            """, (l_no, dept_id, name, cap, incharge_id))

        # 9. Insert Sections and Room Sections
        for sid, sname, sem, dept_id, cap in SECTIONS:
            # Find matching room and link it
            matching_room = next(r[0] for r in ROOMS if r[1] == dept_id and (sid.endswith("7A") and r[0].endswith("1") or sid.endswith("5A") and r[0].endswith("2") or sid.endswith("7A") and r[0].endswith("3") or sid.endswith("5A") and r[0].endswith("4") or sid.endswith("7A") and r[0].endswith("5") or sid.endswith("5A") and r[0].endswith("6")))
            mentor_id = CLASS_TEACHERS.get(sid)
            cursor.execute("""
                INSERT INTO sections(section_id, section_name, semester, department_id, capacity, strength, class_teacher_id, classroom_id) 
                VALUES (?, ?, ?, ?, ?, 60, ?, ?)
            """, (sid, sname, sem, dept_id, cap, mentor_id, matching_room))
            cursor.execute("INSERT INTO room_section(room_no, section_id) VALUES (?, ?)", (matching_room, sid))

        # 10. Link Class Mentors (Class Teachers)
        for sid, mentor_id in CLASS_TEACHERS.items():
            cursor.execute("INSERT INTO class_teacher(section_id, faculty_id) VALUES (?, ?)", (sid, mentor_id))

        # 11. Insert Courses and Department-Course Links
        labs_by_sem = {
            7: {"ISC": ["LAB103", "LAB102", "LAB101"], "CSE": ["LAB104", "LAB104", "LAB104"], "ECE": ["LAB105", "LAB105", "LAB105"]},
            5: {"ISC": ["LAB101", "LAB102", "LAB103"], "CSE": ["LAB104", "LAB104", "LAB104"], "ECE": ["LAB105", "LAB105", "LAB105"]}
        }
        for row in COURSES:
            # (course_id, name, L, T, P, credits, difficulty, semester, has_lab, weekly_hours, dept_id)
            c_id = row[0]
            c_name = row[1]
            l_val, t_val, p_val = row[2], row[3], row[4]
            credits_val = row[5]
            diff_val = row[6]
            sem_val = row[7]
            has_lab_val = row[8]
            weekly_hours_val = row[9]
            dept_id_val = row[10]
            
            # get required laboratory room
            req_lab = None
            if has_lab_val:
                lab_choices = labs_by_sem[sem_val][dept_id_val]
                req_lab = lab_choices[0] if c_id.endswith("6") else (lab_choices[1] if c_id.endswith("7") else lab_choices[2])
            
            cursor.execute("""
                INSERT INTO courses(course_id, course_name, l, t, p, c, difficulty, semester, has_lab, weekly_hours, department_id, credits, theory_hours, lab_hours, course_type, required_laboratory, course_color) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CORE', ?, '#3b82f6')
            """, (c_id, c_name, l_val, t_val, p_val, credits_val, diff_val, sem_val, has_lab_val, weekly_hours_val, dept_id_val, credits_val, l_val + t_val, p_val, req_lab))
            cursor.execute("INSERT INTO department_course(department_id, course_id) VALUES (?, ?)", (dept_id_val, c_id))

        # Link Course Labs
        for code, name, l, t, p, c, diff, sem, has_lab, hours, dept_id in COURSES:
            if has_lab:
                # Get Lab Room based on semester and department
                lab_choices = labs_by_sem[sem][dept_id]
                lab_room = lab_choices[0] if code.endswith("6") else (lab_choices[1] if code.endswith("7") else lab_choices[2])
                cursor.execute("INSERT INTO course_lab(course_id, lab_room_no) VALUES (?, ?)", (code, lab_room))

        # 12. Map Section Courses and Faculty Assignments
        # To avoid overloading, we will distribute the teaching responsibilities:
        # ISC Section Assignments:
        # IS7A (Theory: F01, F02, F03, F04, F05; Labs: L01, L02, L03; Seminars: F09, F10)
        # IS5A (Theory: F06, F07, F08, F01, F02; Labs: L01, L02, L03; Seminars: F09, F10)
        # CSE Section Assignments:
        # CS7A (Theory: F11, F12, F13, F14, F15; Labs: L04; Seminars: F17, F18)
        # CS5A (Theory: F16, F11, F12, F13, F14; Labs: L04; Seminars: F17, F18)
        # ECE Section Assignments:
        # EC7A (Theory: F19, F20, F21, F22, F23; Labs: L05; Seminars: F24, F25)
        # EC5A (Theory: F21, F22, F23, F24, F25; Labs: L05; Seminars: F19, F20)
        
        assigned_teachers = {
            "IS7A": {
                "ISC701": "F01", "ISC702": "F02", "ISC703": "F03", "ISC704": "F04", "ISC705": "F05",
                "ISC706": "L01", "ISC707": "L02", "ISC708": "L03", "ISC709": "F09", "ISC710": "F10"
            },
            "IS5A": {
                "ISC501": "F06", "ISC502": "F07", "ISC503": "F08", "ISC504": "F01", "ISC505": "F02",
                "ISC506": "L01", "ISC507": "L02", "ISC508": "L03", "ISC509": "F09", "ISC510": "F10"
            },
            "CS7A": {
                "CSE701": "F11", "CSE702": "F12", "CSE703": "F13", "CSE704": "F14", "CSE705": "F15",
                "CSE706": "L04", "CSE707": "L04", "CSE708": "L04", "CSE709": "F17", "CSE710": "F18"
            },
            "CS5A": {
                "CSE501": "F16", "CSE502": "F11", "CSE503": "F12", "CSE504": "F13", "CSE505": "F14",
                "CSE506": "L04", "CSE507": "L04", "CSE508": "L04", "CSE509": "F17", "CSE510": "F18"
            },
            "EC7A": {
                "ECE701": "F19", "ECE702": "F20", "ECE703": "F21", "ECE704": "F22", "ECE705": "F23",
                "ECE706": "L05", "ECE707": "L05", "ECE708": "L05", "ECE709": "F24", "ECE710": "F25"
            },
            "EC5A": {
                "ECE501": "F21", "ECE502": "F22", "ECE503": "F23", "ECE504": "F24", "ECE505": "F25",
                "ECE506": "L05", "ECE507": "L05", "ECE508": "L05", "ECE509": "F19", "ECE510": "F20"
            }
        }

        for sid, sname, sem, dept_id, cap in SECTIONS:
            # Find courses of department and semester
            semester_courses = [c for c in COURSES if c[10] == dept_id and c[7] == sem]
            for c_row in semester_courses:
                c_id = c_row[0]
                cursor.execute("INSERT INTO section_course(section_id, course_id) VALUES (?, ?)", (sid, c_id))
                
                # Fetch pre-assigned teacher for this course
                teacher_id = assigned_teachers[sid][c_id]
                cursor.execute("INSERT INTO faculty_assignment(faculty_id, section_id, course_id) VALUES (?, ?, ?)", (teacher_id, sid, c_id))

        # 13. Insert Rules
        rules = [
            ("R001","Maximum two labs per day","At most two labs per day",1,"HARD",'{"max_labs": 2}',1,0),
            ("R002","Friday afternoon unavailable","Avoid faculty classes after P5 Friday",1,"HARD",'{"friday_afternoon": "P6-P7"}',1,0),
            ("R003","Lunch fixed","Lunch break is fixed",1,"HARD",'{"lunch_break": "12:30-13:20"}',1,0),
            ("R004","Mentor hour","One mentor hour weekly",2,"SOFT",'{"mentor": 1}',1,5)
        ]
        for r in rules:
            cursor.execute("INSERT INTO rules(rule_id, rule_name, original_text, priority, type, parameter, enabled, cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", r)

        # 14. Create a default admin & HOD users in users table so login continues to work
        cursor.execute("DELETE FROM users")
        from werkzeug.security import generate_password_hash
        admin_pwd_hash = generate_password_hash("adminpassword")
        hod_pwd_hash = generate_password_hash("hodpassword")
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ("admin", admin_pwd_hash, "ADMIN"))
        cursor.execute("INSERT INTO users (username, password_hash, role, department_id) VALUES (?, ?, ?, ?)", ("hod", hod_pwd_hash, "HOD", "ISC"))

        logger.info("Realistic university dataset seeded successfully.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    seed_data()
