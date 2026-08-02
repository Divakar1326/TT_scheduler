"""Session data structure for scheduling units."""
from dataclasses import dataclass

@dataclass
class Session:
    """Represents a discrete scheduling unit derived from a course's L-T-P parameters."""
    session_id: str
    course_id: str
    section_id: str
    faculty_id: str
    type: str  # 'THEORY', 'TUTORIAL', 'PRACTICAL'
    duration: int  # Number of periods (1 for theory/tutorial, P for practical)
    has_lab: bool
