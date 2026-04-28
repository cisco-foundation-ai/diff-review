from dataclasses import dataclass


@dataclass
class PRFile:
    """Represents a file changed in a PR"""

    path: str
    additions: int
    deletions: int
    status: str  # added, modified, removed, renamed
    diff: str


@dataclass
class Category:
    """Represents a category of related files"""

    name: str
    description: str
    files: list[PRFile]
    priority: int = 0  # For sorting (0 = highest)
    detailed_summary: str = ""  # LLM-generated detailed summary of changes
