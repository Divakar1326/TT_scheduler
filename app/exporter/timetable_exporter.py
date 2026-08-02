"""Timetable Exporter constructing CSV & print-ready HTML layouts for Section, Faculty, and Lab schedules."""
import io
import csv
from typing import List
from app.models.domain import Schedule

class TimetableExporter:
    """Formats schedule lists into grid CSV dumps and print-ready HTML files."""

    @staticmethod
    def to_csv_section(schedule: List[Schedule], section_id: str) -> str:
        """Generates a CSV grid for a Section's timetable (Days as rows, Periods as columns)."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header: Period numbers
        writer.writerow(["Day / Period", "Period 1", "Period 2", "Period 3", "Period 4", "Period 5", "Period 6", "Period 7"])
        
        # Grid initialization
        grid = {day: [""] * 7 for day in range(1, 6)}
        
        for s in schedule:
            if s.section_id == section_id:
                if 1 <= s.day_id <= 5 and 1 <= s.period_no <= 7:
                    room = s.room_no or s.lab_room_no or ""
                    grid[s.day_id][s.period_no - 1] = f"{s.course_id} ({s.faculty_id}) [{room}]"
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        for day in range(1, 6):
            writer.writerow([day_names[day]] + grid[day])
            
        return output.getvalue()

    @staticmethod
    def to_csv_faculty(schedule: List[Schedule], faculty_id: str) -> str:
        """Generates a CSV grid for a Faculty member's timetable."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["Day / Period", "Period 1", "Period 2", "Period 3", "Period 4", "Period 5", "Period 6", "Period 7"])
        grid = {day: [""] * 7 for day in range(1, 6)}
        
        for s in schedule:
            if s.faculty_id == faculty_id:
                if 1 <= s.day_id <= 5 and 1 <= s.period_no <= 7:
                    room = s.room_no or s.lab_room_no or ""
                    grid[s.day_id][s.period_no - 1] = f"{s.course_id} ({s.section_id}) [{room}]"
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        for day in range(1, 6):
            writer.writerow([day_names[day]] + grid[day])
            
        return output.getvalue()

    @staticmethod
    def to_csv_lab(schedule: List[Schedule], lab_room_no: str) -> str:
        """Generates a CSV grid for a Laboratory's utilization schedule."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["Day / Period", "Period 1", "Period 2", "Period 3", "Period 4", "Period 5", "Period 6", "Period 7"])
        grid = {day: [""] * 7 for day in range(1, 6)}
        
        for s in schedule:
            if s.lab_room_no == lab_room_no:
                if 1 <= s.day_id <= 5 and 1 <= s.period_no <= 7:
                    grid[s.day_id][s.period_no - 1] = f"{s.course_id} ({s.section_id}) [{s.faculty_id}]"
        
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        for day in range(1, 6):
            writer.writerow([day_names[day]] + grid[day])
            
        return output.getvalue()

    @staticmethod
    def to_html_print_layout(schedule: List[Schedule], target_type: str, target_id: str) -> str:
        """Generates an elegant print-ready HTML grid view."""
        grid = {day: [""] * 7 for day in range(1, 6)}
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        
        for s in schedule:
            if not (1 <= s.day_id <= 5 and 1 <= s.period_no <= 7):
                continue
            match = False
            room = s.room_no or s.lab_room_no or "Unassigned"
            if target_type == "section" and s.section_id == target_id:
                grid[s.day_id][s.period_no - 1] = f"<strong>{s.course_id}</strong><br>{s.faculty_id}<br>[{room}]"
            elif target_type == "faculty" and s.faculty_id == target_id:
                grid[s.day_id][s.period_no - 1] = f"<strong>{s.course_id}</strong><br>{s.section_id}<br>[{room}]"
            elif target_type == "lab" and s.lab_room_no == target_id:
                grid[s.day_id][s.period_no - 1] = f"<strong>{s.course_id}</strong><br>{s.section_id}<br>({s.faculty_id})"

        rows_html = ""
        for day_id in range(1, 6):
            cols_html = "".join([f"<td>{cell}</td>" for cell in grid[day_id]])
            rows_html += f"<tr><th>{day_names[day_id]}</th>{cols_html}</tr>"

        html_layout = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Timetable - {target_type.upper()} {target_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; color: #111; }}
                h1 {{ color: #f97316; text-align: center; margin-bottom: 0.5rem; }}
                h2 {{ text-align: center; color: #444; font-size: 1.1rem; margin-bottom: 2rem; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
                th, td {{ border: 1px solid #ddd; padding: 1rem; text-align: center; font-size: 0.85rem; }}
                th {{ background-color: #f9fafb; font-weight: bold; }}
                @media print {{
                    button {{ display: none; }}
                }}
            </style>
        </head>
        <body>
            <h1>University Timetable</h1>
            <h2>Target: {target_type.capitalize()} {target_id}</h2>
            <button onclick="window.print()" style="background:#10b981; color:white; border:none; padding:0.5rem 1rem; font-weight:bold; cursor:pointer; margin-bottom:1rem;">Print / Save PDF</button>
            <table>
                <thead>
                    <tr>
                        <th>Day / Period</th>
                        <th>Period 1</th>
                        <th>Period 2</th>
                        <th>Period 3</th>
                        <th>Period 4</th>
                        <th>Period 5</th>
                        <th>Period 6</th>
                        <th>Period 7</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </body>
        </html>
        """
        return html_layout
