"""Group job titles into broad categories for coordinator analytics (keyword rules)."""

import re

# Checked in order: the first matching category wins ("Data Engineer" is Data, not Software).
ROLE_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Data & AI",
        (
            "data",
            "analyst",
            "analytics",
            "machine learning",
            "ml",
            "ai",
            "scientist",
            "business intelligence",
            "bi",
        ),
    ),
    (
        "Cloud & DevOps",
        (
            "cloud",
            "devops",
            "sre",
            "site reliability",
            "infrastructure",
            "platform engineer",
            "system administrator",
            "network",
        ),
    ),
    ("Cybersecurity", ("security", "cyber", "soc", "penetration")),
    ("QA & Testing", ("qa", "test", "testing", "quality")),
    (
        "Embedded & Hardware",
        ("embedded", "vlsi", "hardware", "firmware", "electronics", "design verification"),
    ),
    ("Product & Design", ("product", "ui", "ux", "designer")),
    (
        "Software Engineering",
        (
            "software",
            "developer",
            "sde",
            "engineer",
            "programmer",
            "full stack",
            "frontend",
            "backend",
            "mobile",
            "android",
            "ios",
        ),
    ),
    ("Consulting & Business", ("consultant", "business", "sales", "marketing", "operations")),
    ("Graduate Trainee", ("trainee", "graduate", "get")),
]


def categorise_role(title: str | None) -> str | None:
    if not title:
        return None
    low = title.lower()
    for category, words in ROLE_CATEGORIES:
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in words):
            return category
    return "Other"
