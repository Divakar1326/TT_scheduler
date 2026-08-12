"""Soft constraint scoring and penalty calculations."""
from typing import Dict, List
from collections import defaultdict
from app.core.domain import Schedule


def score_morning_lab_preference(allocation: Schedule) -> int:
    """Labs prefer morning slots (Periods 1-4). Penalty if scheduled after Period 4."""
    if allocation.lab_room_no and allocation.period_no > 4:
        return 5
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
            penalty += (count - 3) * 2
    return penalty


def score_compact_timetable(section_id: str, current_schedule: List[Schedule]) -> int:
    """Minimize gaps (idle periods) in section schedule per day."""
    day_slots = defaultdict(list)
    for s in current_schedule:
        if s.section_id == section_id:
            day_slots[s.day_id].append(s.period_no)
    penalty = 0
    for day, periods in day_slots.items():
        if len(periods) > 1:
            p_min = min(periods)
            p_max = max(periods)
            gaps = (p_max - p_min + 1) - len(periods)
            penalty += gaps * 2
    return penalty


def score_minimize_room_changes(section_id: str, current_schedule: List[Schedule], room_sections: Dict[str, str]) -> int:
    """Section should stay in permanent room. Penalty for each theory period in a different room."""
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
    Excludes practical/lab classes which are naturally consecutive on the same day.
    """
    day_course_counts = defaultdict(lambda: defaultdict(int))
    for s in current_schedule:
        if s.section_id == section_id and not s.lab_room_no:
            day_course_counts[s.day_id][s.course_id] += 1
    penalty = 0
    for day, courses in day_course_counts.items():
        for course_id, count in courses.items():
            if count > 1:
                penalty += (count - 1) * 3
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
            penalty += gaps * 1
    return penalty


def score_lab_spread(section_id: str, current_schedule: List[Schedule]) -> int:
    """Penalise multiple lab sessions for the same section on the same weekday.
    Labs should be spread across different days of the week.
    """
    day_lab_counts = defaultdict(int)
    for s in current_schedule:
        if s.section_id == section_id and s.lab_room_no:
            day_lab_counts[s.day_id] += 1
    penalty = 0
    for day, count in day_lab_counts.items():
        if count > 1:
            penalty += (count - 1) * 8  # heavy penalty for lab stacking
    return penalty


def calculate_soft_penalty_percentage(schedule: List[Schedule], room_sections: Dict[str, str]) -> float:
    """
    Calculates a meaningful Soft Penalty % using per-category normalization.

    Instead of dividing by a single giant theoretical maximum (which always
    dwarfs actual penalties), we compute each category independently and
    average the scores. Each category returns a value in [0, 100]:
      0   = perfectly optimal
      100 = worst possible for that category

    Categories:
      1. Lab morning preference
      2. Faculty workload balance
      3. Compact student timetable (section gaps)
      4. Subject distribution (no same-course twice in a day)
      5. Faculty gap minimization
      6. Lab spread (no two labs on same day for same section)
      7. Room stability (minimize room changes)
    """
    if not schedule:
        return 0.0

    sections = set(s.section_id for s in schedule)
    faculties = set(s.faculty_id for s in schedule)

    scores = []

    # --- Category 1: Lab morning preference ---
    labs = [s for s in schedule if s.lab_room_no]
    if labs:
        actual = sum(score_morning_lab_preference(s) for s in labs)
        max_possible = len(labs) * 5  # max 5 per lab
        scores.append(actual / max_possible * 100)
    else:
        scores.append(0.0)

    # --- Category 2: Faculty workload balance ---
    fac_balance_actual = sum(score_balanced_faculty_workload(f, schedule) for f in faculties)
    fac_counts = defaultdict(int)
    for s in schedule:
        fac_counts[s.faculty_id] += 1
    # Max: each class over 3 per faculty per day costs 2 pts
    fac_balance_max = sum(max(0, count - 3) * 2 for count in fac_counts.values())
    scores.append((fac_balance_actual / max(1, fac_balance_max)) * 100 if fac_balance_max else 0.0)

    # --- Category 3: Compact student timetable ---
    compact_actual = sum(score_compact_timetable(sec, schedule) for sec in sections)
    sec_days = defaultdict(set)
    for s in schedule:
        sec_days[s.section_id].add(s.day_id)
    compact_max = sum(len(days) * 10 for days in sec_days.values())  # max 10 pts per section-day
    scores.append((compact_actual / max(1, compact_max)) * 100 if compact_max else 0.0)

    # --- Category 4: Subject distribution ---
    dist_actual = sum(score_subject_distribution(sec, schedule) for sec in sections)
    sec_course_counts = defaultdict(int)
    for s in schedule:
        if not s.lab_room_no:
            sec_course_counts[(s.section_id, s.course_id)] += 1
    dist_max = sum(max(0, count - 1) * 3 for count in sec_course_counts.values())
    scores.append((dist_actual / max(1, dist_max)) * 100 if dist_max else 0.0)

    # --- Category 5: Faculty gap minimization ---
    fac_gap_actual = sum(score_faculty_gap_minimization(f, schedule) for f in faculties)
    fac_days = defaultdict(set)
    for s in schedule:
        fac_days[s.faculty_id].add(s.day_id)
    fac_gap_max = sum(len(days) * 5 for days in fac_days.values())  # max 5 pts per faculty-day
    scores.append((fac_gap_actual / max(1, fac_gap_max)) * 100 if fac_gap_max else 0.0)

    # --- Category 6: Lab spread ---
    lab_spread_actual = sum(score_lab_spread(sec, schedule) for sec in sections)
    day_lab_counts = defaultdict(int)
    for s in schedule:
        if s.lab_room_no:
            day_lab_counts[(s.section_id, s.day_id)] += 1
    lab_spread_max = sum(max(0, count - 1) * 8 for count in day_lab_counts.values())
    scores.append((lab_spread_actual / max(1, lab_spread_max)) * 100 if lab_spread_max else 0.0)

    # --- Category 7: Room stability ---
    room_chg_actual = sum(score_minimize_room_changes(sec, schedule, room_sections) for sec in sections)
    theory_count = sum(1 for s in schedule if not s.lab_room_no)
    room_chg_max = theory_count * 3
    scores.append((room_chg_actual / max(1, room_chg_max)) * 100 if room_chg_max else 0.0)

    # Return average across all categories
    return min(100.0, round(sum(scores) / len(scores), 2))


def calculate_total_penalty(schedule: List[Schedule], room_sections: Dict[str, str]) -> int:
    """Calculates aggregate soft constraint penalty score for the entire schedule."""
    total_penalty = 0
    sections = set(s.section_id for s in schedule)
    faculties = set(s.faculty_id for s in schedule)

    for sec in sections:
        total_penalty += score_compact_timetable(sec, schedule)
        total_penalty += score_minimize_room_changes(sec, schedule, room_sections)
        total_penalty += score_subject_distribution(sec, schedule)
        total_penalty += score_lab_spread(sec, schedule)

    for fac in faculties:
        total_penalty += score_balanced_faculty_workload(fac, schedule)
        total_penalty += score_faculty_gap_minimization(fac, schedule)

    for s in schedule:
        total_penalty += score_morning_lab_preference(s)

    return total_penalty


def calculate_max_possible_penalty(schedule: List[Schedule], room_sections: Dict[str, str]) -> int:
    """Legacy function retained for backward compatibility. Delegates to category-aware calculation."""
    if not schedule:
        return 1
    # Use the same approach: sum of per-category theoretical maxima
    labs_count = sum(1 for s in schedule if s.lab_room_no)
    max_lab_pref = labs_count * 5

    fac_counts = defaultdict(int)
    for s in schedule:
        fac_counts[s.faculty_id] += 1
    max_fac_workload = sum(max(0, count - 3) * 2 for count in fac_counts.values())

    theory_count = sum(1 for s in schedule if not s.lab_room_no)
    max_room_change = theory_count * 3 if room_sections else 0

    sec_course_counts = defaultdict(int)
    for s in schedule:
        if not s.lab_room_no:
            sec_course_counts[(s.section_id, s.course_id)] += 1
    max_subject_dist = sum(max(0, count - 1) * 3 for count in sec_course_counts.values())

    sec_days = set((s.section_id, s.day_id) for s in schedule)
    max_sec_gaps = len(sec_days) * 10

    fac_days = set((s.faculty_id, s.day_id) for s in schedule)
    max_fac_gaps = len(fac_days) * 5

    day_lab_counts = defaultdict(int)
    for s in schedule:
        if s.lab_room_no:
            day_lab_counts[(s.section_id, s.day_id)] += 1
    max_lab_spread = sum(max(0, count - 1) * 8 for count in day_lab_counts.values())

    total_max = (max_lab_pref + max_fac_workload + max_room_change +
                 max_subject_dist + max_sec_gaps + max_fac_gaps + max_lab_spread)
    return max(1, total_max)
