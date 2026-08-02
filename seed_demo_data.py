"""Idempotently seed Phase 1 ISC timetable data into timetable.db."""
import sqlite3
from config import DATABASE_PATH

DEPT = "ISC"
TEACHERS = [
    ("F01", "Dr. Rekha"), ("F02", "Dr. Daisy"), ("F03", "Dr. Priyadarshini"),
    ("F04", "Mr. Vishnu Sekar"), ("F05", "Mr. Karthikeyan"), ("F06", "Mr. Saravanan"),
    ("F07", "Mrs. Subashini"), ("F08", "Dr. Ramesh"), ("F09", "Mr. Manoj"),
    ("F10", "Mrs. Deepa"), ("F11", "Dr. Prakash"), ("F12", "Mr. Arun"),
    ("F13", "Mrs. Kavitha"), ("F14", "Mr. Suresh"), ("F15", "Dr. Meena"),
]
LAB_STAFF = [("L01", "Mr. Lab AI"), ("L02", "Mr. Lab ML"), ("L03", "Mr. Lab Cyber")]

# course_id, name, L, T, P, credits, difficulty, semester, has_lab, hours
COURSES = [
    ("ISC701", "Machine Learning", 3,0,0,3,4,7,0,3), ("ISC702", "Deep Learning", 3,0,0,3,5,7,0,3), ("ISC703", "Computer Vision", 3,0,0,3,4,7,0,3), ("ISC704", "Business Intelligence", 3,0,0,3,3,7,0,3), ("ISC705", "Cyber Security", 3,0,0,3,4,7,0,3), ("ISC706", "Cloud Computing", 3,0,0,3,3,7,0,3), ("ISC707", "ML Laboratory", 0,0,3,2,3,7,1,3), ("ISC708", "Cyber Security Laboratory", 0,0,3,2,3,7,1,3),
    ("ISC501", "Operating Systems", 3,0,0,3,4,5,0,3), ("ISC502", "Computer Networks", 3,0,0,3,4,5,0,3), ("ISC503", "Data Mining", 3,0,0,3,4,5,0,3), ("ISC504", "Compiler Design", 3,0,0,3,5,5,0,3), ("ISC505", "Big Data Analytics", 3,0,0,3,4,5,0,3), ("ISC506", "Software Engineering", 3,0,0,3,3,5,0,3), ("ISC507", "Big Data Laboratory", 0,0,3,2,3,5,1,3), ("ISC508", "Network Laboratory", 0,0,3,2,3,5,1,3),
    ("ISC301", "Data Structures", 3,0,0,3,4,3,0,3), ("ISC302", "Algorithms", 3,0,0,3,4,3,0,3), ("ISC303", "Database Systems", 3,0,0,3,4,3,0,3), ("ISC304", "Java Programming", 3,0,0,3,3,3,0,3), ("ISC305", "Computer Organization", 3,0,0,3,4,3,0,3), ("ISC306", "Professional Training", 2,0,0,2,1,3,0,2), ("ISC307", "Java Laboratory", 0,0,3,2,3,3,1,3),
    ("ISC101", "Python Programming", 3,0,0,3,3,1,0,3), ("ISC102", "Programming Fundamentals", 3,0,0,3,3,1,0,3), ("ISC103", "Discrete Mathematics", 3,0,0,3,4,1,0,3), ("ISC104", "Digital Fundamentals", 3,0,0,3,3,1,0,3), ("ISC105", "Engineering Mathematics", 3,0,0,3,4,1,0,3), ("ISC106", "Placement Foundations", 2,0,0,2,1,1,0,2), ("ISC107", "Python Laboratory", 0,0,3,2,3,1,1,3),
]
SECTIONS = [(f"IS{semester}{letter}", f"ISC {letter}", semester) for semester, letters in [(7,"ABCDEF"),(5,"GH"),(3,"I"),(1,"J")] for letter in letters]

def main():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            # Remove only the prior ISC demo records and their mappings.
            ids = [row[0] for row in conn.execute("SELECT section_id FROM sections WHERE department_id=?", (DEPT,))]
            run_ids = [row[0] for row in conn.execute("SELECT run_id FROM scheduler_run WHERE department_id=?", (DEPT,))]
            if run_ids:
                run_marks = ",".join("?" * len(run_ids))
                conn.execute(f"DELETE FROM schedule WHERE run_id IN ({run_marks})", run_ids)
                conn.execute(f"DELETE FROM validation_log WHERE run_id IN ({run_marks})", run_ids)
                conn.execute(f"DELETE FROM scheduler_run WHERE run_id IN ({run_marks})", run_ids)
            if ids:
                marks = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM faculty_assignment WHERE section_id IN ({marks})", ids)
                conn.execute(f"DELETE FROM section_course WHERE section_id IN ({marks})", ids)
                conn.execute(f"DELETE FROM room_section WHERE section_id IN ({marks})", ids)
                conn.execute(f"DELETE FROM class_teacher WHERE section_id IN ({marks})", ids)
            conn.execute("DELETE FROM department_faculty WHERE department_id=?", (DEPT,))
            conn.execute("DELETE FROM department_course WHERE department_id=?", (DEPT,))
            conn.execute("DELETE FROM rooms WHERE department_id=?", (DEPT,))
            conn.execute("DELETE FROM labs WHERE department_id=?", (DEPT,))
            conn.execute("DELETE FROM sections WHERE department_id=?", (DEPT,))
            conn.execute("DELETE FROM department WHERE department_id=?", (DEPT,))
            conn.execute("INSERT INTO department(department_id, department_name) VALUES (?, ?)", (DEPT, "Intelligent Systems and Cybersecurity"))
            conn.execute("INSERT OR REPLACE INTO academic_year(year, semester, odd_even) VALUES (2026, 1, 'ODD')")
            conn.executemany("INSERT OR REPLACE INTO days(day_id, day_name) VALUES (?, ?)", enumerate(["Monday","Tuesday","Wednesday","Thursday","Friday"], 1))
            conn.execute("DELETE FROM template")
            template = [(d,p,s,e,b,l) for d in range(1,6) for p,s,e,b,l in [(1,"08:30","09:25",0,0),(2,"09:25","10:20",0,0),(3,"10:40","11:35",0,0),(4,"11:35","12:30",0,0),(5,"13:20","14:15",0,0),(6,"14:15","15:10",0,0),(7,"15:10","16:05",0,0)]]
            conn.executemany("INSERT INTO template(day_id, period_no, start_time, end_time, is_break, is_lunch) VALUES (?, ?, ?, ?, ?, ?)", template)
            faculty = [(fid,name,30,f"{fid.lower()}@isc.edu.in","ACTIVE") for fid,name in TEACHERS] + [(fid,name,30,f"{fid.lower()}@isc.edu.in","ACTIVE") for fid,name in LAB_STAFF]
            conn.executemany("INSERT OR REPLACE INTO faculty(faculty_id, faculty_name, max_hours_week, email, status) VALUES (?, ?, ?, ?, ?)", faculty)
            conn.executemany("INSERT INTO department_faculty(department_id, faculty_id) VALUES (?, ?)", [(DEPT, f[0]) for f in faculty])
            rooms = [(f"JB{400+i}", DEPT, 60) for i in range(1,11)]
            conn.executemany("INSERT INTO rooms(room_no, department_id, capacity) VALUES (?, ?, ?)", rooms)
            labs = [("LAB101",DEPT,"AI Laboratory",35),("LAB102",DEPT,"ML Laboratory",35),("LAB103",DEPT,"Cyber Security Laboratory",35)]
            conn.executemany("INSERT INTO labs(lab_room_no, department_id, lab_name, capacity) VALUES (?, ?, ?, ?)", labs)
            conn.executemany("INSERT INTO sections(section_id, section_name, semester, department_id, capacity) VALUES (?, ?, ?, ?, 60)", [(a,b,c,DEPT) for a,b,c in SECTIONS])
            conn.executemany("INSERT INTO room_section(room_no, section_id) VALUES (?, ?)", [(rooms[i][0], section[0]) for i,section in enumerate(SECTIONS)])
            conn.executemany("INSERT OR REPLACE INTO courses(course_id, course_name, l, t, p, c, difficulty, semester, has_lab, weekly_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", COURSES)
            conn.executemany("INSERT INTO department_course(department_id, course_id) VALUES (?, ?)", [(DEPT,c[0]) for c in COURSES])
            labs_by_sem = {7:["LAB102","LAB103"],5:["LAB101","LAB103"],3:["LAB102"],1:["LAB101"]}
            for code,*_,semester,has_lab,hours in COURSES:
                if has_lab: conn.execute("INSERT INTO course_lab(course_id, lab_room_no) VALUES (?, ?)", (code, labs_by_sem[semester][0 if code.endswith("7") else -1]))
            teacher = 0
            for section_id, _, semester in SECTIONS:
                semester_courses = [c for c in COURSES if c[7] == semester]
                for course in semester_courses:
                    conn.execute("INSERT INTO section_course(section_id, course_id) VALUES (?, ?)", (section_id, course[0]))
                    assigned = LAB_STAFF[(course[0][-1] in "78") and (int(course[0][-1]) % 3) or 0][0] if course[8] else TEACHERS[teacher % len(TEACHERS)][0]
                    teacher += 0 if course[8] else 1
                    conn.execute("INSERT INTO faculty_assignment(faculty_id, section_id, course_id) VALUES (?, ?, ?)", (assigned,section_id,course[0]))
            rules = [("R001","Maximum two labs per day","At most two labs per day",1,"HARD","max_labs=2",1,0),("R002","Friday afternoon unavailable","Avoid faculty classes after P5 Friday",1,"HARD","Friday P6-P7",1,0),("R003","Lunch fixed","Lunch break is fixed",1,"HARD","12:30-13:20",1,0),("R004","Mentor hour","One mentor hour weekly",2,"SOFT","mentor=1",1,5)]
            conn.executemany("INSERT OR REPLACE INTO rules(rule_id, rule_name, description, priority, type, parameter, enabled, cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rules)
        print(f"Department 1\nFaculty {len(faculty)}\nSections {len(SECTIONS)}\nCourses {len(COURSES)}\nRooms {len(rooms)}\nLabs {len(labs)}\nAssignments Completed\nDatabase Ready")
    finally:
        conn.close()

if __name__ == "__main__": main()
