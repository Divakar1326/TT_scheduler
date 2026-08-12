"""Timetable Exporter constructing CSV & print-ready HTML layouts for Section, Faculty, and Lab schedules."""
import io
import csv
from typing import List
from app.core.domain import Schedule

class TimetableExporter:
    """Formats schedule lists into grid CSV dumps and print-ready HTML files."""

    @staticmethod
    def _get_metadata():
        """Helper to retrieve course names, faculty names, section metadata from DB."""
        from app.repository.connection import DatabaseConnectionManager
        conn, should_close = DatabaseConnectionManager.get_connection()
        
        course_names = {}
        course_has_lab = {}
        course_ltp = {}
        faculty_names = {}
        sec_details = {}
        lab_details = {}
        department_names = {}
        gen_date = "N/A"
        version_num = 1
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT course_id, course_name, has_lab, l, t, p FROM courses")
            for r in cursor.fetchall():
                course_names[r[0]] = r[1]
                course_has_lab[r[0]] = bool(r[2])
                course_ltp[r[0]] = (r[3], r[4], r[5])
                
            cursor.execute("SELECT faculty_id, faculty_name FROM faculty")
            for r in cursor.fetchall():
                faculty_names[r[0]] = r[1]
                
            cursor.execute("""
                SELECT s.section_id, s.section_name, s.semester, s.capacity, 
                       f.faculty_name, rs.room_no, s.department_id
                FROM sections s
                LEFT JOIN class_teacher ct ON s.section_id = ct.section_id
                LEFT JOIN faculty f ON ct.faculty_id = f.faculty_id
                LEFT JOIN room_section rs ON s.section_id = rs.section_id
            """)
            for r in cursor.fetchall():
                sec_details[r[0]] = {
                    "name": r[1],
                    "semester": r[2],
                    "capacity": r[3],
                    "teacher": r[4] or "Unassigned",
                    "classroom": r[5] or "Unassigned",
                    "department_id": r[6]
                }

            cursor.execute("SELECT lab_room_no, lab_name, capacity FROM labs")
            for r in cursor.fetchall():
                lab_details[r[0]] = {
                    "name": r[1],
                    "capacity": r[2]
                }

            cursor.execute("SELECT department_id, department_name FROM department")
            for r in cursor.fetchall():
                department_names[r[0]] = r[1]
                
            cursor.execute("SELECT finished_at, version FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                gen_date = row[0]
                version_num = row[1]
        except Exception:
            pass
        finally:
            if should_close:
                conn.close()

        return course_names, course_has_lab, course_ltp, faculty_names, sec_details, gen_date, version_num, lab_details, department_names

    @staticmethod
    def to_csv_section(schedule: List[Schedule], section_id: str) -> str:
        """Generates a CSV grid for a Section's timetable including BREAK and LUNCH columns."""
        course_names, course_has_lab, course_ltp, faculty_names, sec_details, _, _ = TimetableExporter._get_metadata()[:7]
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header: Period numbers & timings
        writer.writerow([
            "Day / Period", 
            "P1 (8:30-9:25)", 
            "P2 (9:25-10:20)", 
            "BREAK (10:20-10:40)", 
            "P3 (10:40-11:35)", 
            "P4 (11:35-12:30)", 
            "LUNCH (12:30-1:20)", 
            "P5 (1:20-2:15)", 
            "P6 (2:15-3:10)", 
            "P7 (3:10-4:05)"
        ])
        
        grid = {day: [""] * 7 for day in range(1, 6)}
        for s in schedule:
            if s.section_id == section_id:
                if 1 <= s.day_id <= 5 and 1 <= s.period_no <= 7:
                    room = s.room_no or s.lab_room_no or ""
                    c_name = course_names.get(s.course_id, s.course_id)
                    f_name = faculty_names.get(s.faculty_id, s.faculty_id)
                    grid[s.day_id][s.period_no - 1] = f"{s.course_id} - {c_name} ({f_name}) [{room}]"
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        for day in range(1, 6):
            row_data = [
                day_names[day],
                grid[day][0],
                grid[day][1],
                "BREAK",
                grid[day][2],
                grid[day][3],
                "LUNCH",
                grid[day][4],
                grid[day][5],
                grid[day][6]
            ]
            writer.writerow(row_data)
            
        return output.getvalue()

    @staticmethod
    def to_csv_faculty(schedule: List[Schedule], faculty_id: str) -> str:
        """Generates a CSV grid for a Faculty member's timetable."""
        course_names, course_has_lab, course_ltp, faculty_names, sec_details, _, _ = TimetableExporter._get_metadata()[:7]
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "Day / Period", 
            "P1 (8:30-9:25)", 
            "P2 (9:25-10:20)", 
            "BREAK (10:20-10:40)", 
            "P3 (10:40-11:35)", 
            "P4 (11:35-12:30)", 
            "LUNCH (12:30-1:20)", 
            "P5 (1:20-2:15)", 
            "P6 (2:15-3:10)", 
            "P7 (3:10-4:05)"
        ])
        grid = {day: [""] * 7 for day in range(1, 6)}
        
        for s in schedule:
            if s.faculty_id == faculty_id:
                if 1 <= s.day_id <= 5 and 1 <= s.period_no <= 7:
                    room = s.room_no or s.lab_room_no or ""
                    c_name = course_names.get(s.course_id, s.course_id)
                    grid[s.day_id][s.period_no - 1] = f"{s.course_id} - {c_name} ({s.section_id}) [{room}]"
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        for day in range(1, 6):
            row_data = [
                day_names[day],
                grid[day][0],
                grid[day][1],
                "BREAK",
                grid[day][2],
                grid[day][3],
                "LUNCH",
                grid[day][4],
                grid[day][5],
                grid[day][6]
            ]
            writer.writerow(row_data)
            
        return output.getvalue()

    @staticmethod
    def to_csv_lab(schedule: List[Schedule], lab_room_no: str) -> str:
        """Generates a CSV grid for a Laboratory's utilization schedule."""
        course_names, course_has_lab, course_ltp, faculty_names, sec_details, _, _ = TimetableExporter._get_metadata()[:7]
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "Day / Period", 
            "P1 (8:30-9:25)", 
            "P2 (9:25-10:20)", 
            "BREAK (10:20-10:40)", 
            "P3 (10:40-11:35)", 
            "P4 (11:35-12:30)", 
            "LUNCH (12:30-1:20)", 
            "P5 (1:20-2:15)", 
            "P6 (2:15-3:10)", 
            "P7 (3:10-4:05)"
        ])
        grid = {day: [""] * 7 for day in range(1, 6)}
        
        for s in schedule:
            if s.lab_room_no == lab_room_no:
                if 1 <= s.day_id <= 5 and 1 <= s.period_no <= 7:
                    c_name = course_names.get(s.course_id, s.course_id)
                    f_name = faculty_names.get(s.faculty_id, s.faculty_id)
                    grid[s.day_id][s.period_no - 1] = f"{s.course_id} - {c_name} ({s.section_id}) [{f_name}]"
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        for day in range(1, 6):
            row_data = [
                day_names[day],
                grid[day][0],
                grid[day][1],
                "BREAK",
                grid[day][2],
                grid[day][3],
                "LUNCH",
                grid[day][4],
                grid[day][5],
                grid[day][6]
            ]
            writer.writerow(row_data)
            
        return output.getvalue()

    @staticmethod
    def to_html_print_layout(schedule: List[Schedule], target_type: str, target_id: str) -> str:
        """Generates an elegant print-ready HTML grid view matching official university format."""
        course_names, course_has_lab, course_ltp, faculty_names, sec_details, gen_date, version_num, lab_details, department_names = TimetableExporter._get_metadata()
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        
        # We will build the content html dynamically.
        # If target_type is department, we loop over section_ids. Otherwise we just render the single target_id!
        targets = []
        if target_type == "department":
            targets = [sid for sid, details in sec_details.items() if details.get("department_id") == target_id]
            targets.sort()
        else:
            targets = [target_id]

        univ_name = "Hindustan Institute of Technology and Science"
        main_dept_name = "Department of Computer Science Engineering"
        if target_type == "department":
            main_dept_name = department_names.get(target_id, main_dept_name)
        elif target_type == "section" and target_id in sec_details:
            dept_id = sec_details[target_id].get("department_id")
            main_dept_name = department_names.get(dept_id, main_dept_name)

        content_html = ""
        for t_id in targets:
            grid = {day: [""] * 7 for day in range(1, 6)}
            slot_types = {day: [""] * 7 for day in range(1, 6)}
            
            for s in schedule:
                if not (1 <= s.day_id <= 5 and 1 <= s.period_no <= 7):
                    continue
                room = s.room_no or s.lab_room_no or "Unassigned"
                c_name = course_names.get(s.course_id, s.course_id)
                f_name = faculty_names.get(s.faculty_id, s.faculty_id)
                
                # Determine type
                ltp = course_ltp.get(s.course_id, (0,0,0))
                is_lab = course_has_lab.get(s.course_id, False)
                
                stype = "THEORY"
                if is_lab:
                    stype = "LAB"
                elif ltp[1] > 0:
                    stype = "TUTORIAL"
                    
                cell_text = f"<span class='course-name'>{c_name}</span><br><span class='course-code'>({s.course_id})</span><br><span class='faculty-name'>{f_name}</span><br><span class='room-no'>Room: {room}</span>"
                
                if (target_type == "section" or target_type == "department") and s.section_id == t_id:
                    grid[s.day_id][s.period_no - 1] = cell_text
                    slot_types[s.day_id][s.period_no - 1] = stype
                elif target_type == "faculty" and s.faculty_id == t_id:
                    grid[s.day_id][s.period_no - 1] = f"<span class='course-name'>{c_name}</span><br><span class='course-code'>({s.course_id})</span><br><span class='section-id'>Sec: {s.section_id}</span><br><span class='room-no'>Room: {room}</span>"
                    slot_types[s.day_id][s.period_no - 1] = stype
                elif target_type == "lab" and s.lab_room_no == t_id:
                    grid[s.day_id][s.period_no - 1] = f"<span class='course-name'>{c_name}</span><br><span class='course-code'>({s.course_id})</span><br><span class='section-id'>Sec: {s.section_id}</span><br><span class='faculty-name'>{f_name}</span>"
                    slot_types[s.day_id][s.period_no - 1] = "LAB"

            # Construct rows HTML
            rows_html = ""
            for day_id in range(1, 6):
                cols = []
                for p_idx in range(7):
                    val = grid[day_id][p_idx]
                    stype = slot_types[day_id][p_idx]
                    class_attr = f" class='slot-{stype.lower()}'" if val else ""
                    cols.append(f"<td{class_attr}>{val}</td>")
                
                break_cell = "<td class='slot-break'>B<br>R<br>E<br>A<br>K</td>"
                lunch_cell = "<td class='slot-lunch'>L<br>U<br>N<br>C<br>H</td>"
                
                day_row = f"""
                <tr>
                    <th>{day_names[day_id]}</th>
                    {cols[0]}
                    {cols[1]}
                    {break_cell}
                    {cols[2]}
                    {cols[3]}
                    {lunch_cell}
                    {cols[4]}
                    {cols[5]}
                    {cols[6]}
                </tr>
                """
                rows_html += day_row

            # Find specific metadata for headers
            sec_meta = sec_details.get(t_id, {}) if (target_type == "section" or target_type == "department") else {}
            classroom_label = sec_meta.get("classroom", "N/A")
            teacher_label = sec_meta.get("teacher", "N/A")
            capacity_label = sec_meta.get("capacity", "N/A")
            semester_label = sec_meta.get("semester", "N/A")
            
            heading_target_type = "Section" if target_type == "department" else target_type.capitalize()
            heading_target_id = t_id

            # Create specific header table
            if target_type == "section" or target_type == "department":
                header_table = f"""
                <table class="header-table">
                    <tr>
                        <td><span class="meta-label">Department:</span> {main_dept_name}</td>
                        <td><span class="meta-label">Semester:</span> {semester_label}</td>
                        <td><span class="meta-label">Section:</span> {heading_target_id}</td>
                    </tr>
                    <tr>
                        <td><span class="meta-label">Strength:</span> {capacity_label} students</td>
                        <td><span class="meta-label">Class Teacher:</span> {teacher_label}</td>
                        <td><span class="meta-label">Classroom:</span> {classroom_label}</td>
                    </tr>
                    <tr>
                        <td><span class="meta-label">Academic Year:</span> 2026-2027</td>
                        <td><span class="meta-label">Version:</span> V{version_num}</td>
                        <td><span class="meta-label">Generated Date:</span> {gen_date}</td>
                    </tr>
                </table>
                """
            elif target_type == "faculty":
                header_table = f"""
                <table class="header-table">
                    <tr>
                        <td><span class="meta-label">Faculty Name:</span> {faculty_names.get(t_id, t_id)}</td>
                        <td><span class="meta-label">Faculty ID:</span> {t_id}</td>
                        <td><span class="meta-label">Academic Year:</span> 2026-2027</td>
                    </tr>
                    <tr>
                        <td><span class="meta-label">Department:</span> {main_dept_name}</td>
                        <td><span class="meta-label">Version:</span> V{version_num}</td>
                        <td><span class="meta-label">Generated Date:</span> {gen_date}</td>
                    </tr>
                </table>
                """
            else:  # lab
                header_table = f"""
                <table class="header-table">
                    <tr>
                        <td><span class="meta-label">Laboratory Room:</span> {t_id}</td>
                        <td><span class="meta-label">Lab Name:</span> {lab_details.get(t_id, {}).get("name", "N/A")}</td>
                        <td><span class="meta-label">Capacity:</span> {lab_details.get(t_id, {}).get("capacity", "N/A")}</td>
                    </tr>
                    <tr>
                        <td><span class="meta-label">Academic Year:</span> 2026-2027</td>
                        <td><span class="meta-label">Version:</span> V{version_num}</td>
                        <td><span class="meta-label">Generated Date:</span> {gen_date}</td>
                    </tr>
                </table>
                """

            grid_content = f"""
            <div class="timetable-grid-block" style="margin-bottom: 3rem; page-break-after: always;">
                <h3 style="font-size:1.15rem; font-weight:700; color:#0f172a; border-bottom:2px solid #cbd5e1; padding-bottom:0.25rem; margin-bottom:1rem;">{heading_target_type}: {t_id}</h3>
                
                {header_table}
                
                <table class="timetable-table">
                    <thead>
                        <tr>
                            <th style="width: 100px;">Day / Period</th>
                            <th>P1<br><span style="font-size:0.7rem;font-weight:normal;">8:30-9:25</span></th>
                            <th>P2<br><span style="font-size:0.7rem;font-weight:normal;">9:25-10:20</span></th>
                            <th style="width: 40px; font-size:0.7rem;">BREAK<br><span style="font-size:0.65rem;font-weight:normal;">10:20-10:40</span></th>
                            <th>P3<br><span style="font-size:0.7rem;font-weight:normal;">10:40-11:35</span></th>
                            <th>P4<br><span style="font-size:0.7rem;font-weight:normal;">11:35-12:30</span></th>
                            <th style="width: 40px; font-size:0.7rem;">LUNCH<br><span style="font-size:0.65rem;font-weight:normal;">12:30-1:20</span></th>
                            <th>P5<br><span style="font-size:0.7rem;font-weight:normal;">1:20-2:15</span></th>
                            <th>P6<br><span style="font-size:0.7rem;font-weight:normal;">2:15-3:10</span></th>
                            <th>P7<br><span style="font-size:0.7rem;font-weight:normal;">3:10-4:05</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
            """
            content_html += grid_content

        html_layout = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>University Timetable - {target_type.upper()} {target_id}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 1.5rem; color: #1e293b; background-color: #f8fafc; }}
                .printable-container {{ background-color: #ffffff; border: 2px solid #e2e8f0; padding: 2rem; border-radius: 8px; max-width: 1200px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
                .header-table {{ width: 100%; margin-bottom: 1.5rem; border-collapse: collapse; border: 1px solid #e2e8f0; }}
                .header-table td {{ border: 1px solid #e2e8f0; padding: 0.5rem 0.75rem; font-size: 0.85rem; width: 33.33%; }}
                .university-title {{ font-size: 1.6rem; font-weight: 700; color: #0f172a; text-align: center; margin-bottom: 0.25rem; }}
                .department-title {{ font-size: 1.1rem; font-weight: 600; color: #475569; text-align: center; margin-bottom: 1.5rem; border-bottom: 3px double #cbd5e1; padding-bottom: 0.5rem; }}
                .meta-label {{ font-weight: bold; color: #334155; }}
                
                table.timetable-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 1rem; }}
                table.timetable-table th, table.timetable-table td {{ border: 1px solid #cbd5e1; padding: 0.5rem; text-align: center; font-size: 0.8rem; overflow: hidden; }}
                table.timetable-table th {{ background-color: #f1f5f9; font-weight: 600; color: #334155; height: 35px; }}
                
                /* Color Codes */
                .slot-theory {{ background-color: #e0f2fe; color: #0369a1; border-left: 3px solid #0284c7 !important; }}
                .slot-tutorial {{ background-color: #fef3c7; color: #b45309; border-left: 3px solid #d97706 !important; }}
                .slot-lab {{ background-color: #dcfce7; color: #15803d; border-left: 3px solid #16a34a !important; }}
                .slot-break, .slot-lunch {{ background-color: #f1f5f9; font-weight: bold; font-size: 0.75rem; color: #64748b; letter-spacing: 0.1em; width: 35px; }}
                
                .course-code {{ font-size: 0.75rem; color: #64748b; font-weight: normal; }}
                .course-name {{ font-weight: bold; font-size: 0.8rem; color: #1e293b; display: block; margin-bottom: 0.15rem; }}
                .faculty-name, .section-id {{ font-size: 0.75rem; font-weight: 500; display: block; color: #334155; }}
                .room-no {{ font-size: 0.75rem; color: #64748b; font-style: italic; }}
                
                .legend {{ display: flex; gap: 1.5rem; justify-content: center; margin-top: 1.5rem; font-size: 0.85rem; border-top: 1px solid #e2e8f0; padding-top: 1rem; }}
                .legend-item {{ display: flex; align-items: center; gap: 0.5rem; }}
                .legend-color {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid #cbd5e1; }}
                
                .no-print {{ display: flex; justify-content: space-between; max-width: 1200px; margin: 0 auto 1rem auto; }}
                .btn {{ background-color: #10b981; color: white; border: none; padding: 0.5rem 1.25rem; font-weight: bold; cursor: pointer; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.5rem; }}
                .btn:hover {{ background-color: #059669; }}
                
                @media print {{
                    body {{ background-color: #ffffff; margin: 0; }}
                    .printable-container {{ border: none; box-shadow: none; padding: 0; }}
                    .no-print {{ display: none; }}
                }}
            </style>
        </head>
        <body>
            <div class="no-print">
                <button class="btn" onclick="window.print()">Print / Save PDF</button>
            </div>
            
            <div class="printable-container">
                <div class="university-title">{univ_name}</div>
                <div class="department-title">{main_dept_name}</div>
                
                {content_html}
                
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color slot-theory"></div>
                        <span>Theory Class</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color slot-tutorial"></div>
                        <span>Tutorial Slot</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color slot-lab"></div>
                        <span>Laboratory Session</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color slot-break"></div>
                        <span>Break / Lunch Intervals</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html_layout

    @staticmethod
    def to_excel_layout(schedule: List[Schedule], target_type: str, target_id: str) -> str:
        """Generates a styled Excel spreadsheet by applying inline display configurations."""
        html = TimetableExporter.to_html_print_layout(schedule, target_type, target_id)
        # Disable print controls for cleaner spreadsheet opening
        html = html.replace('<div class="no-print">', '<div class="no-print" style="display:none;">')
        return html
