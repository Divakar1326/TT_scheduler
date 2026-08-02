"""Prompt manager for rules translation via Gemini 3.5 Flash."""
import os
import json
from typing import Dict, Any, Optional

DEFAULT_SYSTEM_INSTRUCTION = """
You are an AI assistant that translates natural language scheduling rules for a university timetable into a structured JSON configuration.
Your output must be a valid JSON object matching this schema:
{
  "rule_id": "unique slug (e.g. F01_avoid_friday)",
  "rule_name": "human readable name",
  "type": "HARD" or "SOFT",
  "priority": integer (default 1),
  "parameter": {
    "faculty_id": "optional string (e.g. F01)",
    "course_id": "optional string (e.g. CS101)",
    "section_id": "optional string (e.g. S1)",
    "room_no": "optional string (e.g. R101)",
    "lab_room_no": "optional string (e.g. LAB101)",
    "avoid_days": "optional array of integers (1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri)",
    "avoid_periods": "optional array of integers (1 to 7)",
    "preferred_days": "optional array of integers",
    "preferred_periods": "optional array of integers"
  }
}

Do not include any markdown wrappers (like ```json), commentary, or extra characters. Output ONLY raw JSON.
"""

DEFAULT_EXAMPLES = """
Example 1:
User Rule: "Dr. Rekha (F01) cannot teach on Friday after Period 4"
Output JSON:
{
  "rule_id": "F01_no_friday_after_p4",
  "rule_name": "Dr. Rekha avoid Fri after P4",
  "type": "HARD",
  "priority": 1,
  "parameter": {
    "faculty_id": "F01",
    "avoid_days": [5],
    "avoid_periods": [5, 6, 7]
  }
}

Example 2:
User Rule: "Course CS101 should preferably not be scheduled in Period 1"
Output JSON:
{
  "rule_id": "CS101_avoid_p1",
  "rule_name": "CS101 avoid P1",
  "type": "SOFT",
  "priority": 2,
  "parameter": {
    "course_id": "CS101",
    "avoid_periods": [1]
  }
}
"""

class RulePromptManager:
    """Manages AI rule translation prompt generation."""

    def __init__(self, system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION, examples: str = DEFAULT_EXAMPLES):
        self.system_instruction = system_instruction
        self.examples = examples

    def generate_prompt(self, user_rule: str) -> str:
        """Combines system instruction, examples, and user input into a single prompt string."""
        return f"{self.system_instruction}\n{self.examples}\nUser Rule: \"{user_rule}\"\nOutput JSON:"
