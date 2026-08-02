"""Soft constraint scoring and penalty calculations."""
from typing import Dict, List
from collections import defaultdict
from app.models.domain import Schedule

def score_morning_lab_preference(allocation: Schedule) -> int:
    """Labs prefer morning slots (Periods 1-4). Penalty if scheduled after Period 4."""
    if allocation.lab_room_no and allocation.period_no > 4:
        return 5  # Penalty weight
    return 0

def score_balanced_faculty_workload(faculty_id: str, current_schedule: List[Schedule]) -> int:
    """Balanced workload per day. Penalty if faculty teaches more than 3 classes in a single day."""
    day_counts = defaultdict(int)
    for s in current_schedule:
        if s.faculty_id == faculty_id:
            day_counts[s.day_id] += 1
            
    penalty = 0
    for day, count in day_counts.items():
        if count > 3:
            penalty += (count - 3) * 2  # 2 points per class over 3
    return penalty

def score_compact_timetable(section_id: str, current_schedule: List[Schedule]) -> int:
    """Minimize gaps (idle periods) in section schedule per day.
    For each day, find first and last period and count empty slots in between.
    """
    day_slots = defaultdict(list)
    for s in current_schedule:
        if s.section_id == section_id:
            day_slots[s.day_id].append(s.period_no)
            
    penalty = 0
    for day, periods in day_slots.items():
        if len(periods) > 1:
            p_min = min(periods)
            p_max = max(periods)
            # Total periods between min and max that are not in the list
            gaps = (p_max - p_min + 1) - len(periods)
            penalty += gaps * 2  # 2 penalty points per gap period
    return penalty

def score_minimize_room_changes(section_id: str, current_schedule: List[Schedule], room_sections: Dict[str, str]) -> int:
    """Section should stay in permanent room. Penalty of 3 points for each theory period in a different room."""
    perm_room = room_sections.get(section_id)
    if not perm_room:
        return 0
        
    penalty = 0
    for s in current_schedule:
        if s.section_id == section_id and not s.lab_room_no:
            if s.room_no != perm_room:
                penalty += 3
    return penalty

def score_subject_distribution(section_id: str, current_schedule: List[Schedule]) -> int:
    """Prefer distributing course sessions across different days.
    If the same course is taught multiple times on the same day for a section, add penalty.
    """
    day_course_counts = defaultdict(lambda: defaultdict(int))
    for s in current_schedule:
        if s.section_id == section_id:
            day_course_counts[s.day_id][s.course_id] += 1
            
    penalty = 0
    for day, courses in day_course_counts.items():
        for course_id, count in courses.items():
            if count > 1:
                penalty += (count - 1) * 3  # 3 penalty points for daily duplicate sessions
    return penalty

def score_faculty_gap_minimization(faculty_id: str, current_schedule: List[Schedule]) -> int:
    """Minimize idle gaps in faculty schedule per day."""
    day_slots = defaultdict(list)
    for s in current_schedule:
        if s.faculty_id == faculty_id:
            day_slots[s.day_id].append(s.period_no)
            
    penalty = 0
    for day, periods in day_slots.items():
        if len(periods) > 1:
            p_min = min(periods)
            p_max = max(periods)
            gaps = (p_max - p_min + 1) - len(periods)
            penalty += gaps * 1  # 1 penalty point per gap period
    return penalty
