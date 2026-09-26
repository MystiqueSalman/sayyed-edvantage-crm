import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
COURSES_FILE = BASE_DIR / "data" / "knowledge" / "courses.json"


def load_courses() -> list:
    """Load Sayyed EdVantage course information from courses.json."""

    if not COURSES_FILE.exists():
        return []

    try:
        with COURSES_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("courses", [])

        return []

    except (json.JSONDecodeError, OSError):
        return []


def get_course_by_name(course_name: str) -> dict | None:
    """Find a course by its name."""

    courses = load_courses()

    search_name = course_name.strip().lower()

    for course in courses:
        if not isinstance(course, dict):
            continue

        name = str(course.get("course_name", "")).strip().lower()

        if name == search_name:
            return course

    return None


def get_course_pricing(course_name: str, international: bool = False) -> dict | None:
    """
    Return pricing information for a course.

    Indian students:
        Uses india_fee.

    International students:
        Uses international_base_fee_inr,
        international_discount_percent,
        and international_final_fee_inr.
    """

    course = get_course_by_name(course_name)

    if not course:
        return None

    if international:
        return {
            "course_id": course.get("course_id"),
            "course_name": course.get("course_name"),
            "pricing_type": "International",
            "base_fee_inr": course.get("international_base_fee_inr"),
            "discount_percent": course.get(
                "international_discount_percent", 25
            ),
            "final_fee_inr": course.get("international_final_fee_inr"),
            "gst_applicable": course.get("gst_applicable", True),
        }

    return {
        "course_id": course.get("course_id"),
        "course_name": course.get("course_name"),
        "pricing_type": "India",
        "fee_inr": course.get("india_fee"),
        "gst_applicable": course.get("gst_applicable", True),
    }


def get_course_knowledge() -> str:
    """
    Convert the complete course catalogue into structured text
    that the Sayyed EdVantage AI Agent can understand.
    """

    courses = load_courses()

    if not courses:
        return "No course information is currently available."

    knowledge_parts = []

    for course in courses:
        if not isinstance(course, dict):
            continue

        course_id = course.get("course_id", "")
        course_name = course.get("course_name", "")
        category = course.get("category", "")
        course_type = course.get("type", "")

        india_fee = course.get("india_fee", "")
        international_base_fee = course.get(
            "international_base_fee_inr", ""
        )
        international_discount = course.get(
            "international_discount_percent", 25
        )
        international_final_fee = course.get(
            "international_final_fee_inr", ""
        )

        gst_applicable = course.get("gst_applicable", True)

        modules = course.get("modules", [])

        if isinstance(modules, list):
            modules_text = ", ".join(str(module) for module in modules)
        else:
            modules_text = str(modules)

        section = f"""
Course ID: {course_id}
Course Name: {course_name}
Category: {category}
Program Type: {course_type}

INDIA PRICING:
Indian Student Fee: ₹{india_fee}
GST Applicable: {gst_applicable}

INTERNATIONAL PRICING:
International Base Fee: ₹{international_base_fee}
International Student Discount: {international_discount}%
International Final Fee: ₹{international_final_fee}
GST Applicable: {gst_applicable}

COURSE MODULES:
{modules_text}
""".strip()

        knowledge_parts.append(section)

    return "\n\n".join(knowledge_parts)